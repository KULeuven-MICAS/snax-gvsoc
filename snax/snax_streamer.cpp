/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// A SNAX streamer as snax_cluster's Chisel streamer builds it
// (hw/chisel/.../streamer/Streamer.scala, readerWriter/, reqRspManager/):
// data movers (readers, then writers), each with an address generator (AGU)
// and one 64-bit TCDM port per channel, configured through CSRs and started
// together. A reader hands its beats to the accelerator, a writer takes them.
//
// CSRs, offsets from the streamer's first CSR (the CSR mux removes it):
//   per mover: pointer low and high, one spatial stride per spatial bound,
//   the temporal bounds, the temporal strides; then the start CSR, all
//   read-write; then busy and the performance counter, read-only.
//
// Timing, per cycle t while busy (s is the cycle the start write is taken):
//   0. the accelerator takes reader beats and gives writer beats (its own
//      event, which runs before the streamer's in a cycle);
//   1. requests: a reader channel requests when its address FIFO has an
//      address and it has credit (reads in flight plus beats buffered below
//      fifo_depth); a writer channel when an address and its lane's data are
//      there. A request not granted is sent again the next cycle.
//   2. the TCDM crossbar arbitrates (its own event, same cycle).
//   3. commit: granted addresses (and a writer's data) leave their FIFOs; the
//      AGU pushes one group of addresses when every channel's FIFO has room,
//      a grant in this cycle making room (the pipe queue); it starts at s + 1,
//      so the first request is at s + 2.
// Read data comes back one cycle after the grant and can leave its lane's
// queue the cycle after that; a beat leaves when every lane holds data, and a
// pop returns the lane's credit in that cycle. A beat given to a writer can be
// written the next cycle; it is taken when no lane's queue is full.
//
// A mover is busy while its AGU is busy or an address waits; the streamer is
// busy from s + 1 to the cycle after its last mover is done (e). The counter
// is reset at s + 1 and counts the busy cycles after it, so its final value
// is e - s - 1. Busy and the counter are computed from these cycles when they
// are read. A streamer that can do nothing (no credit, no data, no room)
// sleeps until a beat moves.
//
// Beat ports: reader_<i> and writer_<j>, io slaves of num_channel * 8 bytes,
// lane 0 first. A request of size 0 is a probe: IO_REQ_OK if a beat could
// move now, IO_REQ_DENIED if not, and nothing moves. A full-size request moves
// the beat (IO_REQ_OK) or is refused (IO_REQ_DENIED, no grant follows: the
// accelerator tries again in a later cycle).
//
// Priority (DataRequestor.scala, ComplexQueue.scala): each TCDM request
// carries a bit for the sparse interconnect, on the wire tcdm_prio_<i> set
// just before the request is sent (and resent). With dynamic priority it is
// the lane's queue hint, reader count <= 1, writer count >= fifo_depth - 1;
// the RTL holds the hint in a register reloaded in every cycle without a
// request or in which the request fires, so a request first sent in cycle t
// carries the hint of the queue count during t - 1, and keeps it while it is
// resent. Without dynamic priority the bit is higherStaticPriority. The count
// during a cycle is the RTL queue's: the words visible by then and not popped
// before it.
//
// Per mover, the cycles of each run are classed as SNAX-MODEL classed them:
// busy (a channel granted) > stall_xbar (requested, none granted) >
// stall_fifo (an address, but no credit or no data) > idle; the trace gives
// them with the highest queue count per lane when the streamer is done.
//
// A lane's queue count in a cycle is the RTL queue's, the one the priority
// hint reads: the words visible by then and not popped before it, so the
// words in the queue at the end of the cycle before. A push and a pop in one
// cycle (a writer's, the unit first) leave it as it was. The run's highest
// count per lane is qmax; with the stalls trace on, a fifo line gives each
// count from the first cycle it holds, written once that cycle's changes are
// known (the next change, or the streamer's end).
//
// Beats (docs/EVENTS.md): a reader's beats are numbered b in its AGU's order
// from 0 in each run, a writer's in the order the unit hands them over. Each
// TCDM request carries its beat's b (SNAX_ARG_ID, snax_events.hpp) for the
// crossbar's lines; a reader's words keep it, and the beat handed to the
// unit carries it back (a beat with a repeat, every time it is handed out).
//
// Events (docs/EVENTS.md, snax_events.hpp), per mover: `start` in the cycle
// the start is taken; `done` in its last busy cycle (the commit in which its
// last address leaves, or the streamer's end for a mover that never started);
// the summary's `mover` line with the run's classes and queue maxima when the
// streamer is done.
//
// Not modelled: reader-writers, configurable channels and byte masks, address
// remapping (logic word sizes), datapath extensions, a second clock domain;
// snax_streamer.py refuses their keys.

