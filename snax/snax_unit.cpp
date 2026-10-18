/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxUnit (GEN3 step 1, D128): the datapath of one of snax-forge's Chisel
// blocks, generic, every number a property read at run time (get_js_config),
// so a design point compiles nothing. The cycle rule and the op table are in
// snax_unit.hpp; this file is the component around them.
//
// Properties (a missing one, a wrong type or a bad value is a fatal error
// naming it):
//   inputs, outputs  port names (lists of strings); the op table is binary,
//                    so two inputs and one output
//   lanes            elements per beat (> 0)
//   data_width       bits per element: 8, 16, 32 or 64, and lanes *
//                    data_width a multiple of 64. The streamer's beats are
//                    whole 64-bit channel words, lane 0 first
//                    (snax_streamer.cpp); the elements are packed in them
//                    data_width bits apart, lane 0 lowest, as Chisel packs a
//                    Vec
//   op               ElementwiseOp's encoding: add 0, sub 1, mul 2, and 3,
//                    or 4, xor 5, min 6, max 7; integers, wrapping to
//                    data_width
//   signed           min and max compare as two's complement (bool)
//   control          counted: the unit counts its firings; the start's
//                    configuration is one 32-bit word, the trip count
//   wait             lockstep or pipelined (snax_unit.hpp)
//   latency, ii      pipelined: L >= 0 and II >= 1; lockstep: 0 and 1
//   csr_base         the shell's first CSR, for the trace
//
// Ports:
//   <input>, <output>  io masters to the streamer's reader_<i> and writer_<j>:
//                      a probe (size 0) of every port, then the beats moved
//                      (snax_alu_shell.cpp's way), so nothing moves unless the
//                      rule says so
//   ctrl               io slave: a write of the configuration words in CSR
//                      order starts a run in that cycle; refused (DENIED, after
//                      a warning) while busy. A count of 0 is answered and
//                      ignored
//   busy               wire<bool> master, driven on every change, in the cycle
//                      the change is decided: true in the cycle a start is
//                      taken (busy from the next), false in the run's last
//                      cycle (idle from the next)
//
// Its event runs every busy cycle, scheduled as snax_alu_shell.cpp's, so it
// runs before the streamer's step in a cycle. At the end of each run the trace
// gives `run <i>: firings <f> busy <b> stall_in <si> stall_out <so> flush <fl>`
// (SnaxUnitRule::run_line), the classes adding up to the run's busy cycles.

#include <deque>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_unit.hpp"


class SnaxUnit : public vp::Component
{
public:
    SnaxUnit(vp::ComponentConf &config);

private:
    static vp::IoReqStatus ctrl_req(vp::Block *__this, vp::IoReq *req);
    static void fire_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    js::Config *prop(const char *name);
    int int_prop(const char *name);
    std::string str_prop(const char *name);
    std::vector<std::string> names_prop(const char *name);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint64_t *beat);
    void compute(std::vector<uint64_t> &out);

    vp::Trace trace;
    vp::IoSlave ctrl_itf;
    vp::WireMaster<bool> busy_itf;
    std::vector<vp::IoMaster> in_itf;
    vp::IoMaster out_itf;
    vp::ClockEvent fire_event;
    vp::IoReq beat_req;

    int lanes;
    int data_width;
    int op;
    bool is_signed;
    int beat_words;             // 64-bit words per beat
    int nb_config_words;        // the ctrl write's words
    uint32_t csr_base;
    SnaxUnitRule rule;

    std::vector<std::vector<uint64_t>> beat_in;   // per input, the beat taken
    std::deque<std::vector<uint64_t>> results;    // computed, not pushed yet
};


