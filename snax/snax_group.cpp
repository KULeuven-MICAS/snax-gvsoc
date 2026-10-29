/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxGroup (snax-forge C§17, D146, D147): one group of accelerator.json, its
// units' datapaths under one control model, generic, every number a property
// read at run time (get_js_config), so a design point compiles nothing. The
// control model is snax_group.hpp's SnaxGroupRule (the `<tag>_<group>_ctrl` of
// snax-forge's Chisel), the datapaths snax_datapath.hpp's classes, wired by
// SnaxGroupDatapaths; this file is the component around them.
//
// Properties (a missing one, a wrong type or a bad value is a fatal error
// naming it):
//   units      the group's units. Each an object:
//                name, datapath     the instance, a catalogue datapath
//                                   (snax_datapath.hpp's registry)
//                inputs             per BRM input, in port order: the outer
//                                   port's name, or "" for an input a link
//                                   feeds (exactly one; a unit of span > 1
//                                   has no outer one)
//                output             the outer output's port name, or ""
//                                   (linked); exactly one unit has one until
//                                   tier A
//                in_widths, in_signed, out_width, out_signed, op_width,
//                op_signed          each input's, the output's and the op's
//                                   element type (snax_types.hpp: 8 to 64
//                                   bits, signed or not)
//                lanes              elements per input beat
//                op                 ElementwiseLanes' op (add ... max); a
//                                   fold's add
//                accumulate, reg_out  Mac's variant
//                latency, ii, span  C§17's timing
//                t                  a result every t-th firing, fixed (1 for a
//                                   unit without a fold, params.T), or 0: a
//                                   fold's JOB_BEATS, from the start
//   links      the edges between the units, each an object: from and to, the
//              producer's and the consumer's names; to_input, the consumer's
//              input it feeds (an index in its inputs, one left ""); depth, 0 a
//              wire, >= 1 a buffer (a LinkBuffer of that many beats). Until
//              tier A the edges are one chain: SnaxGroupRule refuses a fork or
//              a join
//   csr_base   the group's first CSR, for the trace
//
// Ports:
//   <unit>_<port>  io masters to the streamer's reader_<i> and writer_<j>, one
//                  per outer port, each beat its port's words (the mover's
//                  num_channel must match: no FIFO slicer here): a probe
//                  (size 0) of every port, then the beats moved, so nothing
//                  moves unless the rule says so
//   ctrl           io slave: a start, JOBS then the T of each unit with t 0, in
//                  unit order, 32-bit words (a group without one: JOBS and a
//                  word 1, as SnaxShell sends it); refused (DENIED, after a
//                  warning) while busy. JOBS or any T 0 (the empty run, which
//                  the shell never sends) is answered and ignored; a firing
//                  count past 32 bits is a fatal error
//   busy           wire<bool> master, driven on every change, in the cycle the
//                  change is decided: true in the cycle a start is taken (busy
//                  from the next), false in the run's last cycle
//
// Its event runs every busy cycle, so it runs before the streamer's step.
//
// Events (docs/EVENTS.md, snax_events.hpp), at the group's boundary: `start`
// (count, the head's firings, and rate, the head's firings per result of the
// outer output's unit; for one unit JOBS * JOB_BEATS and JOB_BEATS) in the cycle a start
// is taken; `done` (the head's firings, its first and last firing's cycles)
// in the run's last busy cycle; there too, the summary's `run` line
// (SnaxGroupRule::run_line), the classes adding up to the run's busy cycles.
// Beats: `fire` per head firing (its index n, each outer input's beat b as the
// streamer hands it back, -1 if it does not, and the words), `push` per
// result the outer output's unit pushes (its index n, the head's firings it folds, the
// words), and `class` (mode) in the first cycle of each run of one class.
// Per-unit events of a linked group are parked (snax-forge open item 96).
//
// VCD signals (snax_events.hpp, gtkwave only): busy (from s + 1 to E), fire
// and push (the head fires, the outer output's unit pushes), cycle_class (0 idle, 1
// busy, 2 stall_in, 3 stall_out, 4 flush).

