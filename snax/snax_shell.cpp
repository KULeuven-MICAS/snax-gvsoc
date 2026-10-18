/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell (GEN3 step 2, D128, D130): the CSR manager in front of a SnaxUnit,
// GeMMX's shell contract as snax_cluster gives it (05615e4): the
// ReqRspManager (hw/chisel/.../reqRspManager/ReqRspManager.scala) holding the
// read-write CSRs, BlockGemm's ctrl handshake, busy and performance counter
// (hw/chisel_acc/.../gemm/BlockGemm.scala).
//
// CSRs, offsets from its first CSR (the CSR mux removes it): the fields
// (property `fields`, in order), then start: read-write, read back as
// written; then busy and the counter: read-only (ro_set[0], ro_set[1]).
//
// Rules, c being the cycle of an access:
//   - a write to a field, or to start with bit 0 clear, is taken at once;
//   - a start (bit 0 of the start CSR written 1) goes to the unit's ctrl as
//     the fields as they stand, in CSR order, when the unit is idle in c
//     (BlockGemm: ctrl.ready is idle); the start is then accepted in c and
//     the write answered at once. While the unit is busy in c the write is
//     held (IO_REQ_PENDING: the ReqRspManager's req.ready is ctrl.ready), and
//     sent, then answered, in the cycle busy falls: E + 1, E the run's last
//     cycle;
//   - busy reads the unit's busy in c;
//   - the counter is reset by an accepted start and counts each busy cycle,
//     then holds after the run (BlockGemm's performance_counter): at c it is
//     the busy cycles after the accepted start and before c. A start the unit
//     ignores (count 0) still resets it.
// Busy and the counter are computed when read, from the cycles the unit's
// busy wire rose (busy from the next cycle) and fell (idle from the next).
// The unit sets the wire synchronously in the ctrl write that starts it, so a
// start sent in c sees its rise in c.

#include <algorithm>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_csr_block.hpp"


