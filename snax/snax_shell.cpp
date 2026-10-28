/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell (D130, D146 in snax-forge): the CSRs of one group of an
// accelerator, in front of its SnaxUnit. Its rule (START, JOBS, the units'
// read-write CSRs, a start held while busy, the empty run, STATUS, COUNTER)
// is SnaxShellRule in snax_shell.hpp, which tests/snax/shell/ checks against
// hand-worked cases; this file wires it to the CSR port, the unit's ctrl and
// busy ports, and the event that takes a held start in E + 1.
//
// Properties (a missing or bad one is a fatal error naming it):
//   csr_base   the group's first CSR (its START), for the trace
//   csrs       its read-write CSRs' names in CSR order: START, JOBS, then the
//              units' (JOB_BEATS, a fold's); STATUS and COUNTER follow
// An accepted start, but the empty run (JOBS or JOB_BEATS 0), goes to the
// unit's ctrl as a write of two 32-bit words, JOBS and JOB_BEATS (1 without
// one).

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

    void send(int64_t cycle, bool empty);

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::IoMaster ctrl_itf;
    vp::WireSlave<bool> busy_itf;
    vp::ClockEvent send_event;
    vp::IoReq ctrl_req;

    int nb_rw;
    SnaxShellRule rule;
    // The CSRs' decoding, refusals and messages; its registers mirror the
    // rule's, written in the same calls
    SnaxCsrBlock csrs;          // START, JOBS, the units'; STATUS, COUNTER
    uint32_t config_words[2];   // JOBS, JOB_BEATS
    vp::IoReq *held_req;        // the held start's request (rule.held)
};


SnaxShell::SnaxShell(vp::ComponentConf &config)
    : vp::Component(config),
      send_event(this, &SnaxShell::send_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    js::Config *names = this->get_js_config()->get("csrs");
    if (names == nullptr || dynamic_cast<js::ConfigArray *>(names) == nullptr ||
        names->get_size() < 2)
    {
        this->trace.fatal("Property csrs: missing, not a list or shorter than START, JOBS\n");
    }
    int job_beats = -1;
    for (int i = 0; i < names->get_size(); i++)
    {
        js::Config *name = names->get_elem(i);
        if (dynamic_cast<js::ConfigString *>(name) == nullptr || name->get_str().empty())
        {
            this->trace.fatal("Property csrs: not a list of CSR names\n");
        }
        if ((i == 0 && name->get_str() != "START") || (i == 1 && name->get_str() != "JOBS"))
        {
            this->trace.fatal("Property csrs: must start with START, JOBS, not %s\n",
                name->get_str().c_str());
        }
        if (name->get_str() == "JOB_BEATS")
        {
            job_beats = i;
        }
    }
    js::Config *csr_base = this->get_js_config()->get("csr_base");
    if (csr_base == nullptr || dynamic_cast<js::ConfigNumber *>(csr_base) == nullptr)
    {
        this->trace.fatal("Property csr_base: missing or not a number\n");
    }

    this->nb_rw = names->get_size();
    this->rule.configure(this->nb_rw, job_beats);
    this->csrs.configure(&this->trace, csr_base->get_int(), this->nb_rw, 2);

    this->csr_itf.set_req_meth(&SnaxShell::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->new_master_port("ctrl", &this->ctrl_itf);
    this->busy_itf.set_sync_meth(&SnaxShell::busy_sync);
    this->new_slave_port("busy", &this->busy_itf);

    for (int i = 0; i < this->nb_rw; i++)
    {
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: %s\n", this->csrs.csr(i),
            names->get_elem(i)->get_str().c_str());
    }
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: STATUS, CSR %d: COUNTER\n",
        this->csrs.csr(this->nb_rw), this->csrs.csr(this->nb_rw + 1));
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


// An accepted start in cycle: JOBS and JOB_BEATS to the unit's ctrl, or, for
// the empty run, nothing (the rule has ended it)
void SnaxShell::send(int64_t cycle, bool empty)
{
    if (empty)
    {
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld: JOBS %u, "
            "JOB_BEATS %u, the empty run, done\n", cycle, this->rule.jobs(),
            this->rule.job_beats());
        return;
    }
    this->config_words[0] = this->rule.jobs();
    this->config_words[1] = this->rule.job_beats();
    this->ctrl_req.init();
    this->ctrl_req.set_size(sizeof(this->config_words));
    this->ctrl_req.set_is_write(true);
    this->ctrl_req.set_data((uint8_t *)this->config_words);
    if (this->ctrl_itf.req(&this->ctrl_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("Start refused by the unit at cycle %ld while idle\n", cycle);
    }
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld: JOBS %u, JOB_BEATS "
        "%u\n", cycle, this->config_words[0], this->config_words[1]);
}


vp::IoReqStatus SnaxShell::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxShell *_this = (SnaxShell *)__this;
    int64_t cycle = _this->clock.get_cycles();

    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [&](int ro) -> uint32_t {
        return _this->rule.read(cycle, _this->nb_rw + ro);
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
            _this->send(cycle, write.empty);
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
    bool empty = _this->rule.release(cycle);
    _this->csrs.write(SnaxShellRule::START, _this->rule.regs[SnaxShellRule::START], " (held)");
    _this->send(cycle, empty);
    req->status = vp::IO_REQ_OK;
    req->get_resp_port()->resp(req);
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxShell(config);
}