#include <algorithm>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_events.hpp"
#include "snax_group.hpp"


class SnaxGroup : public vp::Component
{
public:
    SnaxGroup(vp::ComponentConf &config);

private:
    static vp::IoReqStatus ctrl_req(vp::Block *__this, vp::IoReq *req);
    static void fire_handler(vp::Block *__this, vp::ClockEvent *event);
    void reset(bool active) override;

    js::Config *prop(js::Config *config, const char *name, const std::string &where);
    int int_prop(js::Config *config, const char *name, const std::string &where);
    bool bool_prop(js::Config *config, const char *name, const std::string &where);
    std::string str_prop(js::Config *config, const char *name, const std::string &where);
    std::vector<js::Config *> list_prop(js::Config *config, const char *name,
        const std::string &where);
    SnaxUnitType type_prop(js::Config *config, const char *width, const char *is_signed,
        const std::string &where);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint64_t *beat, int words);

    vp::Trace trace;
    SnaxEvents ev;
    vp::IoSlave ctrl_itf;
    vp::WireMaster<bool> busy_itf;
    vp::ClockEvent fire_event;
    vp::IoReq beat_req;
    SnaxSignals sigs;
    SnaxSignal sig_busy;
    SnaxSignal sig_fire;
    SnaxSignal sig_push;
    SnaxSignal sig_class;

    // An outer input: its port, its unit, its words per beat, the beat taken
    struct OuterIn
    {
        vp::IoMaster itf;
        size_t unit;
        int words;
        std::vector<uint64_t> beat;
    };

    std::vector<OuterIn> in_itf;        // sized once, before any port is registered
    vp::IoMaster out_itf;
    int out_words;
    std::vector<std::vector<size_t>> unit_ins;   // per unit, its outer inputs (in_itf indices)
    // fire_handler's, sized once: per unit whether its outer inputs have a beat and its outer
    // output room, its outer inputs' beats; the outer output's beat
    std::vector<bool> inputs, room;
    std::vector<std::vector<const uint64_t *>> outer;
    std::vector<uint64_t> out_beat;
    std::vector<uint32_t> fixed_t;      // per unit: its t, 0 from the start
    uint32_t csr_base;
    SnaxGroupRule rule;
    SnaxGroupDatapaths data;
    uint32_t rate;                      // the head's firings per result of the outer output's unit
    int64_t first_fire;                 // the run's first and last head firing, for its done line
    int64_t last_fire;
    int line_class;                     // the class of the last class line in this run, -1 none
    uint32_t pushes;                    // results pushed in this run
};


