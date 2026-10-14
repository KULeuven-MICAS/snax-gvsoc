/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// A test datapath in the ALU's place (SG3), to drive the streamer's beats
// before the ALU is modelled (SG4). It is not the ALU: it copies a beat.
//
// CSRs, offsets from its first CSR (the CSR mux removes it), the ALU's
// layout (snax-alu-lib.h): 0 mode, 1 length, 2 start (read-write); 3 busy,
// 4 counter (read-only).
//   mode bit 0: the beat it copies, 0 from in_a, 1 from in_b
//   mode bits 7:4: k - 1, one firing at most every k cycles
//   length: firings per run
//   start: writing 1 to bit 0 starts a run (refused while busy)
// Busy runs from the cycle after the start write to the cycle of the last
// firing; the counter counts those cycles.
//
// A firing takes one beat from in_a and one from in_b and gives the chosen one
// to out, all in one cycle, as the ALU takes both inputs together and only
// when its output can go. Each cycle it runs before the streamer's step, so a
// beat it takes returns its reader's credit in time for that cycle's requests.
// It asks with a size-0 probe first (snax_streamer.cpp), so nothing moves
// unless all three can.

#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>


class SnaxTestDatapath : public vp::Component
{
public:
    SnaxTestDatapath(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static void fire_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    bool busy_at(int64_t cycle);
    uint32_t counter_at(int64_t cycle);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint8_t *beat);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster in_a;
    vp::IoMaster in_b;
    vp::IoMaster out;
    vp::ClockEvent fire_event;
    vp::IoReq beat_req;

    uint32_t csr_base;          // number of the first CSR, for the trace
    int beat_bytes;             // bytes per beat, 8 per lane
    uint32_t regs[3];           // mode, length, start

    bool started;
    int64_t start_cycle;        // s
    int64_t end_cycle;          // the last busy cycle, -1 while not known
    uint32_t counter_before;    // the counter's value up to s
    int64_t next_cycle;         // first cycle the next firing may happen
    uint32_t fired;             // firings in this run
    std::vector<uint8_t> beat_a, beat_b;
};


SnaxTestDatapath::SnaxTestDatapath(vp::ComponentConf &config)
    : vp::Component(config),
      fire_event(this, &SnaxTestDatapath::fire_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    this->csr_base = this->get_js_config()->get_child_int("csr_base");
    this->beat_bytes = this->get_js_config()->get_child_int("beat_bytes");
    this->beat_a.resize(this->beat_bytes);
    this->beat_b.resize(this->beat_bytes);

    this->csr_itf.set_req_meth(&SnaxTestDatapath::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->new_master_port("in_a", &this->in_a);
    this->new_master_port("in_b", &this->in_b);
    this->new_master_port("out", &this->out);
}


void SnaxTestDatapath::reset(bool active)
{
    if (active)
    {
        this->regs[0] = this->regs[1] = this->regs[2] = 0;
        this->started = false;
        this->start_cycle = 0;
        this->end_cycle = -1;
        this->counter_before = 0;
    }
}


bool SnaxTestDatapath::busy_at(int64_t cycle)
{
    return this->started && cycle > this->start_cycle &&
        (this->end_cycle == -1 || cycle <= this->end_cycle);
}


uint32_t SnaxTestDatapath::counter_at(int64_t cycle)
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
    return (uint32_t)(last - this->start_cycle);
}


vp::IoReqStatus SnaxTestDatapath::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxTestDatapath *_this = (SnaxTestDatapath *)__this;
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

    if (index < 3)
    {
        if (!is_write)
        {
            *data = _this->regs[index];
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x)\n", csr, *data);
            return vp::IO_REQ_OK;
        }
        if (index == 2 && (*data & 1))
        {
            if (_this->busy_at(cycle))
            {
                _this->trace.force_warning("Start (CSR %d) while the datapath is busy\n", csr);
                return vp::IO_REQ_INVALID;
            }
            _this->regs[index] = *data;
            _this->counter_before = _this->counter_at(cycle);
            _this->started = true;
            _this->start_cycle = cycle;
            _this->end_cycle = _this->regs[1] == 0 ? cycle : -1;
            _this->next_cycle = cycle + 1;
            _this->fired = 0;
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Write CSR %d (value: 0x%x), start: copy %s, every %d cycles, %d firings\n",
                csr, *data, (_this->regs[0] & 1) ? "B" : "A", ((_this->regs[0] >> 4) & 0xF) + 1,
                _this->regs[1]);
            if (_this->end_cycle == -1)
            {
                _this->fire_event.enqueue(1);
            }
            return vp::IO_REQ_OK;
        }
        _this->regs[index] = *data;
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Write CSR %d (value: 0x%x)\n", csr, *data);
        return vp::IO_REQ_OK;
    }

    if (index < 5)
    {
        if (is_write)
        {
            _this->trace.force_warning("Write to read-only CSR %d (value: 0x%x)\n", csr, *data);
            return vp::IO_REQ_INVALID;
        }
        *data = index == 3 ? _this->busy_at(cycle) : _this->counter_at(cycle);
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x, read-only)\n",
            csr, *data);
        return vp::IO_REQ_OK;
    }

    _this->trace.force_warning("CSR %d is not held by this block (is_write: %d)\n",
        csr, is_write);
    return vp::IO_REQ_INVALID;
}


bool SnaxTestDatapath::probe(vp::IoMaster &port, bool is_write)
{
    this->beat_req.init();
    this->beat_req.set_size(0);
    this->beat_req.set_is_write(is_write);
    return port.req(&this->beat_req) == vp::IO_REQ_OK;
}


void SnaxTestDatapath::move(vp::IoMaster &port, bool is_write, uint8_t *beat)
{
    this->beat_req.init();
    this->beat_req.set_size(this->beat_bytes);
    this->beat_req.set_is_write(is_write);
    this->beat_req.set_data(beat);
    if (port.req(&this->beat_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("A beat refused after its probe\n");
    }
}


// One cycle: fire if allowed and all three beats can move
void SnaxTestDatapath::fire_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxTestDatapath *_this = (SnaxTestDatapath *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (cycle >= _this->next_cycle && _this->probe(_this->in_a, false) &&
        _this->probe(_this->in_b, false) && _this->probe(_this->out, true))
    {
        _this->move(_this->in_a, false, _this->beat_a.data());
        _this->move(_this->in_b, false, _this->beat_b.data());
        _this->move(_this->out, true,
            (_this->regs[0] & 1) ? _this->beat_b.data() : _this->beat_a.data());
        _this->fired++;
        _this->next_cycle = cycle + ((_this->regs[0] >> 4) & 0xF) + 1;
        _this->trace.msg(vp::Trace::LEVEL_TRACE, "Fire %d\n", _this->fired - 1);

        if (_this->fired == _this->regs[1])
        {
            _this->end_cycle = cycle;
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Done: busy up to cycle %ld, counter %d\n",
                cycle, _this->counter_at(cycle + 1));
            return;
        }
    }

    // Every cycle while busy, so it always runs before the streamer's step
    _this->fire_event.enqueue(1);
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxTestDatapath(config);
}
