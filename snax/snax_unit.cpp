/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxUnit (D134 in snax-forge): the datapath of one of snax-forge's Chisel
// blocks, generic, every number a property read at run time (get_js_config),
// so a design point compiles nothing. The cycle rule and the op table are in
// snax_unit.hpp; this file is the component around them.
//
// Properties (a missing one, a wrong type or a bad value is a fatal error
// naming it):
//   inputs, outputs  port names (lists of strings): one output, and two
//                    inputs (the op on each pair of beats) or one (a fold:
//                    x is the beat's lanes reduced by op through a tree,
//                    snax_unit_tree, and the output's value is op(acc, x)
//                    over the firings of one output, acc starting from the
//                    first x; the output one element)
//   lanes            elements per input beat (> 0)
//   in_widths, in_signed, out_widths, out_signed
//                    each port's element type (snax_unit.hpp's
//                    SnaxUnitType): its width, 8, 16, 32 or 64, and whether
//                    it is signed (bools), one per input in inputs' order
//                    and one per output. All four, or none: then data_width
//                    and signed give every port. An input of width b takes
//                    lanes * b / 64 channel words, which must be whole, and
//                    the inputs may differ; an elementwise output of width
//                    b_o lanes * b_o / 64, also whole; a fold's output one
//                    word for any b_o, the element in its low b_o bits. The
//                    streamer's beats are whole 64-bit channel words, lane
//                    0 first (snax_streamer.cpp); the elements are packed in
//                    them b bits apart, lane 0 lowest, as Chisel packs a Vec
//   data_width       without the four: every port's width
//   signed           without the four: every port's signedness (bool)
//   op               ElementwiseOp's encoding: add 0, sub 1, mul 2, and 3,
//                    or 4, xor 5, min 6, max 7; integers, as NumPy: an
//                    elementwise op at the inputs' result type T (a
//                    signed type with uint64 has none and is refused;
//                    NumPy gives float64), wrapping, then
//                    cast to the output's type; a fold's lanes cast to the
//                    output's type, the tree and acc at it (snax_unit.hpp)
//   control          counted: the unit counts its firings
//   config           the role of each 32-bit configuration word the shell
//                    sends, in order: count (the firings of the run, once)
//                    and rate (firings per output, at most once; 1 without
//                    it). A start with count or rate 0 is ignored; a count
//                    not a multiple of the rate is a fatal error. rate needs
//                    a fold and pipelined
//   wait             lockstep or pipelined (snax_unit.hpp)
//   latency, ii      pipelined: L >= 0 and II >= 1; lockstep: 0 and 1
//   csr_base         the shell's first CSR, for the trace
//
// Ports:
//   <input>, <output>  io masters to the streamer's reader_<i> and writer_<j>,
//                      each beat its port's words (the reader's or writer's
//                      num_channel must match: no FIFO slicer here):
//                      a probe (size 0) of every port, then the beats moved
//                      (the ALU shell's way, before CLN1), so nothing moves unless the
//                      rule says so
//   ctrl               io slave: a write of the configuration words in CSR
//                      order starts a run in that cycle; refused (DENIED, after
//                      a warning) while busy. A count or rate of 0 is answered
//                      and ignored
//   busy               wire<bool> master, driven on every change, in the cycle
//                      the change is decided: true in the cycle a start is
//                      taken (busy from the next), false in the run's last
//                      cycle (idle from the next)
//
// Its event runs every busy cycle, scheduled as the ALU shell's was, so it
// runs before the streamer's step in a cycle.
//
// Events (docs/EVENTS.md, snax_events.hpp): `start` (count, rate) in the cycle
// a start is taken; `done` (firings, the first and last firing's cycles) in
// the run's last busy cycle; there too, the summary's `run` line
// (SnaxUnitRule::run_line), the classes adding up to the run's busy cycles.
// Beats: `fire` per firing (its index n in the run, each input's beat b as
// the streamer hands it back, -1 if it does not, and the input words), `push`
// per result pushed (its index n among the run's results, the firings it
// folds, the output words), and `class` (mode) in the first cycle of each run
// of one class: the rule's class per busy cycle, the one the run line counts.
//
// VCD signals (snax_events.hpp, gtkwave only): busy (from s + 1 to E), fire
// and push (1 in a cycle the unit fires, pushes), cycle_class (0 idle, 1 busy,
// 2 stall_in, 3 stall_out, 4 flush; snax_unit.hpp's classes plus one).