class SnaxShell : public vp::Component
{
public:
    SnaxShell(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static void busy_sync(vp::Block *__this, bool busy);
    static void send_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    bool unit_idle(int64_t cycle);
    bool busy_at(int64_t cycle);
    uint32_t counter_at(int64_t cycle);
    void send(int64_t cycle);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster ctrl_itf;
    vp::WireSlave<bool> busy_itf;
    vp::ClockEvent send_event;
    vp::IoReq ctrl_req;

    int nb_fields;
    int start_index;            // the start CSR: the last read-write one
    SnaxCsrBlock csrs;          // the fields, start; busy, counter
    std::vector<uint32_t> config_words;

    // The unit's busy wire: the cycles it last rose and fell (-1 if not)
    int64_t rise_cycle;
    int64_t fall_cycle;
    // The last accepted start (-1 if none)
    int64_t accept_cycle;
    // A start held while busy, and the value it writes to the start CSR
    vp::IoReq *held_req;
    uint32_t held_value;
};


SnaxShell::SnaxShell(vp::ComponentConf &config)
    : vp::Component(config),
      send_event(this, &SnaxShell::send_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    js::Config *fields = this->get_js_config()->get("fields");
    if (fields == nullptr || dynamic_cast<js::ConfigArray *>(fields) == nullptr ||
        fields->get_size() == 0)
    {
        this->trace.fatal("Property fields: missing, not a list or empty\n");
    }
    for (js::Config *field : fields->get_elems())
    {
        if (dynamic_cast<js::ConfigString *>(field) == nullptr || field->get_str().empty())
        {
            this->trace.fatal("Property fields: not a list of CSR names\n");
        }
    }
    js::Config *csr_base = this->get_js_config()->get("csr_base");
    if (csr_base == nullptr || dynamic_cast<js::ConfigNumber *>(csr_base) == nullptr)
    {
        this->trace.fatal("Property csr_base: missing or not a number\n");
    }

    this->nb_fields = fields->get_size();
    this->start_index = this->nb_fields;
    this->csrs.configure(&this->trace, csr_base->get_int(), this->nb_fields + 1, 2);
    this->config_words.resize(this->nb_fields);

    this->csr_itf.set_req_meth(&SnaxShell::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->new_master_port("ctrl", &this->ctrl_itf);
    this->busy_itf.set_sync_meth(&SnaxShell::busy_sync);
    this->new_slave_port("busy", &this->busy_itf);

    for (int i = 0; i < this->nb_fields; i++)
    {
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: %s\n", this->csrs.csr(i),
            fields->get_elem(i)->get_str().c_str());
    }
}


void SnaxShell::reset(bool active)
{
    if (active)
    {
        this->csrs.reset();
        this->rise_cycle = this->fall_cycle = -1;
        this->accept_cycle = -1;
        this->held_req = nullptr;
    }
}


// Idle in cycle: never started, or the last run ended before it
bool SnaxShell::unit_idle(int64_t cycle)
{
    return this->rise_cycle == -1 || (this->fall_cycle != -1 && this->fall_cycle < cycle);
}


bool SnaxShell::busy_at(int64_t cycle)
{
    return this->rise_cycle != -1 && cycle > this->rise_cycle &&
        (this->fall_cycle == -1 || cycle <= this->fall_cycle);
}


// The busy cycles in [accept + 1, cycle - 1]
uint32_t SnaxShell::counter_at(int64_t cycle)
{
    if (this->accept_cycle == -1 || this->rise_cycle == -1)
    {
        return 0;
    }
    int64_t first = std::max(this->accept_cycle, this->rise_cycle) + 1;
    int64_t last = cycle - 1;
    if (this->fall_cycle != -1 && this->fall_cycle < last)
    {
        last = this->fall_cycle;
    }
    return last >= first ? last - first + 1 : 0;
}


// The fields to the unit's ctrl: an accepted start in cycle
void SnaxShell::send(int64_t cycle)
{
    for (int i = 0; i < this->nb_fields; i++)
    {
        this->config_words[i] = this->csrs.regs[i];
    }
    this->ctrl_req.init();
    this->ctrl_req.set_size(4 * this->nb_fields);
    this->ctrl_req.set_is_write(true);
    this->ctrl_req.set_data((uint8_t *)this->config_words.data());
    if (this->ctrl_itf.req(&this->ctrl_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("Start refused by the unit at cycle %ld while idle\n", cycle);
    }
    this->accept_cycle = cycle;
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld\n", cycle);
}


vp::IoReqStatus SnaxShell::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();

    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [&](int ro) -> uint32_t {
        return ro == 0 ? _this->busy_at(cycle) : _this->counter_at(cycle);
    });
    if (index < 0)
    {
        return status;
    }

    uint32_t value = *(uint32_t *)req->get_data();
    if (index != _this->start_index || !(value & 1))
    {
        _this->csrs.write(index, value);
        return vp::IO_REQ_OK;
    }

    if (_this->unit_idle(cycle))
    {
        _this->csrs.write(index, value);
        _this->send(cycle);
        return vp::IO_REQ_OK;
    }

    // Held until the cycle busy falls; if the run already ended in this
    // cycle, that is the next one
    _this->held_req = req;
    _this->held_value = value;
    _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start held at cycle %ld: the unit is busy\n", cycle);
    if (_this->fall_cycle != -1 && !_this->send_event.is_enqueued())
    {
        _this->send_event.enqueue(_this->fall_cycle + 1 - cycle);
    }
    return vp::IO_REQ_PENDING;
}


void SnaxShell::busy_sync(vp::Block *__this, bool busy)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();
    if (busy)
    {
        _this->rise_cycle = cycle;
        _this->fall_cycle = -1;
        return;
    }
    _this->fall_cycle = cycle;
    if (_this->held_req != nullptr && !_this->send_event.is_enqueued())
    {
        _this->send_event.enqueue(1);
    }
}


// The cycle busy falls: the held start goes to the unit, then its write is
// answered
void SnaxShell::send_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();
    vp::IoReq *req = _this->held_req;
    if (req == nullptr)
    {
        return;
    }
    _this->held_req = nullptr;
    _this->csrs.write(_this->start_index, _this->held_value, " (held)");
    _this->send(cycle);
    req->status = vp::IO_REQ_OK;
    req->get_resp_port()->resp(req);
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxShell(config);
}
