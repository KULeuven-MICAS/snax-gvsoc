/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxGroup: one group of accelerator.json, its
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
//                                   has no outer one but its seed); a name
//                                   several units give is a forked input,
//                                   one reader's for the heads of
//                                   their chains, alike on each (never a seed)
//                seed               the index in inputs of a fold's seed (the
//                                   last, an outer port, taken once per job:
//                                   one element in one word, a Mac's its
//                                   output's lanes), or -1
//                output             the outer output's port name, or ""
//                                   (linked); each chain's sink has one
//                in_widths, in_signed, out_width, out_signed, op_width,
//                op_signed          each input's, the output's and the op's
//                                   element type (snax_types.hpp: 8 to 64
//                                   bits, signed or not)
//                lanes              elements per input beat
//                d_in               optional, per input: an outer input's pops
//                                   per 64-bit word, through a slicer when
//                                   above 1 (2, 4 or 8, lanes x width x d_in
//                                   = 64 bits); absent, 1 for each
//                broadcast          optional, per input: an outer input read
//                                   as one lane a beat and given to all lanes
//                                   (snax_group.hpp's snax_broadcast), so
//                                   its words and d_in count one lane; never
//                                   the seed, linked only when held; absent,
//                                   false
//                hold               optional, per input: a broadcast input
//                                   of a bank, read once a row and kept:
//                                   its beat moved only on a row's first firing
//                                   (the rule's take), the unit using the beat
//                                   it holds on the others; outer, or a held
//                                   link's (its one-lane beat popped into the
//                                   hold register); never the seed or forked;
//                                   absent, false
//                rows               optional: a Mac's bank rows R, its
//                                   ROWS from the start; absent, 1
//                carry              optional: its seed is carried, the
//                                   unit's own output: taken every job, its
//                                   value given as 0 while the job is below
//                                   CARRY, from the start; absent, false
//                op                 SimdLanes' op (add ... max, or axpby);
//                                   a fold's add
//                k                  SimdLanes' constant at one stream,
//                                   decimal ("0", "-3"), its second operand
//                                   at opType for every lane; "" at two
//                k1, k2             axpby's baked k1 and k2, decimal; ""
//                                   when not baked
//                scalars            the slots read from CSRs (k at one
//                                   stream, k1, k2), in CSR order, each
//                                   [slot, words]: 1 word, or 2 at 64 bits
//                                   (low first), sent at each start
//                accumulate, reg_out  Mac's variant
//                latency, ii, span  the unit's timing
//                t                  a result every t-th firing, fixed (1 for a
//                                   unit without a fold, params.T), or 0: a
//                                   fold's JOB_BEATS, from the start
//   links      the edges between the units, each an object: from and to, the
//              producer's and the consumer's names; to_input, the consumer's
//              input it feeds (an index in its inputs, one left ""); depth, 0 a
//              wire, >= 1 a buffer (a LinkBuffer of that many beats); hold,
//              optional, true into a held input (a buffer of one-lane beats,
//              taken once a bank row). The edges are chains, joined by the
//              forked inputs: SnaxGroupRule refuses a fork or a join of links,
//              and chains no fork joins
//   fork_links optional: a fork's buffered branches, each an object: fork, the
//              forked input's port name (its reader's); to and to_input, the
//              consumer (after every unit of the fork) and its input left "";
//              depth >= 1, the LinkBuffer the fork's taken beats enter, one an
//              entry, popped by the consumer's firings (snax_group.hpp)
//   csr_base   the group's first CSR, for the trace
//
// Ports:
//   <unit>_<port>  io masters to the streamer's reader_<i> and writer_<j>, one
//                  per outer port, each beat its port's words (the mover's
//                  num_channel must match), or one word for a sliced input
//                  (d_in above 1) or a packed output (d_out above 1): a probe
//                  (size 0) of every port, then the beats moved, so nothing
//                  moves unless the rule says so; a sliced input's reader is
//                  probed and moved only when its slicer takes a word; a
//                  forked input's beat is moved once, when all its units fire
//   ctrl           io slave: a start, a JOBS per output (each chain's, in the
//                  outputs' unit order) then the T of each unit with t 0, in
//                  unit order, 32-bit words (a group without one: the JOBS and a
//                  word 1, as SnaxShell sends it), then per unit in unit order
//                  its ROWS (a bank's: 1 to rows, dividing its T), its CARRY (a
//                  carried seed's) and its scalars' words, in CSR order, the
//                  scalars setting their slots; refused (DENIED, after a
//                  warning) while busy. A JOBS or any T 0 (the empty run, which
//                  the shell never sends) is answered and ignored; a firing
//                  count past 32 bits is a fatal error
//   busy           wire<bool> master, driven on every change, in the cycle the
//                  change is decided: true in the cycle a start is taken (busy
//                  from the next), false in the run's last cycle
//   mark           wire<uint32_t> slave, core 0's writes to CSR 0x7C5: a snapshot
//                  of the counters, running totals since boot (the run lines'
//                  classes and every unit's firings and pushes), as snap lines;
//                  the end of the simulation takes the last one, mark -1
//
// Its event runs every busy cycle, so it runs before the streamer's step.
//
// Events, fire, push and class lines and VCD signals: docs/EVENTS.md. Per-unit
// events of a linked group are not written yet.

#include <algorithm>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_events.hpp"
#include "snax_group.hpp"
#include "snax_props.hpp"