SnaxGroup::SnaxGroup(vp::ComponentConf &config)
    : vp::Component(config),
      fire_event(this, &SnaxGroup::fire_handler),
      sigs(this),
      sig_busy(*this, "busy", 1),
      sig_fire(*this, "fire", 1),
      sig_push(*this, "push", 1),
      sig_class(*this, "cycle_class", 3)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->ev.declare(this);

    std::vector<js::Config *> units = this->list_prop(this->get_js_config(), "units", "");
    if (units.empty())
    {
        this->trace.fatal("Property units: no unit\n");
    }

    // The outer inputs, counted first: in_itf is sized once
    size_t nb_in = 0;
    for (size_t k = 0; k < units.size(); k++)
    {
        for (js::Config *p : this->list_prop(units[k], "inputs", "units[" + std::to_string(k) + "]"))
        {
            nb_in += dynamic_cast<js::ConfigString *>(p) != nullptr && !p->get_str().empty();
        }
    }
    this->in_itf.resize(nb_in);

    std::vector<SnaxGroupRule::UnitCfg> cfgs;
    std::vector<std::string> names;
    std::vector<SnaxDatapathParams> params;
    std::vector<std::vector<int>> linked(units.size());     // per unit, its inputs left ""
    std::string out_name;
    int output = -1;
    size_t at = 0;
    std::string described;
    for (size_t k = 0; k < units.size(); k++)
    {
        std::string w = "units[" + std::to_string(k) + "]";
        js::Config *u = units[k];
        std::string name = this->str_prop(u, "name", w);
        std::string datapath = this->str_prop(u, "datapath", w);
        SnaxDatapathParams p;
        p.lanes = this->int_prop(u, "lanes", w);
        std::vector<js::Config *> ins = this->list_prop(u, "inputs", w);
        std::vector<js::Config *> widths = this->list_prop(u, "in_widths", w);
        std::vector<js::Config *> signs = this->list_prop(u, "in_signed", w);
        if (widths.size() != ins.size() || signs.size() != ins.size())
        {
            this->trace.fatal("Property %s.in_widths, in_signed: one per input (%ld)\n",
                w.c_str(), ins.size());
        }
        this->unit_ins.emplace_back();
        for (size_t i = 0; i < ins.size(); i++)
        {
            int width = widths[i]->get_int();
            if (width != 8 && width != 16 && width != 32 && width != 64)
            {
                this->trace.fatal("Property %s.in_widths[%ld]: %d, must be 8, 16, 32 or 64\n",
                    w.c_str(), i, width);
            }
            p.in_types.push_back({width, signs[i]->get_bool()});
            std::string port = dynamic_cast<js::ConfigString *>(ins[i]) ? ins[i]->get_str() : "";
            if (port.empty())
            {
                linked[k].push_back(i);
                continue;
            }
            OuterIn &o = this->in_itf[at];
            o.unit = k;
            o.words = snax_words(p.lanes, p.in_types.back());
            o.beat.assign(o.words, 0);
            this->new_master_port(port, &o.itf);
            this->unit_ins.back().push_back(at++);
        }
        p.out_type = this->type_prop(u, "out_width", "out_signed", w);
        p.op_type = this->type_prop(u, "op_width", "op_signed", w);
        std::string op = this->str_prop(u, "op", w);
        p.op = -1;
        for (int i = 0; i < UNIT_NB_OPS; i++)
        {
            p.op = op == snax_unit_op_names[i] ? i : p.op;
        }
        if (p.op == -1)
        {
            this->trace.fatal("Property %s.op: \"%s\", not an op (add, sub, mul, and, or, xor, "
                "min, max)\n", w.c_str(), op.c_str());
        }
        p.accumulate = this->bool_prop(u, "accumulate", w);
        p.reg_out = this->bool_prop(u, "reg_out", w);
        std::string why;
        std::unique_ptr<SnaxDatapath> dp = snax_datapath_new(datapath, p, &why);
        if (!dp)
        {
            this->trace.fatal("Property %s.datapath: %s: %s\n", w.c_str(), datapath.c_str(),
                why.c_str());
        }
        SnaxGroupRule::UnitCfg c;
        c.latency = this->int_prop(u, "latency", w);
        c.ii = this->int_prop(u, "ii", w);
        c.span = this->int_prop(u, "span", w);
        if (c.latency != dp->latency || c.ii != 1 || c.span != dp->span)
        {
            this->trace.fatal("Property %s.latency, ii, span: %d, %d, %d; %s is %d, 1, %d\n",
                w.c_str(), c.latency, c.ii, c.span, datapath.c_str(), dp->latency, dp->span);
        }
        if (c.span > 1 && !this->unit_ins.back().empty())
        {
            this->trace.fatal("Property %s.inputs: a unit of span %d reads its input in place: "
                "its input is a link, not a streamer's\n", w.c_str(), c.span);
        }
        cfgs.push_back(c);
        int t = this->int_prop(u, "t", w);
        if (t < 0)
        {
            this->trace.fatal("Property %s.t: %d, must be 0 or more\n", w.c_str(), t);
        }
        this->fixed_t.push_back(t);
        std::string out = this->str_prop(u, "output", w);
        if (!out.empty())
        {
            if (output != -1)
            {
                this->trace.fatal("Property %s.output: \"%s\", but units[%d] has the outer "
                    "output already: until tier A a group has one\n", w.c_str(), out.c_str(),
                    output);
            }
            output = k;
            out_name = out;
            this->out_words = dp->out_words;
        }
        this->data.units.push_back(std::move(dp));
        names.push_back(name);
        params.push_back(p);
        described += (described.empty() ? "" : ", ") + name + " (" + datapath + ", L " +
            std::to_string(c.latency) + ", span " + std::to_string(c.span) + ")";
    }
    if (output == -1)
    {
        this->trace.fatal("Property units: no unit has an outer output (every output \"\"): a "
            "group has one\n");
    }

    // The links: edges from a unit's output into an input of another that is left ""
    std::vector<js::Config *> links = this->list_prop(this->get_js_config(), "links", "");
    std::vector<SnaxGroupRule::Link> edges;
    std::vector<std::vector<int>> fed(units.size());
    for (size_t k = 0; k < units.size(); k++)
    {
        fed[k].assign(params[k].in_types.size(), 0);
    }
    for (size_t i = 0; i < links.size(); i++)
    {
        std::string w = "links[" + std::to_string(i) + "]";
        SnaxGroupRule::Link e;
        int *ends[] = {&e.from, &e.to};
        const char *keys[] = {"from", "to"};
        for (int j = 0; j < 2; j++)
        {
            std::string name = this->str_prop(links[i], keys[j], w);
            *ends[j] = -1;
            for (size_t k = 0; k < names.size(); k++)
            {
                *ends[j] = names[k] == name ? (int)k : *ends[j];
            }
            if (*ends[j] == -1)
            {
                this->trace.fatal("Property %s.%s: \"%s\", no unit of the group\n", w.c_str(),
                    keys[j], name.c_str());
            }
        }
        e.to_input = this->int_prop(links[i], "to_input", w);
        e.depth = this->int_prop(links[i], "depth", w);
        if (e.depth < 0)
        {
            this->trace.fatal("Property %s.depth: %d, must be 0 or more\n", w.c_str(), e.depth);
        }
        const std::vector<int> &open = linked[e.to];
        bool is_open = false;
        for (int x : open)
        {
            is_open = is_open || x == e.to_input;
        }
        if (!is_open || fed[e.to][e.to_input]++)
        {
            this->trace.fatal("Property %s.to_input: %d; units[%d].inputs[%d] is not an input "
                "left \"\", or another link feeds it\n", w.c_str(), e.to_input, e.to, e.to_input);
        }
        const SnaxDatapath *src = this->data.units[e.from].get();
        const SnaxDatapath *dst = this->data.units[e.to].get();
        if (src->out_words != dst->in_words[e.to_input])
        {
            this->trace.fatal("Property %s: the link carries %d words a beat, units[%d].inputs[%d] "
                "takes %d\n", w.c_str(), src->out_words, e.to, e.to_input,
                dst->in_words[e.to_input]);
        }
        std::unique_ptr<SnaxDatapath> buffer;
        if (e.depth > 0)
        {
            SnaxDatapathParams b;
            b.in_types = {params[e.to].in_types[e.to_input]};
            b.out_type = params[e.to].in_types[e.to_input];
            b.lanes = params[e.to].lanes;
            b.depth = e.depth;
            std::string why;
            buffer = snax_datapath_new("LinkBuffer", b, &why);
        }
        this->data.buffers.push_back(std::move(buffer));
        edges.push_back(e);
        described += "; " + names[e.from] + " -> " + names[e.to] + " depth " +
            std::to_string(e.depth);
    }
    for (size_t k = 0; k < units.size(); k++)
    {
        for (int i : linked[k])
        {
            if (!fed[k][i])
            {
                this->trace.fatal("Property units[%ld].inputs[%d]: \"\", but no link feeds it\n",
                    k, i);
            }
        }
    }
    std::string refused = this->rule.configure(cfgs, edges, output);
    if (!refused.empty())
    {
        this->trace.fatal("Property units, links: %s\n", refused.c_str());
    }
    this->data.wire(this->rule);
    this->inputs.assign(units.size(), true);
    this->room.assign(units.size(), true);
    this->outer.assign(units.size(), {});
    for (size_t k = 0; k < units.size(); k++)
    {
        for (size_t i : this->unit_ins[k])
        {
            this->outer[k].push_back(this->in_itf[i].beat.data());
        }
    }
    this->out_beat.assign(this->out_words, 0);
    this->csr_base = this->int_prop(this->get_js_config(), "csr_base", "");

    this->new_master_port(out_name, &this->out_itf);
    this->ctrl_itf.set_req_meth(&SnaxGroup::ctrl_req);
    this->new_slave_port("ctrl", &this->ctrl_itf);
    this->new_master_port("busy", &this->busy_itf);

    this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", described.c_str());
}


