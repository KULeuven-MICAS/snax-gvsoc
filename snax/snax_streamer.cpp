/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// A SNAX streamer as snax_cluster's Chisel streamer builds it
// (hw/chisel/.../streamer/Streamer.scala, readerWriter/, reqRspManager/):
// data movers, each with an address generator (AGU) and one 64-bit TCDM port
// per channel, configured through CSRs and started together.
//
// CSRs, offsets from the streamer's first CSR (the CSR router removes it):
//   per mover: pointer low and high, one spatial stride per spatial bound,
//   the temporal bounds, the temporal strides; then the start CSR, all
//   read-write; then busy and the performance counter, read-only.
//
// Timing, per cycle t while busy (s is the cycle the start write is taken):
//   1. requests: a channel requests when its address FIFO has an address and
//      it has credit (reads in flight plus beats buffered below fifo_depth);
//      a request not granted is sent again the next cycle.
//   2. the TCDM crossbar arbitrates (its own event, same cycle).
//   3. commit: granted addresses leave their FIFO; the AGU pushes one group
//      of addresses when every channel's FIFO has room, a grant in this cycle
//      making room (the pipe queue); it starts at s + 1, so the first request
//      is at s + 2.
// A mover is busy while its AGU is busy or an address waits; the streamer is
// busy from s + 1 to the cycle after its last mover is done (e). The counter
// is reset at s + 1 and counts the busy cycles after it, so its final value
// is e - s - 1. Busy and the counter are computed from these cycles when they
// are read.
//
// Not modelled yet: writers (SG3 P5; a writer with a zero temporal bound is
// accepted, it never starts), the beats to and from the accelerator (P5).
// Not modelled: reader-writers, configurable channels and byte masks, address
// remapping (logic word sizes), datapath extensions, a second clock domain;
// snax_streamer.py refuses their keys.

#include <deque>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>


class SnaxStreamer;

// A data mover: a reader or a writer, its configuration and its AGU
struct Mover
{
    bool is_reader;
    std::vector<uint32_t> spatial_bounds;
    int temporal_dim;
    int num_channel;
    int fifo_depth;
    int csr_first;              // offset of its first CSR
    int first_channel;          // index of its first channel in the streamer

    // Configuration, taken at start
    uint32_t ptr;
    std::vector<uint32_t> spatial_strides;
    std::vector<uint32_t> temporal_bounds;
    std::vector<uint32_t> temporal_strides;
    uint32_t repeat;            // a reader's beat repeat (temporal stride 0 on loop 0)

    // AGU
    bool agu_busy;
    std::vector<uint32_t> loop_index;    // per temporal loop, 0 to bound - 1
    std::vector<uint32_t> loop_offset;   // per temporal loop, index * stride
};

// One channel: one 64-bit TCDM port
struct Channel
{
    Mover *mover;
    int lane;                   // index within its mover

    std::deque<uint32_t> addrs; // address FIFO, fifo_depth deep
    int used;                   // reads in flight plus beats buffered
    vp::IoReq *held;            // request sent and not granted yet
    bool granted;               // granted in this cycle
    std::deque<uint64_t> data;  // beats received (reader)

    // Requests in flight, at most fifo_depth, plus the one being sent
    vp::IoReq *reqs;
    uint64_t *bufs;
    std::vector<int> free_reqs;
};