#include <deque>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include "snax_csr_block.hpp"
#include "snax_events.hpp"


// A beat word in a lane's queue, and the first cycle it can leave
struct Word
{
    int64_t visible;
    uint64_t value;
    int64_t b;                  // its beat
};

// A word popped from a lane's queue: when it became visible, when it left
struct PoppedWord
{
    int64_t visible;
    int64_t popped;
};

enum CycleClass { BUSY, STALL_XBAR, STALL_FIFO, IDLE, NB_CLASSES };
static const char *class_names[NB_CLASSES] = {"busy", "stall_xbar", "stall_fifo", "idle"};

// A data mover: a reader or a writer, its configuration and its AGU
struct Mover
{
    std::string name;           // reader<i> or writer<j>
    bool is_reader;
    std::vector<uint32_t> spatial_bounds;
    int temporal_dim;
    int num_channel;
    int fifo_depth;
    bool dynamic_priority;      // the priority bit from the queue count
    bool higher_static_priority;  // else this bit
    int csr_first;              // offset of its first CSR
    int first_channel;          // index of its first channel in the streamer

    // Configuration, taken at start
    uint32_t ptr;
    std::vector<uint32_t> spatial_strides;
    std::vector<uint32_t> temporal_bounds;
    std::vector<uint32_t> temporal_strides;
    uint32_t repeat;            // a reader's beat repeat (temporal stride 0 on loop 0)
    uint32_t handed;            // times the head beat was handed out
    int64_t beats;              // beats numbered in this run: the next one's b

    // AGU
    bool agu_busy;
    std::vector<uint32_t> loop_index;    // per temporal loop, 0 to bound - 1
    std::vector<uint32_t> loop_offset;   // per temporal loop, index * stride

    // Cycle classes of the current run, and the class of the cycles it sleeps
    int64_t classes[NB_CLASSES];
    CycleClass gap_class;
    bool done;                  // its done line is written for this run
};

// One channel: one 64-bit TCDM port
struct Channel
{
    Mover *mover;
    int lane;                   // index within its mover

    std::deque<uint32_t> addrs; // address FIFO, fifo_depth deep
    std::deque<int64_t> addr_beats;  // a reader's: each address's beat
    int used;                   // reader: reads in flight plus words buffered
    vp::IoReq *held;            // request sent and not granted yet
    bool requested;             // sent a request in this cycle
    bool granted;               // granted in this cycle
    std::deque<Word> data;      // the lane's queue, fifo_depth deep
    std::deque<PoppedWord> popped;  // words popped in the last two cycles
    int max_count;              // highest count of the lane's queue in this run
    int count;                  // the queue's count, as last written
    int64_t count_cycle;        // the last cycle its words changed, -1 if none
    int count_end;              // the words in it after that cycle's changes
    bool priority;              // the priority bit of the request sent

    // Requests in flight, at most fifo_depth, plus the one being sent
    std::vector<vp::IoReq> reqs;
    std::vector<uint64_t> bufs;
    std::vector<int> free_reqs;
};