#include <deque>
#include <tuple>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_events.hpp"
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
    std::vector<int> ints_prop(const char *name);
    std::vector<bool> bools_prop(const char *name);
    void types_prop(size_t nb_inputs);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint64_t *beat, int words);
    void compute(std::vector<uint64_t> &out);
    void fold(bool first);

    vp::Trace trace;
    SnaxEvents ev;
    vp::IoSlave ctrl_itf;
    vp::WireMaster<bool> busy_itf;
    std::vector<vp::IoMaster> in_itf;
    vp::IoMaster out_itf;
    vp::ClockEvent fire_event;
    vp::IoReq beat_req;
    SnaxSignals sigs;
    SnaxSignal sig_busy;
    SnaxSignal sig_fire;
    SnaxSignal sig_push;
    SnaxSignal sig_class;

    int lanes;
    int op;
    bool is_fold;               // one input
    std::vector<SnaxUnitType> in_types;     // per input
    SnaxUnitType out_type;
    std::vector<int> in_words;  // 64-bit words per beat, per input
    int out_words;              // per output beat: lanes * its width / 64, 1 for a fold
    int nb_config_words;        // the ctrl write's words
    int count_word;             // the count's word in it
    int rate_word;              // the rate's, -1 without one
    uint32_t csr_base;
    SnaxUnitRule rule;
    int64_t first_fire;         // the run's first and last firing, for its done line
    int64_t last_fire;
    int line_class;             // the class of the last class line in this run, -1 none

    // A result computed and not pushed yet: its words and the firings it folds
    struct Result
    {
        std::vector<uint64_t> words;
        uint32_t first;
        uint32_t last;
    };

    std::vector<std::vector<uint64_t>> beat_in;   // per input, the beat taken
    std::vector<uint64_t> acc;                    // a fold's output so far, one word
    std::deque<Result> results;
    uint32_t pushes;                              // results pushed in this run
};


SnaxUnit::SnaxUnit(vp::ComponentConf &config)
    : vp::Component(config),
      fire_event(this, &SnaxUnit::fire_handler),
      sigs(this),
      sig_busy(*this, "busy", 1),
      sig_fire(*this, "fire", 1),
      sig_push(*this, "push", 1),
      sig_class(*this, "cycle_class", 3)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->ev.declare(this);

    std::vector<std::string> inputs = this->names_prop("inputs");
    std::vector<std::string> outputs = this->names_prop("outputs");
    if (inputs.size() != 1 && inputs.size() != 2)
    {
        this->trace.fatal("Property inputs: %ld names, one (a fold) or two (the op table)\n",
            inputs.size());
    }
    this->is_fold = inputs.size() == 1;
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
    this->types_prop(inputs.size());

    this->op = this->int_prop("op");
    if (this->op < 0 || this->op >= UNIT_NB_OPS)
    {
        this->trace.fatal("Property op: %d, not an ElementwiseOp encoding (0 to %d)\n", this->op,
            UNIT_NB_OPS - 1);
    }

    std::string control = this->str_prop("control");
    if (control != "counted")
    {
        this->trace.fatal("Property control: unknown kind \"%s\" (counted)\n", control.c_str());
    }
    std::vector<std::string> roles = this->names_prop("config");
    this->nb_config_words = roles.size();
    this->count_word = this->rate_word = -1;
    for (size_t i = 0; i < roles.size(); i++)
    {
        int *word = roles[i] == "count" ? &this->count_word :
            roles[i] == "rate" ? &this->rate_word : nullptr;
        if (word == nullptr)
        {
            this->trace.fatal("Property config: unknown role \"%s\" (count, rate)\n",
                roles[i].c_str());
        }
        if (*word != -1)
        {
            this->trace.fatal("Property config: \"%s\" twice\n", roles[i].c_str());
        }
        *word = i;
    }
    if (this->count_word == -1)
    {
        this->trace.fatal("Property config: no \"count\"\n");
    }

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
    if (this->rate_word != -1 && (!this->is_fold || wait != "pipelined"))
    {
        this->trace.fatal("Property config: \"rate\" needs a fold (one input) and wait "
            "pipelined\n");
    }
    this->csr_base = this->int_prop("csr_base");

    this->beat_in.resize(inputs.size());
    for (size_t i = 0; i < inputs.size(); i++)
    {
        this->beat_in[i].assign(this->in_words[i], 0);
    }
    this->acc.assign(this->out_words, 0);

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

    std::string types;
    for (SnaxUnitType t : this->in_types)
    {
        types += (types.empty() ? "" : " x ") + snax_unit_type_name(t);
    }
    types += " -> " + snax_unit_type_name(this->out_type);
    this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s%s, %d lanes, %s, %s, latency %d, ii %d\n",
        snax_unit_op_names[this->op], this->is_fold ? " fold" : "", this->lanes, types.c_str(),
        wait.c_str(), latency, ii);
}