class SnaxGroup : public vp::Component
{
public:
    SnaxGroup(vp::ComponentConf &config);

private:
    static vp::IoReqStatus ctrl_req(vp::Block *__this, vp::IoReq *req);
    static void cycle_handler(vp::Block *__this, vp::ClockEvent *event);
    static void mark_sync(vp::Block *__this, uint32_t mark);
    void reset(bool active) override;
    void stop() override;
    // The counters as snap lines, mark the snapshot's (-1 at the end)
    void snap(int64_t mark);

    SnaxType type_prop(js::Config *config, const char *width, const char *is_signed,
        const std::string &where);
    bool probe(vp::IoMaster &port, bool is_write);
    void move(vp::IoMaster &port, bool is_write, uint64_t *beat, int words);

    vp::Trace trace;
    SnaxProps props;
    SnaxEvents ev;
    vp::IoSlave ctrl_itf;
    vp::WireMaster<bool> busy_itf;
    vp::WireSlave<uint32_t> mark_itf;
    vp::ClockEvent cycle_event;
    vp::IoReq beat_req;
    SnaxSignals sigs;
    SnaxSignal sig_busy;
    SnaxSignal sig_fire;
    SnaxSignal sig_push;
    SnaxSignal sig_class;

    // An outer input: its port, its units (two or more: a forked input), its words per
    // beat, the beat taken, and whether it is the unit's seed (taken once per job); with d_in
    // above 1 its slicer, the beat its slice, and the beat id of the word it holds (-1
    // untagged); a broadcast's type, the unit's lanes and the unit's beat, the beat's lane 0
    // in each lane; the beat id taken this cycle (-1 none)
    struct OuterIn
    {
        vp::IoMaster itf;
        std::string name;
        std::vector<size_t> units;
        int words;
        std::vector<uint64_t> beat;
        bool seed = false;
        SnaxSlicer slicer;
        long word_id = -1;
        bool broadcast = false;
        bool hold = false;      // held for a bank row: moved on the rule's take
        SnaxType type = {64, true};
        int lanes = 1;
        std::vector<uint64_t> wide;
        long id = -1;
    };

    // An outer output: its port, its unit (a chain's sink), its words per beat and beat; per
    // run its results, the head's firings per result (rate) and its pushes; its packer, at
    // d_out 1 none (snax_group.hpp)
    struct OuterOut
    {
        vp::IoMaster itf;
        std::string name;
        size_t unit;
        int words;
        std::vector<uint64_t> beat;
        uint32_t results = 0;
        uint32_t rate = 1;
        uint32_t pushes = 0;
        SnaxPacker packer;
    };

    std::vector<OuterIn> in_itf;        // sized once, before any port is registered
    std::vector<OuterOut> out_itf;      // the same, in unit order: the start's JOBS order
    std::vector<std::vector<size_t>> unit_ins;   // per unit, its outer inputs (in_itf indices)
    // cycle_handler's, sized once: per unit whether its outer inputs have a beat and its outer
    // output room, its outer inputs' beats
    std::vector<bool> inputs, seeds, holds, room;
    std::vector<std::vector<const uint64_t *>> outer;
    std::vector<uint32_t> fixed_t;      // per unit: its t, 0 from the start
    std::vector<int> bank_rows;         // per unit: its bank's rows R, 1 without
    std::vector<bool> carried;          // per unit: its seed is carried
    std::vector<uint32_t> carry_jobs;   // per unit: its CARRY, from the start
    // per unit, its slots read from CSRs, each (slot, words), in CSR order
    std::vector<std::vector<std::pair<std::string, int>>> scalars;
    size_t scalar_words = 0;            // their words, summed: a start's last ones
    uint32_t csr_base;
    SnaxGroupRule rule;
    SnaxGroupDatapaths data;
    int64_t first_fire;                 // the run's first and last head firing, for its done line
    int64_t last_fire;
    int line_class;                     // the class of the last class line in this run, -1 none

    // The snapshots' counters since boot: the busy cycles per class, and per unit (named as
    // in accelerator.json) its firings and its pushes
    int64_t total_classes[SnaxGroupRule::NB_CLASSES];
    std::vector<std::string> unit_names;
    std::vector<int64_t> unit_firings;
    std::vector<int64_t> unit_pushes;
};