class SnaxStreamer : public vp::Component
{
public:
    SnaxStreamer(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static vp::IoReqStatus reader_req(vp::Block *__this, vp::IoReq *req, int id);
    static vp::IoReqStatus writer_req(vp::Block *__this, vp::IoReq *req, int id);
    static void tcdm_grant(vp::Block *__this, vp::IoReq *req, int id);
    static void tcdm_resp(vp::Block *__this, vp::IoReq *req, int id);
    static void step_handler(vp::Block *__this, vp::ClockEvent *event);
    static void commit_handler(vp::Block *__this, vp::ClockEvent *event);
    static void summary_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    void start(int64_t cycle);
    bool busy_at(int64_t cycle);
    uint32_t counter_at(int64_t cycle);
    void agu_push(Mover &mover);
    Channel &channel(Mover &mover, int lane);
    bool agu_has_room(Mover &mover);
    bool has_addresses(Mover &mover);
    bool mover_busy(Mover &mover);
    bool can_request(Channel &ch, int64_t cycle);
    void wake(int64_t delay);
    void queue_changed(Channel &ch);
    void count_flush(Channel &ch);
    void tag(vp::IoReq *req, int64_t b);
    void pop_word(Channel &ch, int64_t cycle);
    bool priority_hint(Channel &ch, int64_t cycle);
    void end_run(int64_t cycle);
    void mover_done(Mover &mover, int64_t cycle);

    vp::Trace trace;
    SnaxEvents ev;
    vp::IoSlave csr_itf;
    std::vector<vp::IoMaster> tcdm_itf;
    std::vector<vp::WireMaster<bool>> tcdm_prio_itf;
    std::vector<vp::IoSlave> reader_itf;
    std::vector<vp::IoSlave> writer_itf;
    vp::ClockEvent step_event;
    vp::ClockEvent commit_event;
    vp::ClockEvent summary_event;

    uint32_t addr_mask;         // the AGU's address width, from the TCDM size
    int nb_rw;                  // read-write CSRs, the start CSR last
    SnaxCsrBlock csrs;          // then busy and the counter, read-only

    std::vector<Mover> movers;
    std::vector<Channel> channels;
    std::vector<Mover *> readers;
    std::vector<Mover *> writers;

    bool started;               // a start was taken since reset
    int64_t start_cycle;        // s
    int64_t end_cycle;          // e, -1 while not known
    uint32_t counter_before;    // the counter's value up to s + 1
    int64_t stepped_cycle;      // the last cycle the requests were sent
    int64_t classed_cycle;      // the last cycle classed
    int runs;                   // starts taken, the current run's index + 1
};


SnaxStreamer::SnaxStreamer(vp::ComponentConf &config)
    : vp::Component(config),
      step_event(this, &SnaxStreamer::step_handler),
      commit_event(this, &SnaxStreamer::commit_handler),
      summary_event(this, &SnaxStreamer::summary_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->ev.declare(this);

    js::Config *cfg = this->get_js_config();
    int addr_bits = cfg->get_child_int("addr_bits");
    this->addr_mask = (uint32_t)((1ULL << addr_bits) - 1);

    int csr = 0;
    int nb_channels = 0;
    for (auto m : cfg->get("movers")->get_elems())
    {
        Mover mover = {};
        mover.name = m->get_child_str("name");
        mover.is_reader = m->get_child_bool("is_reader");
        for (auto b : m->get("spatial_bounds")->get_elems())
        {
            mover.spatial_bounds.push_back(b->get_int());
        }
        mover.temporal_dim = m->get_child_int("temporal_dim");
        mover.num_channel = m->get_child_int("num_channel");
        mover.fifo_depth = m->get_child_int("fifo_depth");
        mover.dynamic_priority = m->get_child_bool("dynamic_priority");
        mover.higher_static_priority = m->get_child_bool("higher_static_priority");
        mover.csr_first = csr;
        mover.first_channel = nb_channels;
        // Pointer low and high, spatial strides, temporal bounds and strides
        csr += 2 + mover.spatial_bounds.size() + 2 * mover.temporal_dim;
        nb_channels += mover.num_channel;
        this->movers.push_back(mover);
    }
    // The start CSR
    this->nb_rw = csr + 1;
    this->csrs.configure(&this->trace, cfg->get_child_int("csr_base"), this->nb_rw, 2);

    this->csr_itf.set_req_meth(&SnaxStreamer::csr_req);
    this->new_slave_port("input", &this->csr_itf);

    // From here the movers do not move in memory: channels point to them
    for (Mover &mover : this->movers)
    {
        (mover.is_reader ? this->readers : this->writers).push_back(&mover);
    }

    // Sized once, before any port is registered: never resized after
    this->channels.resize(nb_channels);
    this->tcdm_itf.resize(nb_channels);
    this->tcdm_prio_itf.resize(nb_channels);
    this->reader_itf.resize(this->readers.size());
    this->writer_itf.resize(this->writers.size());
    for (Mover &mover : this->movers)
    {
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            int id = mover.first_channel + lane;
            Channel &ch = this->channels[id];
            ch.mover = &mover;
            ch.lane = lane;
            ch.reqs.resize(mover.fifo_depth + 1);
            ch.bufs.resize(mover.fifo_depth + 1);

            this->tcdm_itf[id].set_grant_meth_muxed(&SnaxStreamer::tcdm_grant, id);
            this->tcdm_itf[id].set_resp_meth_muxed(&SnaxStreamer::tcdm_resp, id);
            this->new_master_port("tcdm_" + std::to_string(id), &this->tcdm_itf[id]);
            this->new_master_port("tcdm_prio_" + std::to_string(id), &this->tcdm_prio_itf[id]);
        }
    }