class SnaxStreamer : public vp::Component
{
public:
    SnaxStreamer(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static void tcdm_grant(vp::Block *__this, vp::IoReq *req, int id);
    static void tcdm_resp(vp::Block *__this, vp::IoReq *req, int id);
    static void step_handler(vp::Block *__this, vp::ClockEvent *event);
    static void commit_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    bool start(int64_t cycle);
    bool busy_at(int64_t cycle);
    uint32_t counter_at(int64_t cycle);
    void agu_push(Mover &mover);
    bool mover_busy(Mover &mover);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster *tcdm_itf;
    vp::ClockEvent step_event;
    vp::ClockEvent commit_event;

    uint32_t csr_base;          // number of the first CSR, for the trace
    uint32_t addr_mask;         // the AGU's address width, from the TCDM size
    int nb_rw;                  // read-write CSRs, the start CSR last
    std::vector<uint32_t> rw_regs;

    std::vector<Mover> movers;
    std::vector<Channel> channels;

    bool started;               // a start was taken since reset
    int64_t start_cycle;        // s
    int64_t end_cycle;          // e, -1 while not known
    uint32_t counter_before;    // the counter's value up to s + 1
};


SnaxStreamer::SnaxStreamer(vp::ComponentConf &config)
    : vp::Component(config),
      step_event(this, &SnaxStreamer::step_handler),
      commit_event(this, &SnaxStreamer::commit_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    js::Config *cfg = this->get_js_config();
    this->csr_base = cfg->get_child_int("csr_base");
    int addr_bits = cfg->get_child_int("addr_bits");
    this->addr_mask = (uint32_t)((1ULL << addr_bits) - 1);

    int csr = 0;
    int nb_channels = 0;
    for (auto m : cfg->get("movers")->get_elems())
    {
        Mover mover = {};
        mover.is_reader = m->get_child_bool("is_reader");
        for (auto b : m->get("spatial_bounds")->get_elems())
        {
            mover.spatial_bounds.push_back(b->get_int());
        }
        mover.temporal_dim = m->get_child_int("temporal_dim");
        mover.num_channel = m->get_child_int("num_channel");
        mover.fifo_depth = m->get_child_int("fifo_depth");
        mover.csr_first = csr;
        mover.first_channel = nb_channels;
        // Pointer low and high, spatial strides, temporal bounds and strides
        csr += 2 + mover.spatial_bounds.size() + 2 * mover.temporal_dim;
        nb_channels += mover.num_channel;
        this->movers.push_back(mover);
    }
    // The start CSR
    this->nb_rw = csr + 1;
    this->rw_regs.assign(this->nb_rw, 0);

    this->csr_itf.set_req_meth(&SnaxStreamer::csr_req);
    this->new_slave_port("input", &this->csr_itf);

    this->channels.resize(nb_channels);
    this->tcdm_itf = new vp::IoMaster[nb_channels];
    for (Mover &mover : this->movers)
    {
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            int id = mover.first_channel + lane;
            Channel &ch = this->channels[id];
            ch.mover = &mover;
            ch.lane = lane;
            ch.reqs = new vp::IoReq[mover.fifo_depth + 1];
            ch.bufs = new uint64_t[mover.fifo_depth + 1];

            this->tcdm_itf[id].set_grant_meth_muxed(&SnaxStreamer::tcdm_grant, id);
            this->tcdm_itf[id].set_resp_meth_muxed(&SnaxStreamer::tcdm_resp, id);
            this->new_master_port("tcdm_" + std::to_string(id), &this->tcdm_itf[id]);
        }
    }
}


void SnaxStreamer::reset(bool active)
{
    if (active)
    {
        this->rw_regs.assign(this->nb_rw, 0);
        for (Mover &mover : this->movers)
        {
            mover.agu_busy = false;
        }
        for (Channel &ch : this->channels)
        {
            ch.addrs.clear();
            ch.data.clear();
            ch.used = 0;
            ch.held = NULL;
            ch.granted = false;
            ch.free_reqs.clear();
            for (int i = 0; i <= ch.mover->fifo_depth; i++)
            {
                ch.free_reqs.push_back(i);
            }
        }
        this->started = false;
        this->start_cycle = 0;
        this->end_cycle = -1;
        this->counter_before = 0;
    }
}


// Busy from s + 1 to e (cstate in Streamer.scala)
bool SnaxStreamer::busy_at(int64_t cycle)
{
    return this->started && cycle >= this->start_cycle + 1 &&
        (this->end_cycle == -1 || cycle <= this->end_cycle);
}


// Reset at the end of s + 1, then one more at the end of each busy cycle
uint32_t SnaxStreamer::counter_at(int64_t cycle)
{
    if (!this->started || cycle <= this->start_cycle + 1)
    {
        return this->counter_before;
    }
    int64_t last = cycle - 1;
    if (this->end_cycle != -1 && this->end_cycle < last)
    {
        last = this->end_cycle;
    }
    return (uint32_t)(last - this->start_cycle - 1);
}


bool SnaxStreamer::mover_busy(Mover &mover)
{
    if (mover.agu_busy)
    {
        return true;
    }
    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        if (!this->channels[mover.first_channel + lane].addrs.empty())
        {
            return true;
        }
    }
    return false;
}