SnaxGroup::SnaxGroup(vp::ComponentConf &config)
    : vp::Component(config),
      props(&this->trace),
      cycle_event(this, &SnaxGroup::cycle_handler),
      sigs(this),
      sig_busy(*this, "busy", 1),
      sig_fire(*this, "fire", 1),
      sig_push(*this, "push", 1),
      sig_class(*this, "cycle_class", 3)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->ev.declare(this);

    std::vector<js::Config *> units = this->props.list_prop(this->get_js_config(), "units", "");
    if (units.empty())
    {
        this->trace.fatal("Property units: no unit\n");
    }

    // The outer ports, counted first: in_itf and out_itf are sized once. A name two units
    // give is one input, forked
    std::vector<std::string> in_names;
    size_t nb_out = 0;
    for (size_t k = 0; k < units.size(); k++)
    {
        std::string w = "units[" + std::to_string(k) + "]";
        for (js::Config *p : this->props.list_prop(units[k], "inputs", w))
        {
            std::string name = dynamic_cast<js::ConfigString *>(p) ? p->get_str() : "";
            if (!name.empty() && std::find(in_names.begin(), in_names.end(), name) ==
                in_names.end())
            {
                in_names.push_back(name);
            }
        }
        nb_out += !this->props.str_prop(units[k], "output", w).empty();
    }
    this->in_itf.resize(in_names.size());
    this->out_itf.resize(nb_out);

    std::vector<SnaxGroupRule::UnitCfg> cfgs;
    std::vector<std::string> names;
    std::vector<SnaxDatapathParams> params;
    std::vector<std::vector<int>> linked(units.size());     // per unit, its inputs left ""
    std::vector<std::vector<bool>> held_link(units.size()); // per unit and input: a held link's
    std::vector<int> outputs;
    size_t at = 0;
    std::string described;
    for (size_t k = 0; k < units.size(); k++)
    {
        std::string w = "units[" + std::to_string(k) + "]";
        js::Config *u = units[k];
        std::string name = this->props.str_prop(u, "name", w);
        std::string datapath = this->props.str_prop(u, "datapath", w);
        SnaxDatapathParams p;
        p.lanes = this->props.int_prop(u, "lanes", w);
        std::vector<js::Config *> ins = this->props.list_prop(u, "inputs", w);
        std::vector<js::Config *> widths = this->props.list_prop(u, "in_widths", w);
        std::vector<js::Config *> signs = this->props.list_prop(u, "in_signed", w);
        if (widths.size() != ins.size() || signs.size() != ins.size())
        {
            this->trace.fatal("Property %s.in_widths, in_signed: one per input (%ld)\n",
                w.c_str(), ins.size());
        }
        this->unit_ins.emplace_back();
        int seed = this->props.int_prop(u, "seed", w);
        if (seed != -1 && seed != (int)ins.size() - 1)
        {
            this->trace.fatal("Property %s.seed: %d; a fold's seed is its last input (%ld), or "
                "-1\n", w.c_str(), seed, ins.size() - 1);
        }
        p.seed = seed != -1;
        js::Config *d_ins = u->get("d_in");
        std::vector<js::Config *> slices = d_ins ? this->props.as_list(d_ins, w + ".d_in")
            : std::vector<js::Config *>();
        if (d_ins && slices.size() != ins.size())
        {
            this->trace.fatal("Property %s.d_in: one per input (%ld)\n", w.c_str(), ins.size());
        }
        js::Config *bcasts = u->get("broadcast");
        std::vector<js::Config *> wired = bcasts ? this->props.as_list(bcasts, w + ".broadcast")
            : std::vector<js::Config *>();
        if (bcasts && wired.size() != ins.size())
        {
            this->trace.fatal("Property %s.broadcast: one per input (%ld)\n", w.c_str(),
                ins.size());
        }
        js::Config *holds = u->get("hold");
        std::vector<js::Config *> kept = holds ? this->props.as_list(holds, w + ".hold")
            : std::vector<js::Config *>();
        if (holds && kept.size() != ins.size())
        {
            this->trace.fatal("Property %s.hold: one per input (%ld)\n", w.c_str(), ins.size());
        }
        js::Config *rows_prop = u->get("rows");
        p.rows = rows_prop ? this->props.as_int(rows_prop, w + ".rows") : 1;
        if (p.rows < 1)
        {
            this->trace.fatal("Property %s.rows: %d; a bank has one row or more\n", w.c_str(),
                p.rows);
        }
        js::Config *carry_prop = u->get("carry");
        bool carry = carry_prop && this->props.as_bool(carry_prop, w + ".carry");
        if (carry && seed == -1)
        {
            this->trace.fatal("Property %s.carry: true, but the unit has no seed; a carried "
                "port is a fold's seed: carry false, or give the unit its seed\n", w.c_str());
        }
        this->bank_rows.push_back(p.rows);
        this->carried.push_back(carry);
        bool held = false;
        for (size_t i = 0; i < ins.size(); i++)
        {
            std::string at_i = "[" + std::to_string(i) + "]";
            p.in_types.push_back({this->props.as_width(widths[i], w + ".in_widths" + at_i),
                this->props.as_bool(signs[i], w + ".in_signed" + at_i)});
            std::string port = dynamic_cast<js::ConfigString *>(ins[i]) ? ins[i]->get_str() : "";
            bool is_seed = p.seed && (int)i == seed;
            int d_in = d_ins ? this->props.as_int(slices[i], w + ".d_in[" + std::to_string(i) +
                "]") : 1;
            bool broadcast = bcasts && this->props.as_bool(wired[i], w + ".broadcast[" +
                std::to_string(i) + "]");
            bool hold = holds && this->props.as_bool(kept[i], w + ".hold[" + std::to_string(i) +
                "]");
            if (hold && (is_seed || !broadcast || p.rows < 2))
            {
                this->trace.fatal("Property %s.hold[%ld]: true, but a held input is a broadcast "
                    "input of a bank (rows above 1), not the seed\n", w.c_str(), i);
            }
            held = held || (hold && !port.empty());
            if (broadcast && ((port.empty() && !hold) || is_seed || p.lanes < 2))
            {
                this->trace.fatal("Property %s.broadcast[%ld]: true, but a broadcast is an input "
                    "of 2 lanes or more, outer or a held link's, not the seed\n", w.c_str(), i);
            }
            held_link[k].push_back(hold && port.empty());
            // the lanes its stream moves a beat: one for a broadcast, a seed its output's
            int lanes = broadcast ? 1 : is_seed ? snax_seed_lanes(datapath, p.lanes) : p.lanes;
            if ((d_in != 1 && d_in != 2 && d_in != 4 && d_in != 8) ||
                (d_in > 1 && (port.empty() || lanes * p.in_types.back().width * d_in != 64)))
            {
                this->trace.fatal("Property %s.d_in[%ld]: %d, must be 1, 2, 4 or 8, and above 1 "
                    "only on an outer input whose %d lanes of %d bits are 64 / d_in\n",
                    w.c_str(), i, d_in, lanes, p.in_types.back().width);
            }
            if (port.empty() && is_seed)
            {
                this->trace.fatal("Property %s.inputs[%ld]: \"\", but the seed is an outer "
                    "input (the streamer's)\n", w.c_str(), i);
            }
            if (port.empty())
            {
                linked[k].push_back(i);
                continue;
            }
            int words = d_in > 1 ? 1 : snax_words(lanes, p.in_types.back());
            size_t x = std::find(in_names.begin(), in_names.end(), port) - in_names.begin();
            if (x < at)
            {
                // NB (D189): a forked input, alike on each of its units, none's seed
                OuterIn &o = this->in_itf[x];
                const SnaxType &t = p.in_types.back();
                if (is_seed || o.seed || hold || o.hold || o.words != words ||
                    o.slicer.d_in != d_in || o.broadcast != broadcast || o.type.width != t.width ||
                    o.type.is_signed != t.is_signed || o.lanes != p.lanes ||
                    std::find(o.units.begin(), o.units.end(), k) != o.units.end())
                {
                    this->trace.fatal("Property %s.inputs[%ld]: \"%s\", an input of another "
                        "unit too, so a forked one, but not alike on both (type, lanes, d_in, "
                        "broadcast), a seed or held, or twice on one unit\n", w.c_str(), i,
                        port.c_str());
                }
                o.units.push_back(k);
                this->unit_ins.back().push_back(x);
                continue;
            }
            OuterIn &o = this->in_itf[at];
            o.name = port;
            o.units = {k};
            o.seed = is_seed;
            o.words = words;
            o.slicer.d_in = d_in;
            o.beat.assign(o.words, 0);
            o.broadcast = broadcast;
            o.hold = hold;
            o.type = p.in_types.back();
            o.lanes = p.lanes;
            o.wide.assign(broadcast ? snax_words(p.lanes, o.type) : 0, 0);
            this->new_master_port(port, &o.itf);
            this->unit_ins.back().push_back(at++);
        }
        p.out_type = this->type_prop(u, "out_width", "out_signed", w);
        p.op_type = this->type_prop(u, "op_width", "op_signed", w);
        std::string op = this->props.str_prop(u, "op", w);
        p.op = op == snax_op_axpby_name ? SNAX_OP_AXPBY : -1;
        for (int i = 0; i < SNAX_NB_OPS; i++)
        {
            p.op = op == snax_op_names[i] ? i : p.op;
        }
        if (p.op == -1)
        {
            this->trace.fatal("Property %s.op: \"%s\", not an op (add, sub, mul, and, or, xor, "
                "min, max, axpby)\n", w.c_str(), op.c_str());
        }
        p.accumulate = this->props.bool_prop(u, "accumulate", w);
        p.reg_out = this->props.bool_prop(u, "reg_out", w);
        // A baked slot: decimal, its bits; "" not baked
        auto baked = [&](const char *key, bool *has, uint64_t *bits) {
            std::string text = this->props.str_prop(u, key, w);
            if (text.empty())
            {
                return;
            }
            try
            {
                size_t used = 0;
                *bits = text[0] == '-' ? (uint64_t)std::stoll(text, &used)
                    : std::stoull(text, &used);
                *has = used == text.size();
            }
            catch (const std::exception &)
            {
                *has = false;
            }
            if (!*has)
            {
                this->trace.fatal("Property %s.%s: \"%s\", not a decimal integer\n", w.c_str(),
                    key, text.c_str());
            }
        };
        baked("k", &p.has_k, &p.k);
        baked("k1", &p.has_k1, &p.k1);
        baked("k2", &p.has_k2, &p.k2);
        this->scalars.emplace_back();
        std::vector<js::Config *> slots = this->props.list_prop(u, "scalars", w);
        for (size_t i = 0; i < slots.size(); i++)
        {
            std::string at_i = w + ".scalars[" + std::to_string(i) + "]";
            std::vector<js::Config *> pair = this->props.as_list(slots[i], at_i);
            if (pair.size() != 2)
            {
                this->trace.fatal("Property %s: [slot, words]\n", at_i.c_str());
            }
            std::string slot = this->props.as_str(pair[0], at_i);
            int words = this->props.as_int(pair[1], at_i);
            bool *has = slot == "k" ? &p.has_k : slot == "k1" ? &p.has_k1 : slot == "k2" ? &p.has_k2
                : nullptr;
            if (!has || *has || (words != 1 && words != 2))
            {
                this->trace.fatal("Property %s: [\"%s\", %d]: a slot k, k1 or k2 not baked, of 1 "
                    "or 2 words\n", at_i.c_str(), slot.c_str(), words);
            }
            *has = true;
            (slot == "k" ? p.k_csr : slot == "k1" ? p.k1_csr : p.k2_csr) = true;
            this->scalars.back().push_back({slot, words});
            this->scalar_words += words;
        }
        std::string why;
        std::unique_ptr<SnaxDatapath> dp = snax_datapath_new(datapath, p, &why);
        if (!dp)
        {
            this->trace.fatal("Property %s.datapath: %s: %s\n", w.c_str(), datapath.c_str(),
                why.c_str());
        }
        SnaxGroupRule::UnitCfg c;
        c.latency = this->props.int_prop(u, "latency", w);
        c.ii = this->props.int_prop(u, "ii", w);
        c.span = this->props.int_prop(u, "span", w);
        c.seeded = p.seed;
        c.rows = p.rows;
        c.held = held;
        if (c.latency != dp->latency || c.ii != 1 || c.span != dp->span)
        {
            this->trace.fatal("Property %s.latency, ii, span: %d, %d, %d; %s is %d, 1, %d\n",
                w.c_str(), c.latency, c.ii, c.span, datapath.c_str(), dp->latency, dp->span);
        }
        if (c.span > 1 && this->unit_ins.back().size() > (p.seed ? 1u : 0u))
        {
            this->trace.fatal("Property %s.inputs: a unit of span %d reads its input in place: "
                "its input is a link, not a streamer's\n", w.c_str(), c.span);
        }
        cfgs.push_back(c);
        int t = this->props.int_prop(u, "t", w);
        if (t < 0)
        {
            this->trace.fatal("Property %s.t: %d, must be 0 or more\n", w.c_str(), t);
        }
        this->fixed_t.push_back(t);
        std::string out = this->props.str_prop(u, "output", w);
        if (!out.empty())
        {
            OuterOut &o = this->out_itf[outputs.size()];
            outputs.push_back(k);
            o.name = out;
            o.unit = k;
            o.words = dp->out_words;
            o.beat.assign(o.words, 0);
            o.packer.d_out = this->props.int_prop(u, "d_out", w);
            int d = o.packer.d_out;
            if ((d != 1 && d != 2 && d != 4 && d != 8) || (d > 1 && dp->out_words != 1))
            {
                this->trace.fatal("Property %s.d_out: %d, must be 1, 2, 4 or 8, and above 1 "
                    "only on a one-word result (%d words)\n", w.c_str(), d, dp->out_words);
            }
        }
        this->data.units.push_back(std::move(dp));
        names.push_back(name);
        params.push_back(p);
        described += (described.empty() ? "" : ", ") + name + " (" + datapath + ", L " +
            std::to_string(c.latency) + ", span " + std::to_string(c.span) + ")";
    }
    if (outputs.empty())
    {
        this->trace.fatal("Property units: no unit has an outer output (every output \"\"): "
            "each chain's sink has one\n");
    }

    // The links: edges from a unit's output into an input of another that is left ""
    std::vector<js::Config *> links = this->props.list_prop(this->get_js_config(), "links", "");
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
            std::string name = this->props.str_prop(links[i], keys[j], w);
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
        e.to_input = this->props.int_prop(links[i], "to_input", w);
        e.depth = this->props.int_prop(links[i], "depth", w);
        js::Config *hold_prop = links[i]->get("hold");
        e.hold = hold_prop && this->props.as_bool(hold_prop, w + ".hold");
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
        if (e.hold != held_link[e.to][e.to_input] || (e.hold && e.depth < 1))
        {
            this->trace.fatal("Property %s.hold: %d, units[%d].hold[%d] %d, depth %d; a held "
                "link, a buffer of depth 1 or more, feeds a held input\n", w.c_str(), e.hold,
                e.to, e.to_input, (int)held_link[e.to][e.to_input], e.depth);
        }
        // NB (D197): a held link's beat is one lane, broadcast from the hold register
        const SnaxType &type = params[e.to].in_types[e.to_input];
        const int lanes = e.hold ? 1 : params[e.to].lanes;
        const SnaxDatapath *src = this->data.units[e.from].get();
        const SnaxDatapath *dst = this->data.units[e.to].get();
        int takes = e.hold ? snax_words(1, type) : dst->in_words[e.to_input];
        if (src->out_words != takes)
        {
            this->trace.fatal("Property %s: the link carries %d words a beat, units[%d].inputs[%d] "
                "takes %d\n", w.c_str(), src->out_words, e.to, e.to_input, takes);
        }
        std::unique_ptr<SnaxDatapath> buffer;
        if (e.depth > 0)
        {
            SnaxDatapathParams b;
            b.in_types = {type};
            b.out_type = type;
            b.lanes = lanes;
            b.depth = e.depth;
            std::string why;
            buffer = snax_datapath_new("LinkBuffer", b, &why);
        }
        this->data.buffers.push_back(std::move(buffer));
        this->data.held.push_back({e.hold ? params[e.to].lanes : 0, type});
        edges.push_back(e);
        described += "; " + names[e.from] + " -> " + names[e.to] + " depth " +
            std::to_string(e.depth) + (e.hold ? " held" : "");
    }

    // The fork links: a forked input's beat through a buffer into an input left "" of a unit
    // further down a chain
    js::Config *fork_prop = this->get_js_config()->get("fork_links");
    std::vector<js::Config *> fork_links = fork_prop ? this->props.as_list(fork_prop,
        "fork_links") : std::vector<js::Config *>();
    std::vector<SnaxGroupRule::ForkLink> branches;
    std::vector<size_t> branch_in;      // per fork link, its forked input (in_itf index)
    for (size_t i = 0; i < fork_links.size(); i++)
    {
        std::string w = "fork_links[" + std::to_string(i) + "]";
        SnaxGroupRule::ForkLink e;
        std::string fork = this->props.str_prop(fork_links[i], "fork", w);
        std::string to = this->props.str_prop(fork_links[i], "to", w);
        size_t x = std::find_if(this->in_itf.begin(), this->in_itf.end(),
            [&](const OuterIn &o) { return o.name == fork; }) - this->in_itf.begin();
        e.to = std::find(names.begin(), names.end(), to) - names.begin();
        if (x == this->in_itf.size() || this->in_itf[x].seed || this->in_itf[x].hold ||
            e.to == (int)names.size())
        {
            this->trace.fatal("Property %s: fork \"%s\" to \"%s\": a fork link goes from an outer "
                "input of the group (not a seed, not held) to one of its units\n", w.c_str(),
                fork.c_str(), to.c_str());
        }
        const OuterIn &o = this->in_itf[x];
        e.to_input = this->props.int_prop(fork_links[i], "to_input", w);
        e.depth = this->props.int_prop(fork_links[i], "depth", w);
        bool is_open = false;
        for (int y : linked[e.to])
        {
            is_open = is_open || y == e.to_input;
        }
        if (!is_open || fed[e.to][e.to_input]++ || e.depth < 1)
        {
            this->trace.fatal("Property %s: to_input %d, depth %d; units[%d].inputs[%d] is not an "
                "input left \"\", or another link feeds it, or the depth is below 1\n", w.c_str(),
                e.to_input, e.depth, e.to, e.to_input);
        }
        const std::vector<size_t> &head_ins = this->unit_ins[o.units[0]];
        e.from_input = std::find(head_ins.begin(), head_ins.end(), x) - head_ins.begin();
        const SnaxType &type = params[e.to].in_types[e.to_input];
        int words = o.broadcast ? snax_words(o.lanes, o.type) : o.words;
        if (o.type.width != type.width || o.type.is_signed != type.is_signed ||
            words != this->data.units[e.to]->in_words[e.to_input] || held_link[e.to][e.to_input])
        {
            this->trace.fatal("Property %s: the fork's beat is %d words of %d bits, "
                "units[%d].inputs[%d] takes %d of %d bits (not held)\n", w.c_str(), words,
                o.type.width, e.to, e.to_input, this->data.units[e.to]->in_words[e.to_input],
                type.width);
        }
        SnaxDatapathParams b;
        b.in_types = {type};
        b.out_type = type;
        b.lanes = params[e.to].lanes;
        b.depth = e.depth;
        std::string why;
        this->data.fork_buffers.push_back(snax_datapath_new("LinkBuffer", b, &why));
        branches.push_back(e);
        branch_in.push_back(x);
        described += "; " + fork + " to " + to + " through " + std::to_string(e.depth);
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
    // the forks: an input of two or more units, or one with a fork link
    std::vector<std::vector<int>> forks;
    for (size_t x = 0; x < this->in_itf.size(); x++)
    {
        const OuterIn &o = this->in_itf[x];
        bool branched = std::find(branch_in.begin(), branch_in.end(), x) != branch_in.end();
        if (o.units.size() > 1 || branched)
        {
            for (size_t i = 0; i < branches.size(); i++)
            {
                branches[i].fork = branch_in[i] == x ? (int)forks.size() : branches[i].fork;
            }
            forks.emplace_back(o.units.begin(), o.units.end());
            described += "; " + o.name + " forked to";
            for (size_t k : o.units)
            {
                described += " " + names[k];
            }
        }
    }
    std::string refused = this->rule.configure(cfgs, edges, outputs, forks, branches);
    if (!refused.empty())
    {
        this->trace.fatal("Property units, links: %s\n", refused.c_str());
    }
    this->data.wire(this->rule);
    this->inputs.assign(units.size(), true);
    this->seeds.assign(units.size(), true);
    this->holds.assign(units.size(), true);
    this->carry_jobs.assign(units.size(), 0);
    this->room.assign(units.size(), true);
    this->outer.assign(units.size(), {});
    for (size_t k = 0; k < units.size(); k++)
    {
        for (size_t i : this->unit_ins[k])
        {
            OuterIn &o = this->in_itf[i];
            this->outer[k].push_back(o.broadcast ? o.wide.data() : o.beat.data());
        }
    }
    this->csr_base = this->props.int_prop(this->get_js_config(), "csr_base", "");

    for (OuterOut &o : this->out_itf)
    {
        this->new_master_port(o.name, &o.itf);
    }
    this->ctrl_itf.set_req_meth(&SnaxGroup::ctrl_req);
    this->new_slave_port("ctrl", &this->ctrl_itf);
    this->new_master_port("busy", &this->busy_itf);
    this->mark_itf.set_sync_meth(&SnaxGroup::mark_sync);
    this->new_slave_port("mark", &this->mark_itf);
    this->unit_names = names;

    this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", described.c_str());
}