void SnaxGroup::reset(bool active)
{
    if (active)
    {
        this->rule.reset();
        this->first_fire = this->last_fire = -1;
        this->pushes = 0;
        this->line_class = -1;
        this->rate = 1;
    }
}


js::Config *SnaxGroup::prop(js::Config *config, const char *name, const std::string &where)
{
    js::Config *value = config->get(name);
    if (value == nullptr)
    {
        this->trace.fatal("Property %s%s%s: missing\n", where.c_str(), where.empty() ? "" : ".",
            name);
    }
    return value;
}


int SnaxGroup::int_prop(js::Config *config, const char *name, const std::string &where)
{
    js::Config *value = this->prop(config, name, where);
    if (dynamic_cast<js::ConfigNumber *>(value) == nullptr)
    {
        this->trace.fatal("Property %s%s%s: not a number\n", where.c_str(),
            where.empty() ? "" : ".", name);
    }
    return value->get_int();
}


bool SnaxGroup::bool_prop(js::Config *config, const char *name, const std::string &where)
{
    js::Config *value = this->prop(config, name, where);
    if (dynamic_cast<js::ConfigBool *>(value) == nullptr)
    {
        this->trace.fatal("Property %s.%s: not a bool\n", where.c_str(), name);
    }
    return value->get_bool();
}


