/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell (D130 in snax-forge): the CSR manager in front of a SnaxUnit.
// Its rule (the CSRs, start, hold while busy, busy, the counter) is
// SnaxShellRule in snax_shell.hpp, which tests/snax/shell/ checks against
// hand-worked cases; this file wires it to the CSR port, the unit's ctrl and
// busy ports, and the event that takes a held start in E + 1.

#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_csr_block.hpp"
#include "snax_shell.hpp"


class SnaxShell : public vp::Component
{
public:
    SnaxShell(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static void busy_sync(vp::Block *__this, bool busy);
    static void send_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    void send(int64_t cycle);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster ctrl_itf;
    vp::WireSlave<bool> busy_itf;
    vp::ClockEvent send_event;
    vp::IoReq ctrl_req;

    int nb_fields;
    SnaxShellRule rule;
    // The CSRs' decoding, refusals and messages; its registers mirror the
    // rule's, written in the same calls
    SnaxCsrBlock csrs;          // the fields, start; busy, counter
    std::vector<uint32_t> config_words;
    vp::IoReq *held_req;        // the held start's request (rule.held)
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
    this->rule.configure(this->nb_fields);
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
        this->rule.reset();
        this->held_req = nullptr;
    }
}


// The fields to the unit's ctrl: an accepted start in cycle
void SnaxShell::send(int64_t cycle)
{
    for (int i = 0; i < this->nb_fields; i++)
    {
        this->config_words[i] = this->rule.regs[i];
    }
    this->ctrl_req.init();
    this->ctrl_req.set_size(4 * this->nb_fields);
    this->ctrl_req.set_is_write(true);
    this->ctrl_req.set_data((uint8_t *)this->config_words.data());
    if (this->ctrl_itf.req(&this->ctrl_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("Start refused by the unit at cycle %ld while idle\n", cycle);
    }
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld\n", cycle);
}


vp::IoReqStatus SnaxShell::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();

    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [&](int ro) -> uint32_t {
        return _this->rule.read(cycle, _this->nb_fields + 1 + ro);
    });
    if (index < 0)
    {
        return status;
    }

    uint32_t value = *(uint32_t *)req->get_data();
    SnaxShellRule::Write write = _this->rule.write(cycle, index, value);
    if (!write.held)
    {
        _this->csrs.write(index, value);
        if (write.start)
        {
            _this->send(cycle);
        }
        return vp::IO_REQ_OK;
    }

    // Held until the cycle after busy falls; if the run already ended in this
    // cycle, that is the next one
    _this->held_req = req;
    _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start held at cycle %ld: the unit is busy\n", cycle);
    int64_t release = _this->rule.release_cycle();
    if (release != -1 && !_this->send_event.is_enqueued())
    {
        _this->send_event.enqueue(release - cycle);
    }
    return vp::IO_REQ_PENDING;
}


void SnaxShell::busy_sync(vp::Block *__this, bool busy)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();
    _this->rule.busy(cycle, busy);
    int64_t release = _this->rule.release_cycle();
    if (release != -1 && !_this->send_event.is_enqueued())
    {
        _this->send_event.enqueue(release - cycle);
    }
}


// The cycle after busy falls: the held start goes to the unit, then its
// write is answered
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
    _this->rule.release(cycle);
    _this->csrs.write(_this->rule.start_index(), _this->rule.regs[_this->rule.start_index()],
        " (held)");
    _this->send(cycle);
    req->status = vp::IO_REQ_OK;
    req->get_resp_port()->resp(req);
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxShell(config);
}