void SnaxGroup::reset(bool active)
{
    if (active)
    {
        this->rule.reset();
        this->first_fire = this->last_fire = -1;
        for (OuterOut &o : this->out_itf)
        {
            o.pushes = 0;
            o.results = 0;
            o.rate = 1;
            o.packer.clear();
        }
        for (OuterIn &o : this->in_itf)
        {
            o.slicer.clear();
            o.word_id = -1;
        }
        this->line_class = -1;
        std::fill(std::begin(this->total_classes), std::end(this->total_classes), 0);
        this->unit_firings.assign(this->unit_names.size(), 0);
        this->unit_pushes.assign(this->unit_names.size(), 0);
    }
}


// The last snapshot, at the end of the simulation
void SnaxGroup::stop()
{
    this->snap(-1);
}


void SnaxGroup::mark_sync(vp::Block *__this, uint32_t mark)
{
    ((SnaxGroup *)__this)->snap(mark);
}


// The group's line, then one per unit in the order of the property units
void SnaxGroup::snap(int64_t mark)
{
    long cycle = (long)this->clock.get_cycles();
    this->ev.summary.msg(vp::Trace::LEVEL_INFO,
        "%ld snap mark=%ld busy=%ld stall_in=%ld stall_out=%ld flush=%ld\n", cycle, (long)mark,
        (long)this->total_classes[SnaxGroupRule::BUSY],
        (long)this->total_classes[SnaxGroupRule::STALL_IN],
        (long)this->total_classes[SnaxGroupRule::STALL_OUT],
        (long)this->total_classes[SnaxGroupRule::FLUSH]);
    for (size_t k = 0; k < this->unit_names.size(); k++)
    {
        this->ev.summary.msg(vp::Trace::LEVEL_INFO,
            "%ld snap mark=%ld unit=%s firings=%ld pushes=%ld\n", cycle, (long)mark,
            this->unit_names[k].c_str(), (long)this->unit_firings[k],
            (long)this->unit_pushes[k]);
    }
}