    for (size_t i = 0; i < this->readers.size(); i++)
    {
        this->reader_itf[i].set_req_meth_muxed(&SnaxStreamer::reader_req, i);
        this->new_slave_port("reader_" + std::to_string(i), &this->reader_itf[i]);
    }
    for (size_t i = 0; i < this->writers.size(); i++)
    {
        this->writer_itf[i].set_req_meth_muxed(&SnaxStreamer::writer_req, i);
        this->new_slave_port("writer_" + std::to_string(i), &this->writer_itf[i]);
    }
}


void SnaxStreamer::reset(bool active)
{
    if (active)
    {
        this->csrs.reset();
        for (Mover &mover : this->movers)
        {
            mover.agu_busy = false;
            mover.handed = 0;
        }
        for (Channel &ch : this->channels)
        {
            ch.addrs.clear();
            ch.addr_beats.clear();
            ch.data.clear();
            ch.popped.clear();
            ch.priority = false;
            ch.used = 0;
            ch.held = NULL;
            ch.requested = false;
            ch.granted = false;
            ch.max_count = 0;
            ch.count = 0;
            ch.count_cycle = -1;
            ch.count_end = 0;
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
        this->stepped_cycle = -1;
        this->classed_cycle = -1;
        this->runs = 0;
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


Channel &SnaxStreamer::channel(Mover &mover, int lane)
{
    return this->channels[mover.first_channel + lane];
}


// Room for the AGU's next group: every lane's address FIFO below fifo_depth
bool SnaxStreamer::agu_has_room(Mover &mover)
{
    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        if ((int)this->channel(mover, lane).addrs.size() >= mover.fifo_depth)
        {
            return false;
        }
    }
    return true;
}


// An address waits in some lane
bool SnaxStreamer::has_addresses(Mover &mover)
{
    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        if (!this->channel(mover, lane).addrs.empty())
        {
            return true;
        }
    }
    return false;
}


bool SnaxStreamer::mover_busy(Mover &mover)
{
    return mover.agu_busy || this->has_addresses(mover);
}


// A reader needs credit, a writer its lane's data, visible in this cycle
bool SnaxStreamer::can_request(Channel &ch, int64_t cycle)
{
    if (ch.addrs.empty())
    {
        return false;
    }
    if (ch.mover->is_reader)
    {
        return ch.used < ch.mover->fifo_depth;
    }
    return !ch.data.empty() && ch.data.front().visible <= cycle;
}


// The streamer's next step: in this cycle (a pop returned credit) or the next
void SnaxStreamer::wake(int64_t delay)
{
    if (this->end_cycle != -1 || !this->started)
    {
        return;
    }
    int64_t cycle = this->clock.get_cycles();
    if (delay == 0 && this->stepped_cycle == cycle)
    {
        delay = 1;
    }
    // Keeps an earlier step already queued
    this->step_event.enqueue(delay);
}


// A word pushed into or popped from the lane's queue in this cycle: the count
// of the cycle after the last change is known once this cycle has a change
void SnaxStreamer::queue_changed(Channel &ch)
{
    int64_t cycle = this->clock.get_cycles();
    this->trace.msg(vp::Trace::LEVEL_TRACE, "Queue %s.lane%d: %ld\n", ch.mover->name.c_str(),
        ch.lane, (long)ch.data.size());
    if (cycle != ch.count_cycle)
    {
        this->count_flush(ch);
        ch.count_cycle = cycle;
    }
    ch.count_end = ch.data.size();
}


// The count from the cycle after the last change: the words left by then
void SnaxStreamer::count_flush(Channel &ch)
{
    if (ch.count_cycle < 0 || ch.count_end == ch.count)
    {
        return;
    }
    ch.count = ch.count_end;
    if (ch.count > ch.max_count)
    {
        ch.max_count = ch.count;
    }
    if (this->ev.stalls.get_active())
    {
        this->ev.stalls.msg(vp::Trace::LEVEL_INFO, "%ld fifo mover=%s lane=%d count=%d\n",
            (long)(ch.count_cycle + 1), ch.mover->name.c_str(), ch.lane, ch.count);
    }
}


// A request's beat, for the crossbar's lines
void SnaxStreamer::tag(vp::IoReq *req, int64_t b)
{
    snax_arg_set(req, SNAX_ARG_TAG, SNAX_TAG_BEAT);
    snax_arg_set(req, SNAX_ARG_ID, (uint64_t)b);
}


// The lane's head word leaves its queue in cycle
void SnaxStreamer::pop_word(Channel &ch, int64_t cycle)
{
    // Only pops from the cycle before on still count (priority_hint)
    while (!ch.popped.empty() && ch.popped.front().popped < cycle - 1)
    {
        ch.popped.pop_front();
    }
    ch.popped.push_back({ch.data.front().visible, cycle});
    ch.data.pop_front();
}


// The queue hint of the RTL in cycle: from the count during it, the words
// visible by then and not popped before it
bool SnaxStreamer::priority_hint(Channel &ch, int64_t cycle)
{
    int count = 0;
    for (const Word &word : ch.data)
    {
        count += word.visible <= cycle;
    }
    for (const PoppedWord &word : ch.popped)
    {
        count += word.visible <= cycle && word.popped >= cycle;
    }
    return ch.mover->is_reader ? count <= 1 : count >= ch.mover->fifo_depth - 1;
}


// The start write is taken in this cycle (s): every mover takes its
// configuration; the AGUs start at s + 1. Channel state (FIFOs, credit, data)
// is kept, as on the RTL.
void SnaxStreamer::start(int64_t cycle)
{
    std::vector<uint32_t> &regs = this->csrs.regs;
    bool any = false;

    for (Mover &mover : this->movers)
    {
        int csr = mover.csr_first;
        // AddressGenUnitCfgIO.connectWithList: the pointer is Cat(high, low),
        // cut to the AGU's address width
        mover.ptr = regs[csr] & this->addr_mask;
        csr += 2;
        mover.spatial_strides.assign(regs.begin() + csr,
            regs.begin() + csr + mover.spatial_bounds.size());
        csr += mover.spatial_bounds.size();
        mover.temporal_bounds.assign(regs.begin() + csr,
            regs.begin() + csr + mover.temporal_dim);
        csr += mover.temporal_dim;
        mover.temporal_strides.assign(regs.begin() + csr,
            regs.begin() + csr + mover.temporal_dim);

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
        any |= mover.agu_busy;

        // The hand-out counter restarts with the run (HandShakeRepeater's reset)
        mover.handed = 0;
        mover.beats = 0;
        for (int c = 0; c < NB_CLASSES; c++)
        {
            mover.classes[c] = 0;
        }
        mover.gap_class = IDLE;

        this->trace.msg(vp::Trace::LEVEL_DEBUG, "Mover %s: pointer 0x%x, %s\n",
            mover.name.c_str(), mover.ptr,
            mover.agu_busy ? "started" : "not started (a temporal bound is 0)");
        mover.done = false;
        this->ev.events.msg(vp::Trace::LEVEL_INFO, "%ld start mover=%s\n", (long)cycle,
            mover.name.c_str());
    }
    for (Channel &ch : this->channels)
    {
        if (ch.count_cycle < cycle)
        {
            this->count_flush(ch);
        }
        ch.max_count = ch.count;
    }

    this->counter_before = this->counter_at(cycle);
    this->runs++;
    this->started = true;
    this->start_cycle = cycle;
    this->end_cycle = -1;
    // Cycles are classed from s + 1
    this->classed_cycle = cycle;

    if (any)
    {
        this->step_event.enqueue(1);
    }
    else
    {
        // Busy for s + 1 only
        this->end_run(cycle);
    }
}


// Every mover is done in cycle + 1: the streamer is busy up to then, a cycle
// classed idle. The summary is written in that cycle, after the read data
// that comes back in it.
void SnaxStreamer::end_run(int64_t cycle)
{
    for (Mover &mover : this->movers)
    {
        this->mover_done(mover, cycle);
    }
    this->end_cycle = cycle + 1;
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Done: busy up to cycle %ld, counter %d\n",
        this->end_cycle, this->counter_at(this->end_cycle + 1));
    for (Mover &mover : this->movers)
    {
        mover.classes[IDLE] += this->end_cycle - this->classed_cycle;
    }
    this->classed_cycle = this->end_cycle;
    this->summary_event.enqueue(1);
}


