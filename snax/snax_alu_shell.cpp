/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// snax_alu's accelerator as snax_cluster builds it (SG4):
// hw/snax_alu/src/snax_alu_shell_wrapper.sv with its CSR block snax_alu_csr.sv
// and num_pe copies of snax_alu_pe.sv, behind the ReqRspManager that holds
// its read-write CSRs (b2672f8).
//
// CSRs, offsets from its first CSR (the CSR mux removes it):
//   0 mode, 1 length, 2 start: read-write, read back as written;
//   3 busy, 4 counter: read-only.
//
// Rules, s being the cycle a start is written (a write to offset 2 with bit
// 0 set; never held, never refused, also while busy; a start that cannot end,
// length 0 or firings kept past length - 1, is warned about and runs on):
//   - mode (bits 1:0) and length are latched at the end of s: a firing in s
//     still uses the previous ones;
//   - busy is 1 from s + 1; it drops after the firing at which len_counter
//     equals length - 1, and if that firing is in s itself the end wins;
//   - len_counter counts firings and is reset only by the end of a run, not
//     by a start: a start while busy keeps the firings done;
//   - the counter is 1 at s + 1, then counts each busy cycle in which
//     len_counter is not length - 1, and holds after the run: its final
//     value is f - s + 1, f the cycle of the second-to-last firing.
// So busy and the counter are computed from three cycles when read: s, F
// (the firing that brings len_counter to length - 1; s if the start found it
// there) and E (the firing that ends the run). A start is recorded when it is
// written and applied at the first event or access in a later cycle, so the
// core's write and the firing of cycle s can run in either order.
//
// A firing (snax_alu_pe.sv, combinational: latency 0, II 1) needs busy, a
// beat on in_a and on in_b and room on out, all in one cycle: it probes the
// three ports (size 0, snax_streamer.cpp), then moves all three. Per lane, on
// data_width-bit words: add (mode 0, the RTL's default), sub, mul (low bits),
// xor. Its event runs every cycle while busy, before the streamer's step
// (SG3 step 7), so a beat it takes returns its reader's credit in time for
// that cycle's requests.
//
// Where a later accelerator differs from this one (GEN3 in snax-forge), the
// change stays local: try_fire() holds how it waits for its inputs and its
// output, compute() what it does with a beat.
//
// Per run, its busy cycles are classed in D59's order at II 1: busy (fired) >
// stall_out (both inputs, no room on out) > stall_in (an input missing); the
// trace gives them when the run ends.

#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include "snax_csr_block.hpp"


enum AluClass { ALU_BUSY, ALU_STALL_OUT, ALU_STALL_IN, ALU_NB_CLASSES };

static const char *mode_names[4] = {"add", "sub", "mul", "xor"};


class SnaxAluShell : public vp::Component
{
public:
    SnaxAluShell(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static void fire_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    void apply_start(int64_t cycle);
    bool busy_at(int64_t cycle);
    uint32_t counter_at(int64_t cycle);
    AluClass try_fire(int64_t cycle);
    void compute(const uint64_t *a, const uint64_t *b, uint64_t *out);
    void count_firing(int64_t cycle);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint64_t *beat);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster in_a;
    vp::IoMaster in_b;
    vp::IoMaster out;
    vp::ClockEvent fire_event;
    vp::IoReq beat_req;

    int num_pe;                 // lanes, NumPE of the shell wrapper
    int beat_bytes;             // num_pe * data_width / 8
    SnaxCsrBlock csrs;          // mode, length, start; busy, counter

    // A start written and not applied yet: its cycle (-1 if none) and the
    // mode and length it latches
    int64_t pending_cycle;
    uint32_t pending_mode;
    uint32_t pending_length;

    // The run: its start s, the latched mode and length, len_counter, and the
    // cycles F and E (-1 while not known)
    bool started;
    int64_t start_cycle;
    uint32_t mode;
    uint32_t length;
    uint32_t len_counter;
    int64_t fin_cycle;
    int64_t end_cycle;
    int64_t classes[ALU_NB_CLASSES];