std::string SnaxGroup::str_prop(js::Config *config, const char *name, const std::string &where)
{
    js::Config *value = this->prop(config, name, where);
    if (dynamic_cast<js::ConfigString *>(value) == nullptr)
    {
        this->trace.fatal("Property %s.%s: not a string\n", where.c_str(), name);
    }
    return value->get_str();
}


std::vector<js::Config *> SnaxGroup::list_prop(js::Config *config, const char *name,
    const std::string &where)
{
    js::Config *value = this->prop(config, name, where);
    if (dynamic_cast<js::ConfigArray *>(value) == nullptr)
    {
        this->trace.fatal("Property %s%s%s: not a list\n", where.c_str(), where.empty() ? "" : ".",
            name);
    }
    return value->get_elems();
}


SnaxUnitType SnaxGroup::type_prop(js::Config *config, const char *width, const char *is_signed,
    const std::string &where)
{
    int w = this->int_prop(config, width, where);
    if (w != 8 && w != 16 && w != 32 && w != 64)
    {
        this->trace.fatal("Property %s.%s: %d, must be 8, 16, 32 or 64\n", where.c_str(), width, w);
    }
    return {w, this->bool_prop(config, is_signed, where)};
}


// A start: JOBS, then the T of each unit with t 0, in unit order
vp::IoReqStatus SnaxGroup::ctrl_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxGroup *_this = (SnaxGroup *)__this;
    int64_t cycle = _this->clock.get_cycles();

    size_t open = 0;
    for (uint32_t t : _this->fixed_t)
    {
        open += t == 0;
    }
    size_t words = 1 + (open ? open : 1);
    if (!req->get_is_write() || req->get_size() != 4 * words)
    {
        _this->trace.force_warning("Unexpected access on ctrl (size: %ld, is_write: %d): a "
            "start is a write of %ld words, JOBS and each fold's JOB_BEATS (or 1)\n",
            req->get_size(), req->get_is_write(), words);
        return vp::IO_REQ_INVALID;
    }
    uint32_t *w = (uint32_t *)req->get_data();
    uint32_t jobs = w[0];
    std::vector<uint32_t> ts;
    size_t next = 1;
    for (uint32_t t : _this->fixed_t)
    {
        ts.push_back(t ? t : w[next++]);
    }
    if (!open && w[1] != 1)
    {
        _this->trace.fatal("Start at cycle %ld: job_beats %u; no unit of the group takes one "
            "(1)\n", cycle, w[1]);
    }
    uint64_t n = jobs;
    for (uint32_t t : ts)
    {
        n *= t;
        if (n > UINT32_MAX)
        {
            _this->trace.fatal("Start at cycle %ld: the head's firings are past 32 bits\n",
                cycle);
        }
    }

    switch (_this->rule.start(cycle, jobs, ts))
    {
        case SnaxGroupRule::REFUSED:
            _this->trace.force_warning("Start (shell CSRs from %d) refused at cycle %ld: busy\n",
                _this->csr_base, cycle);
            return vp::IO_REQ_DENIED;

        case SnaxGroupRule::IGNORED:
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Start at cycle %ld with JOBS or a T 0: ignored, not busy\n", cycle);
            return vp::IO_REQ_OK;

        default:
        {
            size_t last = _this->rule.output_unit();
            uint32_t results = _this->rule.counts[last] / _this->rule.beats[last];
            _this->rate = _this->rule.count() / results;
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: JOBS %u, %ld T\n", cycle,
                jobs, ts.size());
            _this->ev.events.msg(vp::Trace::LEVEL_INFO, "%ld start count=%u rate=%u\n",
                (long)cycle, _this->rule.count(), _this->rate);
            _this->first_fire = _this->last_fire = -1;
            _this->pushes = 0;
            _this->line_class = -1;
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
}