// The mover's done line, once per run: cycle is its last busy cycle
void SnaxStreamer::mover_done(Mover &mover, int64_t cycle)
{
    if (!mover.done)
    {
        mover.done = true;
        this->ev.events.msg(vp::Trace::LEVEL_INFO, "%ld done mover=%s\n", (long)cycle,
            mover.name.c_str());
    }
}


// Per mover, the run's cycle classes and the highest count of each lane's
// queue over the busy window
void SnaxStreamer::summary_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();
    for (Mover &mover : _this->movers)
    {
        std::string counts, qmax;
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            _this->count_flush(_this->channel(mover, lane));
        }
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            std::string count = std::to_string(_this->channel(mover, lane).max_count);
            counts += " " + count;
            qmax += (lane > 0 ? "," : "") + count;
        }
        _this->trace.msg(vp::Trace::LEVEL_DEBUG,
            "Mover %s: busy %ld, stall_xbar %ld, stall_fifo %ld, idle %ld; queue max%s\n",
            mover.name.c_str(), mover.classes[BUSY], mover.classes[STALL_XBAR],
            mover.classes[STALL_FIFO], mover.classes[IDLE], counts.c_str());
        _this->ev.summary.msg(vp::Trace::LEVEL_INFO,
            "%ld mover mover=%s run=%d busy=%ld stall_xbar=%ld stall_fifo=%ld idle=%ld "
            "qmax=%s\n", (long)cycle, mover.name.c_str(), _this->runs - 1,
            (long)mover.classes[BUSY], (long)mover.classes[STALL_XBAR],
            (long)mover.classes[STALL_FIFO], (long)mover.classes[IDLE], qmax.c_str());
    }
}