SnaxType SnaxGroup::type_prop(js::Config *config, const char *width, const char *is_signed,
    const std::string &where)
{
    return {this->props.width_prop(config, width, where),
        this->props.bool_prop(config, is_signed, where)};
}


// A start: a JOBS per output, then the T of each unit with t 0, in unit order
vp::IoReqStatus SnaxGroup::ctrl_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxGroup *_this = (SnaxGroup *)__this;
    int64_t cycle = _this->clock.get_cycles();

    size_t open = 0;
    for (uint32_t t : _this->fixed_t)
    {
        open += t == 0;
    }
    size_t nb_jobs = _this->out_itf.size();
    size_t unit_words = _this->scalar_words;    // ROWS, CARRY and the scalars, per unit
    for (size_t k = 0; k < _this->fixed_t.size(); k++)
    {
        unit_words += (_this->bank_rows[k] > 1) + _this->carried[k];
    }
    size_t words = nb_jobs + (open ? open : 1) + unit_words;
    if (!req->get_is_write() || req->get_size() != 4 * words)
    {
        _this->trace.force_warning("Unexpected access on ctrl (size: %ld, is_write: %d): a "
            "start is a write of %ld words, a JOBS per output and each fold's JOB_BEATS (or "
            "1), then each unit's ROWS, CARRY and scalars'\n", req->get_size(),
            req->get_is_write(), words);
        return vp::IO_REQ_INVALID;
    }
    uint32_t *w = (uint32_t *)req->get_data();
    std::vector<uint32_t> jobs(w, w + nb_jobs);
    std::vector<uint32_t> ts;
    size_t next = nb_jobs;
    for (uint32_t t : _this->fixed_t)
    {
        ts.push_back(t ? t : w[next++]);
    }
    if (!open && w[nb_jobs] != 1)
    {
        _this->trace.fatal("Start at cycle %ld: job_beats %u; no unit of the group takes one "
            "(1)\n", cycle, w[nb_jobs]);
    }
    next = nb_jobs + (open ? open : 1);
    std::vector<uint32_t> rows(_this->fixed_t.size(), 1);
    for (size_t k = 0; k < _this->scalars.size(); k++)
    {
        // NB (D191): a bank's ROWS, the rows a run uses
        if (_this->bank_rows[k] > 1)
        {
            rows[k] = w[next++];
            if (rows[k] < 1 || (int64_t)rows[k] > _this->bank_rows[k] ||
                (ts[k] && ts[k] % rows[k]))
            {
                _this->trace.fatal("Start at cycle %ld: unit %ld's ROWS %u; a bank of %d rows "
                    "uses 1 to %d, dividing its T %u\n", cycle, k, rows[k], _this->bank_rows[k],
                    _this->bank_rows[k], ts[k]);
            }
        }
        // the jobs a carried seed is given as 0
        if (_this->carried[k])
        {
            _this->carry_jobs[k] = w[next++];
        }
        for (const std::pair<std::string, int> &slot : _this->scalars[k])
        {
            uint64_t bits = w[next] | (slot.second == 2 ? (uint64_t)w[next + 1] << 32 : 0);
            next += slot.second;
            _this->data.units[k]->set_scalar(slot.first, bits);
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: unit %ld's %s 0x%lx\n",
                cycle, k, slot.first.c_str(), bits);
        }
    }
    for (uint64_t n : _this->rule.firings_for(jobs, ts, rows))
    {
        if (n > UINT32_MAX)
        {
            _this->trace.fatal("Start at cycle %ld: a unit's firings are past 32 bits\n",
                cycle);
        }
    }

    switch (_this->rule.start(cycle, jobs, ts, rows))
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
            // per output, the head's firings per result (a list with several outputs)
            std::string rates;
            for (OuterOut &o : _this->out_itf)
            {
                o.results = _this->rule.firings_per_run[o.unit] / _this->rule.job_beats[o.unit] *
                    _this->rule.rows[o.unit];
                o.rate = _this->rule.count() / o.results;
                o.pushes = 0;
                o.packer.clear();
                rates += (rates.empty() ? "" : ",") + std::to_string(o.rate);
            }
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Start at cycle %ld: JOBS %u, %ld T\n", cycle,
                jobs[0], ts.size());
            _this->ev.events.msg(vp::Trace::LEVEL_INFO, "%ld start count=%u rate=%s\n",
                (long)cycle, _this->rule.count(), rates.c_str());
            _this->first_fire = _this->last_fire = -1;
            for (OuterIn &o : _this->in_itf)
            {
                o.slicer.clear();
                o.word_id = -1;
            }
            _this->line_class = -1;
            if (_this->busy_itf.is_bound())
            {
                _this->busy_itf.sync(true);
            }
            if (!_this->cycle_event.is_enqueued())
            {
                _this->cycle_event.enqueue(1);
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
void SnaxGroup::cycle_handler(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxGroup *_this = (SnaxGroup *)__this;
    int64_t cycle = _this->clock.get_cycles();

    if (_this->rule.busy(cycle))
    {
        std::vector<bool> &inputs = _this->inputs, &seeds = _this->seeds, &holds = _this->holds;
        std::fill(inputs.begin(), inputs.end(), true);
        std::fill(seeds.begin(), seeds.end(), true);
        std::fill(holds.begin(), holds.end(), true);
        // a sliced input's beat is its slicer's word, not the reader's; a forked one's is each
        // of its units'
        for (OuterIn &o : _this->in_itf)
        {
            std::vector<bool> &has = o.seed ? seeds : o.hold ? holds : inputs;
            bool there = o.slicer.d_in > 1 ? o.slicer.full : _this->probe(o.itf, false);
            for (size_t k : o.units)
            {
                has[k] = there && has[k];
            }
        }
        // A push the packer keeps needs no room at the writer: only a sending one asks it
        for (OuterOut &o : _this->out_itf)
        {
            bool last = o.pushes + 1 == o.results;
            _this->room[o.unit] = !o.packer.sending(last) || _this->probe(o.itf, true);
        }

        const SnaxGroupRule::Step &step = _this->rule.step(cycle, inputs, seeds, holds,
            _this->room);
        _this->total_classes[step.cls]++;
        for (size_t k = 0; k < step.units.size(); k++)
        {
            _this->unit_firings[k] += step.units[k].fire;
            _this->unit_pushes[k] += step.units[k].push;
        }
        size_t first = _this->rule.topological().front();
        const SnaxGroupRule::UnitStep &head = step.units[first];
        bool pushed = false;
        for (const OuterOut &o : _this->out_itf)
        {
            pushed = pushed || step.units[o.unit].push;
        }
        _this->sigs.set(_this->sig_busy, 1);
        _this->sigs.set(_this->sig_fire, head.fire);
        _this->sigs.set(_this->sig_push, pushed);
        _this->sigs.set(_this->sig_class, step.cls + 1);
        snax_class_line(_this->ev.beats, &_this->line_class, step.cls,
            snax_group_class_names[step.cls], cycle);

        // The beats of each unit that fires, its outer inputs in port order (outer); a forked
        // input's once, when its units fire (together). A sliced input pops on that
        // firing (a seed's on its take, a held input's on its row's first firing), its slice
        // the beat, then takes the reader's word when its slicer was empty or that was its last
        // pop. A broadcast's beat goes to all its unit's lanes. A held input's beat stays until
        // its next take: the register of its element's width that keeps it for the row.
        std::string beats, values;
        bool traced = _this->ev.beats.get_active();
        for (OuterIn &o : _this->in_itf)
        {
            size_t k = o.units[0];
            bool moved = o.seed ? step.units[k].seed : o.hold ? step.units[k].take
                : step.units[k].fire;
            bool sliced = o.slicer.d_in > 1;
            bool open = sliced && o.slicer.open(moved);
            o.id = -1;
            if (moved && sliced)
            {
                o.beat[0] = o.slicer.pop();
                o.id = o.word_id;
            }
            else if (moved)
            {
                _this->move(o.itf, false, o.beat.data(), o.words);
                o.id = snax_arg_get(&_this->beat_req, SNAX_ARG_TAG) == SNAX_TAG_BEAT
                    ? (long)snax_arg_get(&_this->beat_req, SNAX_ARG_ID) : -1L;
            }
            // NB (D192): a carried seed's beat is taken every job, its value 0 before CARRY
            if (moved && o.seed && _this->carried[k] && step.units[k].job < _this->carry_jobs[k])
            {
                std::fill(o.beat.begin(), o.beat.end(), 0);
            }
            if (moved && o.broadcast)
            {
                snax_broadcast(o.beat.data(), o.lanes, o.type, o.wide.data());
            }
            if (open && _this->probe(o.itf, false))
            {
                uint64_t word;
                _this->move(o.itf, false, &word, 1);
                o.slicer.take(word);
                o.word_id = snax_arg_get(&_this->beat_req, SNAX_ARG_TAG) == SNAX_TAG_BEAT
                    ? (long)snax_arg_get(&_this->beat_req, SNAX_ARG_ID) : -1L;
            }
        }
        // the head's firing lists every outer input of its own; a seed not taken in it as -1
        for (size_t i : _this->unit_ins[first])
        {
            const OuterIn &o = _this->in_itf[i];
            if (traced && head.fire)
            {
                snax_join(beats, std::to_string(o.id));
                snax_join(values, snax_words_text(o.beat.data(), o.beat.size()));
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

        _this->data.cycle(step, _this->outer);
        // Each output's push; with several outputs its line names its unit
        for (OuterOut &o : _this->out_itf)
        {
            if (!step.units[o.unit].push)
            {
                continue;
            }
            const std::vector<uint64_t> &result = _this->data.out(o.unit);
            std::vector<uint64_t> &out = o.beat;
            std::copy(result.begin(), result.end(), out.begin());
            bool last = o.pushes + 1 == o.results;
            uint64_t word;
            if (o.packer.d_out == 1)
            {
                _this->move(o.itf, true, out.data(), o.words);
            }
            else if (o.packer.push(out[0], last, &word))
            {
                _this->move(o.itf, true, &word, 1);
            }
            if (_this->ev.beats.get_active())
            {
                std::string text = snax_words_text(out.data(), out.size());
                std::string unit = _this->out_itf.size() > 1 ? " unit=" +
                    _this->unit_names[o.unit] : "";
                uint32_t from = o.pushes * o.rate;
                _this->ev.beats.msg(vp::Trace::LEVEL_INFO,
                    "%ld push n=%u first=%u last=%u value=%s%s\n", (long)cycle, o.pushes,
                    from, from + o.rate - 1, text.c_str(), unit.c_str());
            }
            o.pushes++;
        }
        if (step.end)
        {
            if (_this->trace.get_active())
            {
                _this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s\n", _this->rule.run_line().c_str());
            }
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
        _this->cycle_event.enqueue(1);
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxGroup(config);
}