// The ports' types: in_widths, in_signed, out_widths and out_signed, or
// data_width and signed for every port; then each port's words
void SnaxUnit::types_prop(size_t nb_inputs)
{
    static const char *const keys[] = {"in_widths", "in_signed", "out_widths", "out_signed"};
    int given = 0;
    for (const char *key : keys)
    {
        given += this->get_js_config()->get(key) != nullptr;
    }
    if (given != 0 && given != 4)
    {
        for (const char *key : keys)
        {
            if (this->get_js_config()->get(key) == nullptr)
            {
                this->trace.fatal("Property %s: missing; in_widths, in_signed, out_widths and "
                    "out_signed go together (without them, data_width and signed give every "
                    "port)\n", key);
            }
        }
    }

    // The property a port's width or signedness came from, for the messages
    bool shorthand = given == 0;
    auto width_key = [&](bool out, size_t i) {
        return shorthand ? std::string("data_width")
            : std::string(out ? "out_widths[" : "in_widths[") + std::to_string(i) + "]";
    };
    std::vector<int> in_widths, out_widths;
    std::vector<bool> in_signed, out_signed;
    if (shorthand)
    {
        int width = this->int_prop("data_width");
        js::Config *is_signed = this->prop("signed");
        if (dynamic_cast<js::ConfigBool *>(is_signed) == nullptr)
        {
            this->trace.fatal("Property signed: not a bool\n");
        }
        in_widths.assign(nb_inputs, width);
        in_signed.assign(nb_inputs, is_signed->get_bool());
        out_widths.assign(1, width);
        out_signed.assign(1, is_signed->get_bool());
    }
    else
    {
        in_widths = this->ints_prop("in_widths");
        in_signed = this->bools_prop("in_signed");
        out_widths = this->ints_prop("out_widths");
        out_signed = this->bools_prop("out_signed");
        for (auto [key, n, want, what] : {
            std::make_tuple("in_widths", in_widths.size(), nb_inputs, "input"),
            std::make_tuple("in_signed", in_signed.size(), nb_inputs, "input"),
            std::make_tuple("out_widths", out_widths.size(), (size_t)1, "output"),
            std::make_tuple("out_signed", out_signed.size(), (size_t)1, "output")})
        {
            if (n != want)
            {
                this->trace.fatal("Property %s: %ld values, one per %s (%ld)\n", key, n, what,
                    want);
            }
        }
    }

    for (size_t i = 0; i <= nb_inputs; i++)
    {
        bool out = i == nb_inputs;
        int width = out ? out_widths[0] : in_widths[i];
        std::string key = width_key(out, out ? 0 : i);
        if (width != 8 && width != 16 && width != 32 && width != 64)
        {
            this->trace.fatal("Property %s: %d, must be 8, 16, 32 or 64\n", key.c_str(), width);
        }
        // A fold's output is one word, whatever its width
        if (!(out && this->is_fold) && this->lanes * width % 64 != 0)
        {
            this->trace.fatal("Property %s: lanes %d x %d bits is not a whole number of the "
                "streamer's 64-bit channel words\n", key.c_str(), this->lanes, width);
        }
    }

    this->in_types.clear();
    this->in_words.clear();
    for (size_t i = 0; i < nb_inputs; i++)
    {
        this->in_types.push_back({in_widths[i], in_signed[i]});
        this->in_words.push_back(this->lanes * in_widths[i] / 64);
    }
    this->out_type = {out_widths[0], out_signed[0]};
    this->out_words = this->is_fold ? 1 : this->lanes * out_widths[0] / 64;

    SnaxUnitType t;
    if (!this->is_fold && !snax_unit_result_type(this->in_types[0], this->in_types[1], &t))
    {
        this->trace.fatal("Property in_signed: %s with %s has no integer result type (NumPy "
            "gives float64)\n", snax_unit_type_name(this->in_types[0]).c_str(),
            snax_unit_type_name(this->in_types[1]).c_str());
    }
}