vp::IoReqStatus SnaxStreamer::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();

    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [&](int ro) -> uint32_t {
        return ro == 0 ? _this->busy_at(cycle) : _this->counter_at(cycle);
    });
    if (index < 0)
    {
        return status;
    }

    // ReqRspManager.scala: writing 1 to bit 0 of the last read-write CSR
    // starts the streamer; the write waits while the streamer is busy.
    uint32_t value = *(uint32_t *)req->get_data();
    if (index != _this->nb_rw - 1 || !(value & 1))
    {
        _this->csrs.write(index, value);
        return vp::IO_REQ_OK;
    }
    if (_this->busy_at(cycle))
    {
        _this->trace.force_warning("Start (CSR %d) while the streamer is busy; "
            "holding the write is not modelled\n", _this->csrs.csr(index));
        return vp::IO_REQ_INVALID;
    }
    _this->csrs.write(index, value, ", start");
    _this->start(cycle);
    return vp::IO_REQ_OK;
}


// The accelerator takes a reader's beat: every lane's head word, when all are
// visible. With a repeat, the beat leaves after its last hand-out.
vp::IoReqStatus SnaxStreamer::reader_req(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();
    Mover &mover = *_this->readers[id];

    uint64_t size = req->get_size();
    if (req->get_is_write() || (size != 0 && size != (uint64_t)mover.num_channel * 8))
    {
        _this->trace.force_warning("Unexpected access on reader_%d (size: %ld, is_write: %d)\n",
            id, size, req->get_is_write());
        return vp::IO_REQ_INVALID;
    }

    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        Channel &ch = _this->channel(mover, lane);
        if (ch.data.empty() || ch.data.front().visible > cycle)
        {
            return vp::IO_REQ_DENIED;
        }
    }
    if (size == 0)
    {
        return vp::IO_REQ_OK;
    }

    uint64_t *beat = (uint64_t *)req->get_data();
    int64_t b = _this->channel(mover, 0).data.front().b;
    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        const Word &word = _this->channel(mover, lane).data.front();
        if (word.b != b)
        {
            _this->trace.fatal("reader_%d: lane %d's head word is of beat %ld, lane 0's of %ld\n",
                id, lane, (long)word.b, (long)b);
        }
        beat[lane] = word.value;
    }
    _this->tag(req, b);

    mover.handed++;
    if (mover.handed >= mover.repeat)
    {
        mover.handed = 0;
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            Channel &ch = _this->channel(mover, lane);
            _this->pop_word(ch, cycle);
            ch.used--;
            _this->queue_changed(ch);
        }
        // The credit is back in this cycle
        _this->wake(0);
    }
    return vp::IO_REQ_OK;
}