    std::vector<uint64_t> beat_a, beat_b, beat_out;
};


SnaxAluShell::SnaxAluShell(vp::ComponentConf &config)
    : vp::Component(config),
      fire_event(this, &SnaxAluShell::fire_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    this->csrs.configure(&this->trace, this->get_js_config()->get_child_int("csr_base"), 3, 2);
    this->num_pe = this->get_js_config()->get_child_int("num_pe");
    int data_width = this->get_js_config()->get_child_int("data_width");
    if (data_width != 64)
    {
        // The streamer's beats are 64-bit words per lane (one per TCDM port)
        this->trace.fatal("data_width %d: only 64 is modelled\n", data_width);
    }
    this->beat_bytes = this->num_pe * data_width / 8;
    this->beat_a.resize(this->num_pe);
    this->beat_b.resize(this->num_pe);
    this->beat_out.resize(this->num_pe);

    this->csr_itf.set_req_meth(&SnaxAluShell::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->new_master_port("in_a", &this->in_a);
    this->new_master_port("in_b", &this->in_b);
    this->new_master_port("out", &this->out);
}


void SnaxAluShell::reset(bool active)
{
    if (active)
    {
        this->csrs.reset();
        this->pending_cycle = -1;
        this->started = false;
        this->start_cycle = 0;
        this->mode = this->length = 0;
        this->len_counter = 0;
        this->fin_cycle = this->end_cycle = -1;
        for (int c = 0; c < ALU_NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
    }
}


// The start written in s takes effect at the end of s: applied at the first
// event or access in a later cycle, after any firing of cycle s.
void SnaxAluShell::apply_start(int64_t cycle)
{
    if (this->pending_cycle == -1 || cycle <= this->pending_cycle)
    {
        return;
    }
    int64_t s = this->pending_cycle;
    bool ended_in_s = this->started && this->end_cycle == s;
    this->pending_cycle = -1;
    this->started = true;
    this->start_cycle = s;
    this->mode = this->pending_mode & 3;
    this->length = this->pending_length;
    for (int c = 0; c < ALU_NB_CLASSES; c++)
    {
        this->classes[c] = 0;
    }

    if (ended_in_s)
    {
        // The end wins: busy stays 0, the counter reads 1
        this->fin_cycle = this->end_cycle = s;
        this->trace.msg(vp::Trace::LEVEL_DEBUG,
            "Start at cycle %ld: the previous run ended in that cycle, not busy\n", s);
        return;
    }

    uint32_t last = this->length - 1;
    this->end_cycle = -1;
    this->fin_cycle = this->len_counter == last ? s : -1;
    this->trace.msg(vp::Trace::LEVEL_DEBUG,
        "Start at cycle %ld: %s, length %u, %u firings kept\n",
        s, mode_names[this->mode], this->length, this->len_counter);
    if (this->length == 0 || this->len_counter > last)
    {
        // The RTL stays busy and the program goes on: warn without stopping
        // the run, also when warnings are errors (werror)
        this->trace.force_warning_no_error("Start (CSR %d) at cycle %ld with length %u and %u firings "
            "kept: the run does not end\n", this->csrs.csr(2), s, this->length,
            this->len_counter);
    }
}


bool SnaxAluShell::busy_at(int64_t cycle)
{
    return this->started && cycle > this->start_cycle &&
        (this->end_cycle == -1 || cycle <= this->end_cycle);
}


uint32_t SnaxAluShell::counter_at(int64_t cycle)
{
    if (!this->started)
    {
        return 0;
    }
    int64_t last = cycle - 1;
    if (this->fin_cycle != -1 && this->fin_cycle < last)
    {
        last = this->fin_cycle;
    }
    return 1 + (uint32_t)(last > this->start_cycle ? last - this->start_cycle : 0);
}


vp::IoReqStatus SnaxAluShell::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxAluShell *_this = (SnaxAluShell *)__this;
    int64_t cycle = _this->clock.get_cycles();
    _this->apply_start(cycle);

    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [&](int ro) -> uint32_t {
        return ro == 0 ? _this->busy_at(cycle) : _this->counter_at(cycle);
    });
    if (index < 0)
    {
        return status;
    }

    uint32_t value = *(uint32_t *)req->get_data();
    _this->csrs.write(index, value);
    if (index == 2 && (value & 1))
    {
        // The ReqRspManager hands over the registers as they stand
        _this->pending_cycle = cycle;
        _this->pending_mode = _this->csrs.regs[0];
        _this->pending_length = _this->csrs.regs[1];
        if (!_this->fire_event.is_enqueued())
        {
            _this->fire_event.enqueue(1);
        }
    }
    return vp::IO_REQ_OK;
}