SnaxUnit::SnaxUnit(vp::ComponentConf &config)
    : vp::Component(config),
      fire_event(this, &SnaxUnit::fire_handler)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    std::vector<std::string> inputs = this->names_prop("inputs");
    std::vector<std::string> outputs = this->names_prop("outputs");
    if (inputs.size() != 2)
    {
        this->trace.fatal("Property inputs: %ld names, the op table takes two inputs\n",
            inputs.size());
    }
    if (outputs.size() != 1)
    {
        this->trace.fatal("Property outputs: %ld names, the op table gives one output\n",
            outputs.size());
    }

    this->lanes = this->int_prop("lanes");
    if (this->lanes <= 0)
    {
        this->trace.fatal("Property lanes: %d, must be positive\n", this->lanes);
    }
    this->data_width = this->int_prop("data_width");
    if (this->data_width != 8 && this->data_width != 16 && this->data_width != 32 &&
        this->data_width != 64)
    {
        this->trace.fatal("Property data_width: %d, must be 8, 16, 32 or 64\n", this->data_width);
    }
    if (this->lanes * this->data_width % 64 != 0)
    {
        this->trace.fatal("Property data_width: lanes %d x %d bits is not a whole number of the "
            "streamer's 64-bit channel words\n", this->lanes, this->data_width);
    }
    this->beat_words = this->lanes * this->data_width / 64;

    this->op = this->int_prop("op");
    if (this->op < 0 || this->op >= UNIT_NB_OPS)
    {
        this->trace.fatal("Property op: %d, not an ElementwiseOp encoding (0 to %d)\n", this->op,
            UNIT_NB_OPS - 1);
    }
    js::Config *is_signed = this->prop("signed");
    if (dynamic_cast<js::ConfigBool *>(is_signed) == nullptr)
    {
        this->trace.fatal("Property signed: not a bool\n");
    }
    this->is_signed = is_signed->get_bool();

    std::string control = this->str_prop("control");
    if (control != "counted")
    {
        this->trace.fatal("Property control: unknown kind \"%s\" (counted)\n", control.c_str());
    }
    this->nb_config_words = 1;

    std::string wait = this->str_prop("wait");
    int latency = this->int_prop("latency");
    int ii = this->int_prop("ii");
    if (wait == "lockstep")
    {
        if (latency != 0)
        {
            this->trace.fatal("Property latency: %d, lockstep has latency 0\n", latency);
        }
        if (ii != 1)
        {
            this->trace.fatal("Property ii: %d, lockstep has II 1\n", ii);
        }
        this->rule.configure(SnaxUnitRule::LOCKSTEP, 0, 1);
    }
    else if (wait == "pipelined")
    {
        if (latency < 0)
        {
            this->trace.fatal("Property latency: %d, must be 0 or more\n", latency);
        }
        if (ii < 1)
        {
            this->trace.fatal("Property ii: %d, must be 1 or more\n", ii);
        }
        this->rule.configure(SnaxUnitRule::PIPELINED, latency, ii);
    }
    else
    {
        this->trace.fatal("Property wait: unknown kind \"%s\" (lockstep, pipelined)\n",
            wait.c_str());
    }
    this->csr_base = this->int_prop("csr_base");

    this->beat_in.assign(inputs.size(), std::vector<uint64_t>(this->beat_words));

    // Sized once, before any port is registered: never resized after
    this->in_itf.resize(inputs.size());
    for (size_t i = 0; i < inputs.size(); i++)
    {
        this->new_master_port(inputs[i], &this->in_itf[i]);
    }
    this->new_master_port(outputs[0], &this->out_itf);
    this->ctrl_itf.set_req_meth(&SnaxUnit::ctrl_req);
    this->new_slave_port("ctrl", &this->ctrl_itf);
    this->new_master_port("busy", &this->busy_itf);

    this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s, %d lanes of %d bits, %s, latency %d, ii %d\n",
        snax_unit_op_names[this->op], this->lanes, this->data_width, wait.c_str(), latency, ii);
}


void SnaxUnit::reset(bool active)
{
    if (active)
    {
        this->rule.reset();
        this->results.clear();
    }
}


js::Config *SnaxUnit::prop(const char *name)
{
    js::Config *config = this->get_js_config()->get(name);
    if (config == nullptr)
    {
        this->trace.fatal("Property %s: missing\n", name);
    }
    return config;
}


int SnaxUnit::int_prop(const char *name)
{
    js::Config *config = this->prop(name);
    if (dynamic_cast<js::ConfigNumber *>(config) == nullptr)
    {
        this->trace.fatal("Property %s: not a number\n", name);
    }
    return config->get_int();
}


std::string SnaxUnit::str_prop(const char *name)
{
    js::Config *config = this->prop(name);
    if (dynamic_cast<js::ConfigString *>(config) == nullptr)
    {
        this->trace.fatal("Property %s: not a string\n", name);
    }
    return config->get_str();
}