bool SnaxGroup::probe(vp::IoMaster &port, bool is_write)
{
    this->beat_req.init();
    this->beat_req.set_size(0);
    this->beat_req.set_is_write(is_write);
    return port.req(&this->beat_req) == vp::IO_REQ_OK;
}


void SnaxGroup::move(vp::IoMaster &port, bool is_write, uint64_t *beat, int words)
{
    this->beat_req.init();
    this->beat_req.set_size(8 * words);
    this->beat_req.set_is_write(is_write);
    this->beat_req.set_data((uint8_t *)beat);
    if (port.req(&this->beat_req) != vp::IO_REQ_OK)
    {
        this->trace.fatal("A beat refused after its probe\n");
    }
}


// One busy cycle: probe every outer port, step the rule, move what it says, run the datapaths
void SnaxGroup::fire_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxGroup *_this = (SnaxGroup *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (_this->rule.busy(cycle))
    {
        std::vector<bool> &inputs = _this->inputs;
        std::fill(inputs.begin(), inputs.end(), true);
        for (OuterIn &o : _this->in_itf)
        {
            inputs[o.unit] = _this->probe(o.itf, false) && inputs[o.unit];
        }
        _this->room[_this->rule.output_unit()] = _this->probe(_this->out_itf, true);

        const SnaxGroupRule::Step &step = _this->rule.step(cycle, inputs, _this->room);
        const SnaxGroupRule::UnitStep &head = step.units[_this->rule.topological().front()];
        const SnaxGroupRule::UnitStep &tail = step.units[_this->rule.output_unit()];
        _this->sigs.set(_this->sig_busy, 1);
        _this->sigs.set(_this->sig_fire, head.fire);
        _this->sigs.set(_this->sig_push, tail.push);
        _this->sigs.set(_this->sig_class, step.cls + 1);
        if (step.cls != _this->line_class)
        {
            _this->line_class = step.cls;
            _this->ev.beats.msg(vp::Trace::LEVEL_INFO, "%ld class mode=%s\n", (long)cycle,
                snax_unit_class_names[step.cls]);
        }

        // The beats of each unit that fires, its outer inputs in port order (outer)
        std::string beats, values;
        bool traced = _this->ev.beats.get_active();
        for (size_t k = 0; k < _this->unit_ins.size(); k++)
        {
            for (size_t i : _this->unit_ins[k])
            {
                OuterIn &o = _this->in_itf[i];
                if (step.units[k].fire)
                {
                    _this->move(o.itf, false, o.beat.data(), o.words);
                    if (traced && k == _this->rule.topological().front())
                    {
                        bool tagged = snax_arg_get(&_this->beat_req, SNAX_ARG_TAG) == SNAX_TAG_BEAT;
                        beats += (beats.empty() ? "" : ",") + std::to_string(tagged
                            ? (long)snax_arg_get(&_this->beat_req, SNAX_ARG_ID) : -1L);
                        for (uint64_t word : o.beat)
                        {
                            values += (values.empty() ? "" : ",") + snax_word((uint8_t *)&word, 8);
                        }
                    }
                }
            }
        }
        if (head.fire)
        {
            if (traced)
            {
                _this->ev.beats.msg(vp::Trace::LEVEL_INFO, "%ld fire n=%u b=%s value=%s\n",
                    (long)cycle, _this->rule.firings() - 1, beats.c_str(), values.c_str());
            }
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Fire %u\n", _this->rule.firings() - 1);
            if (_this->first_fire == -1)
            {
                _this->first_fire = cycle;
            }
            _this->last_fire = cycle;
        }

        const std::vector<uint64_t> &result = _this->data.cycle(step, _this->outer);
        if (tail.push)
        {
            std::vector<uint64_t> &out = _this->out_beat;
            std::copy(result.begin(), result.end(), out.begin());
            _this->move(_this->out_itf, true, out.data(), _this->out_words);
            if (_this->ev.beats.get_active())
            {
                std::string text;
                for (uint64_t word : out)
                {
                    text += (text.empty() ? "" : ",") + snax_word((uint8_t *)&word, 8);
                }
                uint32_t first = _this->pushes * _this->rate;
                _this->ev.beats.msg(vp::Trace::LEVEL_INFO,
                    "%ld push n=%u first=%u last=%u value=%s\n", (long)cycle, _this->pushes,
                    first, first + _this->rate - 1, text.c_str());
            }
            _this->pushes++;
        }
        if (step.end)
        {
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", _this->rule.run_line().c_str());
            _this->ev.events.msg(vp::Trace::LEVEL_INFO,
                "%ld done firings=%u first=%ld last=%ld\n", (long)cycle, _this->rule.firings(),
                (long)_this->first_fire, (long)_this->last_fire);
            if (_this->ev.summary.get_active())
            {
                _this->ev.summary.msg(vp::Trace::LEVEL_INFO, "%ld %s\n", (long)cycle,
                    _this->rule.run_line().c_str());
            }
            if (_this->busy_itf.is_bound())
            {
                _this->busy_itf.sync(false);
            }
            for (SnaxSignal *s : {&_this->sig_busy, &_this->sig_fire, &_this->sig_push,
                &_this->sig_class})
            {
                _this->sigs.set_from(*s, 0, cycle + 1);
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
    return new SnaxGroup(config);
}