// The accelerator gives a writer a beat: taken when no lane's queue is full,
// written from the next cycle.
vp::IoReqStatus SnaxStreamer::writer_req(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();
    Mover &mover = *_this->writers[id];

    uint64_t size = req->get_size();
    if (!req->get_is_write() || (size != 0 && size != (uint64_t)mover.num_channel * 8))
    {
        _this->trace.force_warning("Unexpected access on writer_%d (size: %ld, is_write: %d)\n",
            id, size, req->get_is_write());
        return vp::IO_REQ_INVALID;
    }

    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        if ((int)_this->channel(mover, lane).data.size() >= mover.fifo_depth)
        {
            return vp::IO_REQ_DENIED;
        }
    }
    if (size == 0)
    {
        return vp::IO_REQ_OK;
    }

    uint64_t *beat = (uint64_t *)req->get_data();
    int64_t b = mover.beats++;
    for (int lane = 0; lane < mover.num_channel; lane++)
    {
        Channel &ch = _this->channel(mover, lane);
        ch.data.push_back({cycle + 1, beat[lane], b});
        _this->queue_changed(ch);
    }
    _this->wake(1);
    return vp::IO_REQ_OK;
}


// 1. Requests: each channel that can sends its address, or sends again the
// one not granted last cycle.
void SnaxStreamer::step_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (_this->stepped_cycle == cycle || _this->end_cycle != -1)
    {
        return;
    }
    _this->stepped_cycle = cycle;

    for (size_t id = 0; id < _this->channels.size(); id++)
    {
        Channel &ch = _this->channels[id];
        if (ch.held == NULL)
        {
            if (!_this->can_request(ch, cycle))
            {
                continue;
            }
            int slot = ch.free_reqs.back();
            ch.free_reqs.pop_back();
            vp::IoReq *req = &ch.reqs[slot];
            req->init();
            req->set_addr(ch.addrs.front());
            req->set_size(8);
            req->set_is_write(!ch.mover->is_reader);
            if (!ch.mover->is_reader)
            {
                ch.bufs[slot] = ch.data.front().value;
            }
            _this->tag(req, ch.mover->is_reader ? ch.addr_beats.front() : ch.data.front().b);
            req->set_data((uint8_t *)&ch.bufs[slot]);
            ch.held = req;
            ch.priority = ch.mover->dynamic_priority ? _this->priority_hint(ch, cycle - 1)
                : ch.mover->higher_static_priority;
        }

        ch.requested = true;
        if (_this->tcdm_prio_itf[id].is_bound())
        {
            _this->tcdm_prio_itf[id].sync(ch.priority);
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


// A read's data, one cycle after its grant: into the lane's queue, which
// hands it out from the next cycle (Queue in DataResponser). A write's
// response only frees its request.
void SnaxStreamer::tcdm_resp(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    Channel &ch = _this->channels[id];
    int slot = req - ch.reqs.data();
    if (ch.mover->is_reader)
    {
        ch.data.push_back({_this->clock.get_cycles() + 1, ch.bufs[slot],
            (int64_t)snax_arg_get(req, SNAX_ARG_ID)});
        _this->queue_changed(ch);
    }
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
        this->channel(mover, lane).addrs.push_back(addr);
        this->channel(mover, lane).addr_beats.push_back(mover.beats);
    }
    if (mover.is_reader)
    {
        mover.beats++;
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
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "AGU of %s done\n", mover.name.c_str());
    }
}