std::vector<std::string> SnaxUnit::names_prop(const char *name)
{
    js::Config *config = this->prop(name);
    if (dynamic_cast<js::ConfigArray *>(config) == nullptr)
    {
        this->trace.fatal("Property %s: not a list of names\n", name);
    }
    std::vector<std::string> names;
    for (js::Config *elem : config->get_elems())
    {
        if (dynamic_cast<js::ConfigString *>(elem) == nullptr || elem->get_str().empty())
        {
            this->trace.fatal("Property %s: not a list of names\n", name);
        }
        names.push_back(elem->get_str());
    }
    return names;
}


// A start: the configuration words, in CSR order, written by the shell
vp::IoReqStatus SnaxUnit::ctrl_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxUnit *_this = (SnaxUnit *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (!req->get_is_write() || req->get_size() != (uint64_t)(4 * _this->nb_config_words))
    {
        _this->trace.force_warning("Unexpected access on ctrl (size: %ld, is_write: %d): a "
            "start is a write of %d words\n", req->get_size(), req->get_is_write(),
            _this->nb_config_words);
        return vp::IO_REQ_INVALID;
    }
    uint32_t count = ((uint32_t *)req->get_data())[0];

    switch (_this->rule.start(cycle, count))
    {
        case SnaxUnitRule::REFUSED:
            _this->trace.force_warning("Start (shell CSRs from %d) refused at cycle %ld: busy\n",
                _this->csr_base, cycle);
            return vp::IO_REQ_DENIED;

        case SnaxUnitRule::IGNORED:
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Start at cycle %ld with count 0: ignored, not busy\n", cycle);
            return vp::IO_REQ_OK;

        default:
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: count %u\n", cycle,
                count);
            if (_this->busy_itf.is_bound())
            {
                _this->busy_itf.sync(true);
            }
            if (!_this->fire_event.is_enqueued())
            {
                _this->fire_event.enqueue(1);
            }
            return vp::IO_REQ_OK;
    }
}


bool SnaxUnit::probe(vp::IoMaster &port, bool is_write)
{
    this->beat_req.init();
    this->beat_req.set_size(0);
    this->beat_req.set_is_write(is_write);
    return port.req(&this->beat_req) == vp::IO_REQ_OK;
}


void SnaxUnit::move(vp::IoMaster &port, bool is_write, uint64_t *beat)
{
    this->beat_req.init();
    this->beat_req.set_size(8 * this->beat_words);
    this->beat_req.set_is_write(is_write);
    this->beat_req.set_data((uint8_t *)beat);
    if (port.req(&this->beat_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("A beat refused after its probe\n");
    }
}


// The op per lane on the beats taken: lane i is bits [i * w, (i + 1) * w)
void SnaxUnit::compute(std::vector<uint64_t> &out)
{
    int w = this->data_width;
    uint64_t mask = w == 64 ? ~(uint64_t)0 : ((uint64_t)1 << w) - 1;
    out.assign(this->beat_words, 0);
    for (int lane = 0; lane < this->lanes; lane++)
    {
        int word = lane * w / 64;
        int shift = lane * w % 64;
        uint64_t a = (this->beat_in[0][word] >> shift) & mask;
        uint64_t b = (this->beat_in[1][word] >> shift) & mask;
        out[word] |= snax_unit_compute(this->op, this->is_signed, w, a, b) << shift;
    }
}


// One busy cycle: probe every port, step the rule, move what it says
void SnaxUnit::fire_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxUnit *_this = (SnaxUnit *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (_this->rule.busy(cycle))
    {
        bool inputs = true;
        for (vp::IoMaster &port : _this->in_itf)
        {
            inputs = _this->probe(port, false) && inputs;
        }
        bool room = _this->probe(_this->out_itf, true);

        SnaxUnitRule::Step step = _this->rule.step(cycle, inputs, room);
        if (step.fire)
        {
            for (size_t i = 0; i < _this->in_itf.size(); i++)
            {
                _this->move(_this->in_itf[i], false, _this->beat_in[i].data());
            }
            _this->results.emplace_back();
            _this->compute(_this->results.back());
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Fire %u\n", _this->rule.firings - 1);
        }
        if (step.push)
        {
            _this->move(_this->out_itf, true, _this->results.front().data());
            _this->results.pop_front();
        }
        if (step.end)
        {
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", _this->rule.run_line().c_str());
            if (_this->busy_itf.is_bound())
            {
                _this->busy_itf.sync(false);
            }
        }
    }

    // Every busy cycle, so it always runs before the streamer's step
    if (_this->rule.busy(cycle + 1))
    {
        _this->fire_event.enqueue(1);
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxUnit(config);
}