bool SnaxAluShell::probe(vp::IoMaster &port, bool is_write)
{
    this->beat_req.init();
    this->beat_req.set_size(0);
    this->beat_req.set_is_write(is_write);
    return port.req(&this->beat_req) == vp::IO_REQ_OK;
}


void SnaxAluShell::move(vp::IoMaster &port, bool is_write, uint64_t *beat)
{
    this->beat_req.init();
    this->beat_req.set_size(this->beat_bytes);
    this->beat_req.set_is_write(is_write);
    this->beat_req.set_data((uint8_t *)beat);
    if (port.req(&this->beat_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("A beat refused after its probe\n");
    }
}


// How the ALU waits: both inputs and room on the output in one cycle, or
// nothing moves (snax_alu_pe.sv's ready and valid).
AluClass SnaxAluShell::try_fire(int64_t cycle)
{
    if (!this->probe(this->in_a, false) || !this->probe(this->in_b, false))
    {
        return ALU_STALL_IN;
    }
    if (!this->probe(this->out, true))
    {
        return ALU_STALL_OUT;
    }
    this->move(this->in_a, false, this->beat_a.data());
    this->move(this->in_b, false, this->beat_b.data());
    this->compute(this->beat_a.data(), this->beat_b.data(), this->beat_out.data());
    this->move(this->out, true, this->beat_out.data());
    this->count_firing(cycle);
    return ALU_BUSY;
}


// What the ALU does with a beat: one op per lane on 64-bit words, wrapping
void SnaxAluShell::compute(const uint64_t *a, const uint64_t *b, uint64_t *out)
{
    for (int lane = 0; lane < this->num_pe; lane++)
    {
        switch (this->mode)
        {
            case 1: out[lane] = a[lane] - b[lane]; break;
            case 2: out[lane] = a[lane] * b[lane]; break;
            case 3: out[lane] = a[lane] ^ b[lane]; break;
            default: out[lane] = a[lane] + b[lane]; break;
        }
    }
}


// len_counter after a firing in cycle: the end of the run, or F
void SnaxAluShell::count_firing(int64_t cycle)
{
    uint32_t last = this->length - 1;
    this->trace.msg(vp::Trace::LEVEL_TRACE, "Fire %u\n", this->len_counter);
    if (this->len_counter == last)
    {
        this->len_counter = 0;
        this->end_cycle = cycle;
        return;
    }
    this->len_counter++;
    if (this->len_counter == last)
    {
        this->fin_cycle = cycle;
    }
}


// One cycle while busy or while a start waits to be applied
void SnaxAluShell::fire_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxAluShell *_this = (SnaxAluShell *)__this;
    int64_t cycle = _this->clock.get_cycles();
    _this->apply_start(cycle);

    if (_this->busy_at(cycle))
    {
        _this->classes[_this->try_fire(cycle)]++;
        if (_this->end_cycle == cycle)
        {
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Done: busy up to cycle %ld, counter %u; busy %ld, stall_out %ld, stall_in %ld\n",
                cycle, _this->counter_at(cycle + 1), _this->classes[ALU_BUSY],
                _this->classes[ALU_STALL_OUT], _this->classes[ALU_STALL_IN]);
        }
    }

    // Every cycle while busy, so it always runs before the streamer's step
    if (_this->pending_cycle != -1 || _this->busy_at(cycle + 1))
    {
        _this->fire_event.enqueue(1);
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxAluShell(config);
}