void SnaxUnit::reset(bool active)
{
    if (active)
    {
        this->rule.reset();
        this->results.clear();
        this->first_fire = this->last_fire = -1;
        this->pushes = 0;
        this->line_class = -1;
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


std::vector<int> SnaxUnit::ints_prop(const char *name)
{
    js::Config *config = this->prop(name);
    if (dynamic_cast<js::ConfigArray *>(config) == nullptr)
    {
        this->trace.fatal("Property %s: not a list of numbers\n", name);
    }
    std::vector<int> values;
    for (js::Config *elem : config->get_elems())
    {
        if (dynamic_cast<js::ConfigNumber *>(elem) == nullptr)
        {
            this->trace.fatal("Property %s: not a list of numbers\n", name);
        }
        values.push_back(elem->get_int());
    }
    return values;
}


std::vector<bool> SnaxUnit::bools_prop(const char *name)
{
    js::Config *config = this->prop(name);
    if (dynamic_cast<js::ConfigArray *>(config) == nullptr)
    {
        this->trace.fatal("Property %s: not a list of bools\n", name);
    }
    std::vector<bool> values;
    for (js::Config *elem : config->get_elems())
    {
        if (dynamic_cast<js::ConfigBool *>(elem) == nullptr)
        {
            this->trace.fatal("Property %s: not a list of bools\n", name);
        }
        values.push_back(elem->get_bool());
    }
    return values;
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
    uint32_t *words = (uint32_t *)req->get_data();
    uint32_t count = words[_this->count_word];
    uint32_t rate = _this->rate_word == -1 ? 1 : words[_this->rate_word];
    if (count != 0 && rate != 0 && count % rate != 0)
    {
        _this->trace.fatal("Start at cycle %ld: count %u is not a multiple of rate %u\n", cycle,
            count, rate);
    }

    switch (_this->rule.start(cycle, count, rate))
    {
        case SnaxUnitRule::REFUSED:
            _this->trace.force_warning("Start (shell CSRs from %d) refused at cycle %ld: busy\n",
                _this->csr_base, cycle);
            return vp::IO_REQ_DENIED;

        case SnaxUnitRule::IGNORED:
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Start at cycle %ld with %s 0: ignored, not busy\n", cycle,
                count == 0 ? "count" : "rate");
            return vp::IO_REQ_OK;

        default:
            if (_this->rate_word == -1)
            {
                _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: count %u\n", cycle,
                    count);
            }
            else
            {
                _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: count %u, rate %u\n",
                    cycle, count, rate);
            }
            _this->ev.events.msg(vp::Trace::LEVEL_INFO, "%ld start count=%u rate=%u\n",
                (long)cycle, count, rate);
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


bool SnaxUnit::probe(vp::IoMaster &port, bool is_write)
{
    this->beat_req.init();
    this->beat_req.set_size(0);
    this->beat_req.set_is_write(is_write);
    return port.req(&this->beat_req) == vp::IO_REQ_OK;
}


void SnaxUnit::move(vp::IoMaster &port, bool is_write, uint64_t *beat, int words)
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


// The op per lane on the beats taken (snax_unit_elementwise)
void SnaxUnit::compute(std::vector<uint64_t> &out)
{
    out.assign(this->out_words, 0);
    snax_unit_elementwise(this->op, this->lanes, this->in_types[0], this->in_types[1],
        this->out_type, this->beat_in[0].data(), this->beat_in[1].data(), out.data());
}


// A fold's firing: the beat taken, its lanes through the tree, starts the
// output's value or is folded into it (snax_unit_fold)
void SnaxUnit::fold(bool first)
{
    this->acc[0] = snax_unit_fold(this->op, this->lanes, this->in_types[0], this->out_type,
        this->beat_in[0].data(), first, this->acc[0]);
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
        _this->sigs.set(_this->sig_busy, 1);
        _this->sigs.set(_this->sig_fire, step.fire);
        _this->sigs.set(_this->sig_push, step.push);
        _this->sigs.set(_this->sig_class, step.cls + 1);
        if (step.cls != _this->line_class)
        {
            _this->line_class = step.cls;
            _this->ev.beats.msg(vp::Trace::LEVEL_INFO, "%ld class mode=%s\n", (long)cycle,
                snax_unit_class_names[step.cls]);
        }
        if (step.fire)
        {
            uint32_t n = _this->rule.firings - 1;
            bool traced = _this->ev.beats.get_active();
            std::string beats, values;
            for (size_t i = 0; i < _this->in_itf.size(); i++)
            {
                _this->move(_this->in_itf[i], false, _this->beat_in[i].data(),
                    _this->in_words[i]);
                if (!traced)
                {
                    continue;
                }
                bool tagged = snax_arg_get(&_this->beat_req, SNAX_ARG_TAG) == SNAX_TAG_BEAT;
                beats += (i > 0 ? "," : "") + std::to_string(tagged
                    ? (long)snax_arg_get(&_this->beat_req, SNAX_ARG_ID) : -1L);
                for (uint64_t word : _this->beat_in[i])
                {
                    values += (values.empty() ? "" : ",") + snax_word((uint8_t *)&word, 8);
                }
            }
            if (traced)
            {
                _this->ev.beats.msg(vp::Trace::LEVEL_INFO, "%ld fire n=%u b=%s value=%s\n",
                    (long)cycle, n, beats.c_str(), values.c_str());
            }
            if (_this->is_fold)
            {
                _this->fold(n % _this->rule.rate == 0);
                if (step.result)
                {
                    _this->results.push_back({_this->acc, n + 1 - _this->rule.rate, n});
                }
            }
            else
            {
                _this->results.push_back({{}, n, n});
                _this->compute(_this->results.back().words);
            }
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Fire %u\n", _this->rule.firings - 1);
            if (_this->first_fire == -1)
            {
                _this->first_fire = cycle;
            }
            _this->last_fire = cycle;
        }
        if (step.push)
        {
            Result &result = _this->results.front();
            _this->move(_this->out_itf, true, result.words.data(), _this->out_words);
            if (_this->ev.beats.get_active())
            {
                std::string values;
                for (uint64_t word : result.words)
                {
                    values += (values.empty() ? "" : ",") + snax_word((uint8_t *)&word, 8);
                }
                _this->ev.beats.msg(vp::Trace::LEVEL_INFO,
                    "%ld push n=%u first=%u last=%u value=%s\n", (long)cycle, _this->pushes,
                    result.first, result.last, values.c_str());
            }
            _this->pushes++;
            _this->results.pop_front();
        }
        if (step.end)
        {
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", _this->rule.run_line().c_str());
            _this->ev.events.msg(vp::Trace::LEVEL_INFO,
                "%ld done firings=%u first=%ld last=%ld\n", (long)cycle, _this->rule.firings,
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
    return new SnaxUnit(config);
}