// The start write is taken in this cycle (s): every mover takes its
// configuration; the AGUs start at s + 1.
bool SnaxStreamer::start(int64_t cycle)
{
    std::vector<Mover> next = this->movers;
    bool any = false;

    for (Mover &mover : next)
    {
        int csr = mover.csr_first;
        // AddressGenUnitCfgIO.connectWithList: the pointer is Cat(high, low),
        // cut to the AGU's address width
        mover.ptr = this->rw_regs[csr] & this->addr_mask;
        csr += 2;
        mover.spatial_strides.assign(this->rw_regs.begin() + csr,
            this->rw_regs.begin() + csr + mover.spatial_bounds.size());
        csr += mover.spatial_bounds.size();
        mover.temporal_bounds.assign(this->rw_regs.begin() + csr,
            this->rw_regs.begin() + csr + mover.temporal_dim);
        csr += mover.temporal_dim;
        mover.temporal_strides.assign(this->rw_regs.begin() + csr,
            this->rw_regs.begin() + csr + mover.temporal_dim);

        // Reader.scala: with temporal stride 0 on loop 0 the AGU runs that loop
        // once and each beat is handed out bound times.
        mover.repeat = 1;
        if (mover.is_reader && mover.temporal_dim > 0 && mover.temporal_strides[0] == 0)
        {
            mover.repeat = mover.temporal_bounds[0];
            mover.temporal_bounds[0] = 1;
        }

        // The AGU starts only if every temporal bound is nonzero
        mover.agu_busy = true;
        for (uint32_t bound : mover.temporal_bounds)
        {
            if (bound == 0)
            {
                mover.agu_busy = false;
            }
        }
        mover.loop_index.assign(mover.temporal_dim, 0);
        mover.loop_offset.assign(mover.temporal_dim, 0);

        if (mover.agu_busy && !mover.is_reader)
        {
            this->trace.force_warning("Writer at CSR %d started: writers are not modelled "
                "yet (SG3 P5)\n", this->csr_base + mover.csr_first);
            return false;
        }
        any |= mover.agu_busy;
    }

    // Channel state (FIFOs, credit, data) is kept, as on the RTL
    for (size_t i = 0; i < next.size(); i++)
    {
        Mover &mover = this->movers[i];
        mover.ptr = next[i].ptr;
        mover.spatial_strides = next[i].spatial_strides;
        mover.temporal_bounds = next[i].temporal_bounds;
        mover.temporal_strides = next[i].temporal_strides;
        mover.repeat = next[i].repeat;
        mover.agu_busy = next[i].agu_busy;
        mover.loop_index = next[i].loop_index;
        mover.loop_offset = next[i].loop_offset;

        this->trace.msg(vp::Trace::LEVEL_DEBUG, "Mover %zu (%s): pointer 0x%x, %s\n", i,
            mover.is_reader ? "reader" : "writer", mover.ptr,
            mover.agu_busy ? "started" : "not started (a temporal bound is 0)");
    }

    this->counter_before = this->counter_at(cycle);
    this->started = true;
    this->start_cycle = cycle;
    this->end_cycle = -1;

    if (any)
    {
        this->step_event.enqueue(1);
    }
    else
    {
        // Busy for s + 1 only
        this->end_cycle = cycle + 1;
    }
    return true;
}


vp::IoReqStatus SnaxStreamer::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();

    uint32_t *data = (uint32_t *)req->get_data();
    bool is_write = req->get_is_write();
    if (req->get_size() != 4 || req->get_addr() % 4 != 0)
    {
        _this->trace.force_warning("Unexpected access (addr: 0x%lx, size: %ld)\n",
            req->get_addr(), req->get_size());
        return vp::IO_REQ_INVALID;
    }
    int index = req->get_addr() / 4;
    uint32_t csr = _this->csr_base + index;

    if (index < _this->nb_rw)
    {
        if (!is_write)
        {
            *data = _this->rw_regs[index];
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x)\n", csr, *data);
            return vp::IO_REQ_OK;
        }

        // ReqRspManager.scala: writing 1 to bit 0 of the last read-write CSR
        // starts the streamer; the write waits while the streamer is busy.
        if (index == _this->nb_rw - 1 && (*data & 1))
        {
            if (_this->busy_at(cycle))
            {
                _this->trace.force_warning("Start (CSR %d) while the streamer is busy; "
                    "holding the write is not modelled\n", csr);
                return vp::IO_REQ_INVALID;
            }
            _this->rw_regs[index] = *data;
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Write CSR %d (value: 0x%x), start\n",
                csr, *data);
            return _this->start(cycle) ? vp::IO_REQ_OK : vp::IO_REQ_INVALID;
        }

        _this->rw_regs[index] = *data;
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Write CSR %d (value: 0x%x)\n", csr, *data);
        return vp::IO_REQ_OK;
    }

    if (index < _this->nb_rw + 2)
    {
        if (is_write)
        {
            _this->trace.force_warning("Write to read-only CSR %d (value: 0x%x)\n", csr, *data);
            return vp::IO_REQ_INVALID;
        }
        *data = index == _this->nb_rw ? _this->busy_at(cycle) : _this->counter_at(cycle);
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x, read-only)\n",
            csr, *data);
        return vp::IO_REQ_OK;
    }

    _this->trace.force_warning("CSR %d is not held by this block (is_write: %d)\n",
        csr, is_write);
    return vp::IO_REQ_INVALID;
}