// 3. Commit: the cycle is classed, grants leave their FIFOs, the AGUs push,
// and the streamer ends, goes on to the next cycle or sleeps.
void SnaxStreamer::commit_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxStreamer *_this = (SnaxStreamer *)__this;
    int64_t cycle = _this->clock.get_cycles();

    for (Mover &mover : _this->movers)
    {
        // The cycles slept through keep the class the mover had when it slept
        mover.classes[mover.gap_class] += cycle - _this->classed_cycle - 1;

        bool granted = false, requested = false;
        for (int lane = 0; lane < mover.num_channel; lane++)
        {
            Channel &ch = _this->channel(mover, lane);
            granted |= ch.granted;
            requested |= ch.requested;
        }
        mover.classes[granted ? BUSY : requested ? STALL_XBAR :
            _this->has_addresses(mover) ? STALL_FIFO : IDLE]++;
    }
    _this->classed_cycle = cycle;

    for (Channel &ch : _this->channels)
    {
        if (ch.granted)
        {
            ch.addrs.pop_front();
            ch.addr_beats.pop_front();
            if (ch.mover->is_reader)
            {
                ch.used++;
            }
            else
            {
                _this->pop_word(ch, cycle);
                _this->queue_changed(ch);
            }
            ch.held = NULL;
        }
        ch.granted = false;
        ch.requested = false;
    }

    for (Mover &mover : _this->movers)
    {
        // Room in every FIFO, counting this cycle's grants (the pipe queue)
        if (mover.agu_busy && _this->agu_has_room(mover))
        {
            _this->agu_push(mover);
        }
        if (!_this->mover_busy(mover))
        {
            _this->mover_done(mover, cycle);
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
        _this->end_run(cycle);
        return;
    }

    // Something can still move next cycle: a request, or an AGU with room.
    // Otherwise the streamer sleeps until a beat moves (wake()).
    bool progress = false;
    for (Channel &ch : _this->channels)
    {
        progress |= _this->can_request(ch, cycle + 1);
    }
    for (Mover &mover : _this->movers)
    {
        progress |= mover.agu_busy && _this->agu_has_room(mover);
        mover.gap_class = _this->has_addresses(mover) ? STALL_FIFO : IDLE;
    }
    if (progress)
    {
        _this->step_event.enqueue(1);
    }
    else
    {
        _this->trace.msg(vp::Trace::LEVEL_TRACE, "Waiting for a beat to move\n");
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxStreamer(config);
}
