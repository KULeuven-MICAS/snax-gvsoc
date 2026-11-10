/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell (D130, D146 in snax-forge): the CSRs of one group of an
// accelerator, in front of its SnaxGroup. Its rule (START, JOBS, the units'
// read-write CSRs, a write held while busy, the empty run, STATUS,
// BUSY_COUNTER) is SnaxShellRule in snax_shell.hpp, which tests/snax/shell/
// checks against hand-worked cases; this file wires it to the CSR port, the
// group's ctrl and busy ports, and the event that takes a held write in E + 1.
//
// Properties (a missing or bad one is a fatal error naming it):
//   csr_base   the group's first CSR (its START), for the trace
//   csrs       its read-write CSRs' names in CSR order: START, JOBS, then the
//              units' (JOB_BEATS, each fold's without a fixed T, then its
//              scalars', in unit order); STATUS and BUSY_COUNTER follow
//   widths     each read-write CSR's width, in the order of csrs, 1 to 32
//              (accelerator.json's, D152: START 1, JOBS and JOB_BEATS
//              job_width); a write keeps its low bits
//   busy_counter_width  BUSY_COUNTER's width, 1 to 32: it saturates at
//              2^w - 1
// An accepted start, but the empty run (JOBS or a JOB_BEATS 0), goes to the
// group's ctrl as a write of 32-bit words: JOBS, then every JOB_BEATS in unit
// order (JOBS and 1 without one), then every unit's scalar CSR (any other
// name after JOBS: K1, K1_LO, K1_HI) in CSR order.

#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_csr_block.hpp"
#include "snax_props.hpp"
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
    SnaxCsrBlock csrs;          // START, JOBS, the units'; STATUS, BUSY_COUNTER
    std::vector<uint32_t> config_words;     // JOBS, then each JOB_BEATS (or 1)
    vp::IoReq *held_req;        // the held write's request (rule.held)
};


SnaxShell::SnaxShell(vp::ComponentConf &config)
    : vp::Component(config),
      send_event(this, &SnaxShell::send_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    SnaxProps props(&this->trace);
    std::vector<std::string> names;
    for (js::Config *name : props.list_prop(this->get_js_config(), "csrs", ""))
    {
        names.push_back(props.as_str(name, "csrs[" + std::to_string(names.size()) + "]"));
    }
    if (names.size() < 2 || names[0] != "START" || names[1] != "JOBS")
    {
        this->trace.fatal("Property csrs: must start with START, JOBS\n");
    }
    std::vector<int> job_beats, scalars;
    for (size_t i = 0; i < names.size(); i++)
    {
        if (names[i].empty())
        {
            this->trace.fatal("Property csrs[%ld]: an empty CSR name\n", i);
        }
        if (names[i] == "JOB_BEATS")
        {
            job_beats.push_back(i);
        }
        else if (i >= 2)    // a unit's scalar (K1, K1_LO, K1_HI), sent after the JOB_BEATS
        {
            scalars.push_back(i);
        }
    }
    int csr_base = props.int_prop(this->get_js_config(), "csr_base", "");
    std::vector<int> widths;
    for (js::Config *width : props.list_prop(this->get_js_config(), "widths", ""))
    {
        int w = props.as_int(width, "widths[" + std::to_string(widths.size()) + "]");
        if (w < 1 || w > 32)
        {
            this->trace.fatal("Property widths[%ld]: %d, must be 1 to 32\n", widths.size(), w);
        }
        widths.push_back(w);
    }
    if (widths.size() != names.size())
    {
        this->trace.fatal("Property widths: %ld, one per read-write CSR (%ld)\n", widths.size(),
            names.size());
    }
    int busy_counter_width = props.int_prop(this->get_js_config(), "busy_counter_width", "");
    if (busy_counter_width < 1 || busy_counter_width > 32)
    {
        this->trace.fatal("Property busy_counter_width: %d, must be 1 to 32\n", busy_counter_width);
    }

    this->nb_rw = names.size();
    this->rule.configure(this->nb_rw, job_beats, widths, busy_counter_width, scalars);
    this->csrs.configure(&this->trace, csr_base, this->nb_rw, 2);

    this->csr_itf.set_req_meth(&SnaxShell::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->new_master_port("ctrl", &this->ctrl_itf);
    this->busy_itf.set_sync_meth(&SnaxShell::busy_sync);
    this->new_slave_port("busy", &this->busy_itf);

    for (int i = 0; i < this->nb_rw; i++)
    {
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: %s\n", this->csrs.csr(i),
            names[i].c_str());
    }
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: STATUS, CSR %d: BUSY_COUNTER\n",
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


// An accepted start in cycle: JOBS and every JOB_BEATS to the group's ctrl,
// or, for the empty run, nothing (the rule has ended it)
void SnaxShell::send(int64_t cycle, bool empty)
{
    this->config_words = this->rule.words();
    // The JOB_BEATS and scalar words, for the debug lines below
    std::string text;
    for (size_t i = 1; this->trace.get_active() && i < this->config_words.size(); i++)
    {
        text += " " + std::to_string(this->config_words[i]);
    }
    if (empty)
    {
        this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld: JOBS %u, "
            "JOB_BEATS%s, the empty run, done\n", cycle, this->rule.jobs(), text.c_str());
        return;
    }
    this->ctrl_req.init();
    this->ctrl_req.set_size(4 * this->config_words.size());
    this->ctrl_req.set_is_write(true);
    this->ctrl_req.set_data((uint8_t *)this->config_words.data());
    if (this->ctrl_itf.req(&this->ctrl_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("Start refused by the group at cycle %ld while idle\n", cycle);
    }
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start accepted at cycle %ld: JOBS %u, JOB_BEATS%s\n",
        cycle, this->rule.jobs(), text.c_str());
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
        // As the rule keeps it: at its width, START 0
        _this->csrs.write(index, _this->rule.regs[index],
            index == SnaxShellRule::START ? " (START, a strobe)" : "");
        if (write.start)
        {
            _this->send(cycle, write.empty);
        }
        return vp::IO_REQ_OK;
    }

    // Held until the cycle after busy falls; if the run already ended in this
    // cycle, that is the next one
    _this->held_req = req;
    _this->trace.msg(vp::Trace::LEVEL_DEBUG,
        "Write to CSR %d held at cycle %ld: the unit is busy\n", index, cycle);
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


// The cycle after busy falls: the held write is taken (a held start goes to
// the unit), then answered
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
    int index = _this->rule.held_index;
    SnaxShellRule::Write write = _this->rule.release(cycle);
    _this->csrs.write(index, _this->rule.regs[index],
        index == SnaxShellRule::START ? " (START, a strobe, held)" : " (held)");
    if (write.start)
    {
        _this->send(cycle, write.empty);
    }
    req->status = vp::IO_REQ_OK;
    req->get_resp_port()->resp(req);
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxShell(config);
}