// 1. Requests: each channel with an address and credit sends it, or sends
// again the one not granted last cycle.
void SnaxStreamer::step_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;

    for (size_t id = 0; id < _this->channels.size(); id++)
    {
        Channel &ch = _this->channels[id];
        if (ch.held == NULL)
        {
            if (ch.addrs.empty() || ch.used >= ch.mover->fifo_depth)
            {
                continue;
            }
            int slot = ch.free_reqs.back();
            ch.free_reqs.pop_back();
            vp::IoReq *req = &ch.reqs[slot];
            req->init();
            req->set_addr(ch.addrs.front());
            req->set_size(8);
            req->set_is_write(false);
            req->set_data((uint8_t *)&ch.bufs[slot]);
            ch.held = req;
        }

        vp::IoReqStatus status = _this->tcdm_itf[id].req(ch.held);
        if (status != vp::IO_REQ_PENDING)
        {
            _this->trace.fatal("TCDM port %zu: unexpected answer %d from the crossbar\n",
                id, status);
            return;
        }
    }

    // After the crossbar's arbitration, queued by the first request above
    _this->commit_event.enqueue(0);
}


void SnaxStreamer::tcdm_grant(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    _this->channels[id].granted = true;
}


void SnaxStreamer::tcdm_resp(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    Channel &ch = _this->channels[id];
    int slot = req - ch.reqs;
    ch.data.push_back(ch.bufs[slot]);
    ch.free_reqs.push_back(slot);
}


// The AGU's next group of addresses, one per channel, then its loops advance
void SnaxStreamer::agu_push(Mover &mover)
{
    uint32_t temporal = 0;
    for (uint32_t offset : mover.loop_offset)
    {
        temporal += offset;
    }

    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        // AddressGenUnit.scala: the channel index split over the spatial bounds
        uint32_t spatial = 0;
        uint32_t remainder = lane;
        for (size_t j = 0; j < mover.spatial_bounds.size(); j++)
        {
            spatial += mover.spatial_strides[j] * (remainder % mover.spatial_bounds[j]);
            remainder /= mover.spatial_bounds[j];
        }
        uint32_t addr = (mover.ptr + temporal + spatial) & this->addr_mask;
        this->channels[mover.first_channel + lane].addrs.push_back(addr);
    }

    // The loops: loop 0 ticks on every group, loop d when loop d - 1 wraps.
    // ProgrammableCounter's step is one bit narrower than the address.
    bool tick = true;
    bool all_last = true;
    for (int d = 0; d < mover.temporal_dim; d++)
    {
        bool last = mover.loop_index[d] == mover.temporal_bounds[d] - 1;
        all_last &= last;
        if (tick)
        {
            if (last)
            {
                mover.loop_index[d] = 0;
                mover.loop_offset[d] = 0;
            }
            else
            {
                mover.loop_index[d]++;
                mover.loop_offset[d] = (mover.loop_offset[d]
                    + (mover.temporal_strides[d] & (this->addr_mask >> 1))) & this->addr_mask;
            }
        }
        tick = tick && last;
    }

    if (all_last)
    {
        mover.agu_busy = false;
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "AGU of mover at CSR %d done\n",
            this->csr_base + mover.csr_first);
    }
}


// 3. Commit: grants leave their FIFO, the AGUs push, and the streamer ends
// or goes on to the next cycle.
void SnaxStreamer::commit_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();

    for (Channel &ch : _this->channels)
    {
        if (ch.granted)
        {
            ch.addrs.pop_front();
            ch.used++;
            ch.held = NULL;
            ch.granted = false;
        }
    }

    for (Mover &mover : _this->movers)
    {
        if (!mover.agu_busy)
        {
            continue;
        }
        // Room in every FIFO, counting this cycle's grants (the pipe queue)
        bool room = true;
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            Channel &ch = _this->channels[mover.first_channel + lane];
            room &= (int)ch.addrs.size() < mover.fifo_depth;
        }
        if (room)
        {
            _this->agu_push(mover);
        }
    }

    // The movers as they stand at the start of the next cycle
    bool busy = false;
    for (Mover &mover : _this->movers)
    {
        busy |= _this->mover_busy(mover);
    }
    if (!busy)
    {
        // Every mover is done in cycle + 1: the streamer is busy up to then
        _this->end_cycle = cycle + 1;
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Done: busy up to cycle %ld, counter %d\n",
            _this->end_cycle, _this->counter_at(_this->end_cycle + 1));
        return;
    }

    // Something can still move: a request with credit, or an AGU with room.
    // A streamer waiting only for credit sleeps (the beats out come in P5).
    bool progress = false;
    for (Channel &ch : _this->channels)
    {
        progress |= !ch.addrs.empty() && ch.used < ch.mover->fifo_depth;
    }
    for (Mover &mover : _this->movers)
    {
        if (mover.agu_busy)
        {
            bool room = true;
            for (int lane = 0; lane < mover.num_channel; lane++)
            {
                room &= (int)_this->channels[mover.first_channel + lane].addrs.size()
                    < mover.fifo_depth;
            }
            progress |= room;
        }
    }
    if (progress)
    {
        _this->step_event.enqueue(1);
    }
    else
    {
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Stalled: no credit and no room\n");
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxStreamer(config);
}
