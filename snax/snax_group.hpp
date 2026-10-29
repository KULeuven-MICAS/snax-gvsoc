/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxGroupRule: the control model of one group of an accelerator, snax-forge
// C§17's Control paragraph (D146, D147): the `<tag>_<group>_ctrl` of its
// Chisel, which drives the group's datapaths (snax_datapath.hpp) with their
// enables, every cycle. Plain C++, so the component (snax_group.cpp) and the
// standalone tests (tests/snax/unit/, tests/snax/shell/, tests/snax/group/,
// the first two with one unit and no links) run the same code, as
// snax_sparse_arb.hpp. Its Python twin is snax_group_rule.py (GroupRule),
// which writes the group cases: a change to the rule changes both.
//
// A group is a graph of units and links: a link is an edge from one unit's
// output to an input of another (Link: from, to, to_input, depth; depth 0 a
// wire, >= 1 a buffer of D beats, a LinkBuffer). Each unit has its latency L,
// its II, its span (the cycles it reads one input beat in place,
// SerialAccumulate's lanes) and, per run, its T: a result every T-th firing
// (a fold's JOB_BEATS or params.T; 1 for a unit without a fold). Each unit's
// outer inputs, if any, come from the streamer; one unit owns the group's
// outer output (by default the sink, the unit without an out-edge). Until
// tier A a group is one chain: configure() refuses a unit with two out-edges
// (a fork) or two in-edges (a join), a cycle, and units no link joins.
//
// A run: a start offered in cycle s carries JOBS and each unit's T; unit k
// fires n_k times, JOBS * T for the sink, n_succ * T_k for a unit before it
// (each firing of its consumer takes one of its results): over a chain, JOBS *
// prod T_v over k and every unit after it (C§17's firings). It is taken only
// when the group is idle in s and no number is 0 (JOBS 0 or any T 0 is the
// empty run, which the shell ends without the group: here it is ignored, busy
// stays 0); a start while busy is refused. The group is busy from s + 1 to the
// run's last cycle E, when every unit has fired its n and nothing is in
// flight. step() is called once per busy cycle with, per unit, whether its
// outer inputs all have a beat and whether its outer output has room (true for
// a unit without one).
//
// Per unit (C§17): its beat digit d (its firings mod T: first = [d = 0], it
// gives a result on firings with d = T - 1), an L-deep pipeline that stalls
// as a whole when its head cannot be pushed, at most one firing per II (the
// II counts cycles from the unit's last firing; a stall does not restart it,
// and it carries over to the next run), and a lane counter when span > 1. A
// unit wants to fire while it has firings left and its II allows. Its input
// has a beat when each of its outer inputs has one and each in-edge offers
// one: a wire offers what its producer presents this cycle (its pipeline's
// head, or with L = 0 a firing that gives a result), a buffer its oldest beat
// (occupancy > 0: a beat written in an earlier cycle). A unit of span 1 fires
// when it wants to and its input has a beat; one of span S reads lane l of
// the beat in place (the lane counter) in each such cycle and fires (takes
// the beat) on lane S - 1, so its throughput is one beat per max(II, S). A
// result from a firing in t is pushed in t + L when nothing stalls. A unit
// has room when its outer output (if it owns it) has room and each out-edge
// takes: a wire when its consumer fires, a buffer when occupancy < D or its
// consumer fires. So at depth 0 a unit holds its result until its reader
// takes it, at span S its last lane. With L = 0 a firing that gives a result
// with no room is a stall (L = 0, II 1 is lockstep). A firing enters slot 0
// in the cycle the head is pushed: with L = 1 and II 1 the next input is
// taken as a result leaves. A wire chain is one nest with L = sum L_k, plus
// one enable per stage: fire_{k+1}(c) = fire_k(c - L_k) and gives_k(c - L_k).
//
// The cycle is decided in two passes over the units in a topological order:
// forward, what each unit offers on its output whatever its room, so each
// unit knows whether its input has a beat (avail_k = inputs_k and the offer
// of every in-edge); backward, in reverse order, its room (room_k =
// outer_room_k and the take of every out-edge), whether it is frozen (its
// head, or with L = 0 a giving firing, has no room), fires and reads. Then
// each buffer's occupancy: + 1 on a load (its producer's push), - 1 on a take
// (its consumer's firing), its write and read slots a ring.
//
// Each busy cycle is one class, judged at the unit owning the outer output,
// in D59's order: stall_out (it has a result and no room: it is frozen) >
// busy (any unit fires or reads, or is in its II gap) > stall_in (a unit with
// outer inputs wants to fire and one of them has no beat) > flush (results in
// flight, beats in a buffer: accel.py's idle). busy + stall_in + stall_out +
// flush is the run's busy cycles, E - s; the run line's firings are the
// head's (the first unit in the topological order).

#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

#include "snax_datapath.hpp"
#include "snax_run_span.hpp"


// The classes by name, as a run line and the class lines give them
static const char *const snax_group_class_names[] = {"busy", "stall_in", "stall_out", "flush"};


class SnaxGroupRule
{
public:
    enum Class { BUSY, STALL_IN, STALL_OUT, FLUSH, NB_CLASSES };
    enum Start { TAKEN, IGNORED, REFUSED };

    struct UnitCfg
    {
        int latency = 0;
        int ii = 1;
        int span = 1;
    };

    // An edge: unit from's output into input to_input of unit to (its index among the
    // unit's inputs, for the datapaths; the rule does not read it)
    struct Link
    {
        int from = 0;
        int to = 0;
        int to_input = 0;
        int depth = 0;
    };

    // What one unit does in a busy cycle: its datapath's enables are fire,
    // first, read and lane (snax_datapath.hpp's SnaxEnables; en = fire for a
    // plain Mac's output register)
    struct UnitStep
    {
        bool fire = false;      // a beat taken from its input (the last lane's read at span > 1)
        bool result = false;    // the firing gives a result (d = T - 1)
        bool push = false;      // a result given to the outer output or the link
        bool read = false;      // span > 1: lane `lane` read in place
        int lane = 0;
        bool first = false;     // the beat fired or read is its job's first (d = 0)
        bool frozen = false;    // its head (or, L = 0, a giving firing) had no room
    };

    // What one buffer does: its LinkBuffer's load, wslot, rslot (a wire's stays all 0)
    struct LinkStep
    {
        bool load = false;
        bool take = false;
        int wslot = 0;
        int rslot = 0;
        int occupancy = 0;      // after the cycle
    };

    struct Step
    {
        std::vector<UnitStep> units;
        std::vector<LinkStep> links;
        Class cls = FLUSH;
        bool end = false;       // the run's last cycle: idle from the next one
    };

    // The units, the links between them, and the unit owning the outer output (-1: the
    // sink). Returns why the graph is refused, or "" (then the rule is configured).
    std::string configure(const std::vector<UnitCfg> &units, const std::vector<Link> &links,
        int output = -1)
    {
        size_t n = units.size();
        std::vector<std::vector<int>> ins(n), outs(n);
        for (size_t i = 0; i < links.size(); i++)
        {
            const Link &e = links[i];
            if (e.from < 0 || e.from >= (int)n || e.to < 0 || e.to >= (int)n || e.depth < 0)
            {
                return "link " + std::to_string(i) + ": no such unit, or a depth below 0";
            }
            outs[e.from].push_back(i);
            ins[e.to].push_back(i);
        }
        for (size_t k = 0; k < n; k++)
        {
            if (outs[k].size() > 1 || ins[k].size() > 1)
            {
                bool fork = outs[k].size() > 1;
                return "unit " + std::to_string(k) + " has " +
                    std::to_string(fork ? outs[k].size() : ins[k].size()) +
                    (fork ? " out-edges (a fork)" : " in-edges (a join)") +
                    ": until tier A a group is a chain";
            }
        }
        // Kahn's order, the lowest index first among the units ready
        std::vector<size_t> order, need(n);
        std::vector<size_t> ready;
        for (size_t k = 0; k < n; k++)
        {
            need[k] = ins[k].size();
            if (!need[k])
            {
                ready.push_back(k);
            }
        }
        for (size_t r = 0; r < ready.size(); r++)
        {
            size_t k = ready[r];
            order.push_back(k);
            for (int i : outs[k])
            {
                if (--need[links[i].to] == 0)
                {
                    ready.push_back(links[i].to);
                }
            }
        }
        if (order.size() != n)
        {
            return "the links form a cycle";
        }
        size_t sinks = 0, sink = 0;
        for (size_t k = 0; k < n; k++)
        {
            if (outs[k].empty())
            {
                sinks++;
                sink = k;
            }
        }
        if (sinks != 1)
        {
            return std::to_string(sinks) + " units have no out-edge: until tier A a group is "
                "one chain";
        }
        if (output >= (int)n)
        {
            return "the outer output's unit " + std::to_string(output) + ": no such unit";
        }
        this->cfg = units;
        this->links = links;
        this->ins = ins;
        this->outs = outs;
        this->order = order;
        this->output = output < 0 ? sink : output;
        this->u.assign(n, UnitState());
        this->l.assign(links.size(), LinkState());
        this->stepped.units.assign(n, UnitStep());
        this->stepped.links.assign(links.size(), LinkStep());
        for (std::vector<bool> *v : {&this->avail, &this->wants, &this->would_fire, &this->gives,
            &this->head, &this->offer})
        {
            v->assign(n, false);
        }
        this->reset();
        return "";
    }

    void reset()
    {
        this->span.reset();
        this->jobs = 0;
        this->beats.assign(this->cfg.size(), 1);
        this->counts.assign(this->cfg.size(), 0);
        for (size_t k = 0; k < this->u.size(); k++)
        {
            this->u[k] = UnitState();
            this->u[k].slots.assign(this->cfg[k].latency, false);
        }
        for (LinkState &ls : this->l)
        {
            ls = LinkState();
        }
        this->runs = 0;
        for (int c = 0; c < NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
    }

    size_t nb_units() const { return this->cfg.size(); }

    // The units in topological order, the head first; the unit owning the outer output
    const std::vector<size_t> &topological() const { return this->order; }
    size_t output_unit() const { return this->output; }
    const std::vector<Link> &edges() const { return this->links; }

    // Idle in cycle: no run, or the last one ended before it
    bool idle(int64_t cycle) const { return this->span.idle(cycle); }

    // Busy in cycle: from the cycle after the start to the run's last cycle
    bool busy(int64_t cycle) const { return this->span.busy(cycle); }

    // A start of jobs, unit k a result every t[k] firings, offered in cycle;
    // the caller keeps every n_k within 32 bits
    Start start(int64_t cycle, uint32_t jobs, const std::vector<uint32_t> &t)
    {
        if (!this->idle(cycle))
        {
            return REFUSED;
        }
        bool empty = jobs == 0;
        for (uint32_t x : t)
        {
            empty = empty || x == 0;
        }
        if (empty)
        {
            return IGNORED;
        }
        this->span.start(cycle);
        this->jobs = jobs;
        this->beats = t;
        // From the sink back: each firing of a consumer takes one result of its producer
        for (size_t r = this->order.size(); r-- > 0;)
        {
            size_t k = this->order[r];
            uint32_t n = this->outs[k].empty() ? jobs
                : this->counts[this->links[this->outs[k][0]].to];
            this->counts[k] = n * t[k];
        }
        for (size_t k = 0; k < this->u.size(); k++)
        {
            this->u[k].firings = 0;
            this->u[k].lane = 0;
        }
        for (int c = 0; c < NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
        return TAKEN;
    }

    // One busy cycle: inputs[k], every outer input of unit k has a beat (true
    // for a unit without one); outer_room[k], unit k's outer output has room
    // (true for a unit without one). The step is valid until the next call.
    const Step &step(int64_t cycle, const std::vector<bool> &inputs,
        const std::vector<bool> &outer_room)
    {
        size_t n = this->cfg.size();
        Step &s = this->stepped;
        std::fill(s.units.begin(), s.units.end(), UnitStep());
        std::fill(s.links.begin(), s.links.end(), LinkStep());
        s.cls = FLUSH;
        s.end = false;
        std::vector<bool> &avail = this->avail, &wants = this->wants,
            &would_fire = this->would_fire, &gives = this->gives, &head = this->head,
            &offer = this->offer;

        // Forward: what each unit offers whatever its room
        for (size_t k : this->order)
        {
            const UnitCfg &c = this->cfg[k];
            UnitState &us = this->u[k];
            bool linked = true;
            for (int i : this->ins[k])
            {
                const Link &e = this->links[i];
                linked = linked && (e.depth == 0 ? offer[e.from] : this->l[i].occupancy > 0);
            }
            avail[k] = inputs[k] && linked;
            bool ii_ok = !us.has_fired || cycle >= us.last_fire + c.ii;
            wants[k] = us.firings < this->counts[k] && ii_ok;
            would_fire[k] = wants[k] && avail[k] && (c.span == 1 || us.lane == c.span - 1);
            gives[k] = would_fire[k] && (us.firings + 1) % this->beats[k] == 0;
            head[k] = c.latency > 0 && us.slots[c.latency - 1];
            offer[k] = c.latency > 0 ? head[k] : gives[k];
        }

        // Backward: room, frozen, fire, read, push; an out-edge takes on its consumer's firing
        bool busy = false, waits = false;
        for (size_t r = n; r-- > 0;)
        {
            size_t k = this->order[r];
            const UnitCfg &c = this->cfg[k];
            UnitState &us = this->u[k];
            UnitStep &st = s.units[k];
            bool room = outer_room[k];
            for (int i : this->outs[k])
            {
                const Link &e = this->links[i];
                bool take = s.units[e.to].fire;
                room = room && (e.depth == 0 ? take : this->l[i].occupancy < e.depth || take);
            }
            st.frozen = c.latency > 0 ? head[k] && !room : gives[k] && !room;
            st.first = us.firings % this->beats[k] == 0;
            if (!st.frozen)
            {
                st.fire = would_fire[k];
                st.result = gives[k];
                st.push = c.latency > 0 ? head[k] : gives[k];
                st.read = c.span > 1 && wants[k] && avail[k];
                st.lane = us.lane;
                for (int i = c.latency - 1; i > 0; i--)
                {
                    us.slots[i] = us.slots[i - 1];
                }
                if (c.latency > 0)
                {
                    us.slots[0] = st.result;
                }
                bool in_gap = us.has_fired && cycle < us.last_fire + c.ii;
                busy = busy || st.fire || st.read || in_gap;
                waits = waits || (wants[k] && !inputs[k]);
            }
            if (st.fire)
            {
                us.has_fired = true;
                us.last_fire = cycle;
                us.firings++;
                us.lane = 0;
            }
            else if (st.read)
            {
                us.lane++;
            }
        }

        // The buffers: a load is the producer's push, a take the consumer's firing
        for (size_t i = 0; i < this->links.size(); i++)
        {
            const Link &e = this->links[i];
            LinkStep &ls = s.links[i];
            LinkState &state = this->l[i];
            if (e.depth == 0)
            {
                continue;
            }
            ls.load = s.units[e.from].push;
            ls.take = s.units[e.to].fire;
            ls.wslot = state.wptr;
            ls.rslot = state.rptr;
            if (ls.load)
            {
                state.wptr = (state.wptr + 1) % e.depth;
            }
            if (ls.take)
            {
                state.rptr = (state.rptr + 1) % e.depth;
            }
            state.occupancy += (int)ls.load - (int)ls.take;
            ls.occupancy = state.occupancy;
        }

        s.cls = s.units[this->output].frozen ? STALL_OUT : busy ? BUSY : waits ? STALL_IN : FLUSH;
        this->classes[s.cls]++;
        if (this->finished())
        {
            s.end = true;
            this->span.end(cycle);
            this->runs++;
        }
        return s;
    }

    // The head unit's firings in this run, and its count n
    uint32_t firings() const { return this->order.empty() ? 0 : this->u[this->order[0]].firings; }
    uint32_t count() const { return this->order.empty() ? 0 : this->counts[this->order[0]]; }

    // The summary line of the run that ended, run index from 0
    // (docs/EVENTS.md): its classes add up to its busy cycles
    std::string run_line() const
    {
        char line[160];
        snprintf(line, sizeof(line),
            "run index=%d firings=%u busy=%ld stall_in=%ld stall_out=%ld flush=%ld",
            this->runs - 1, this->firings(), (long)this->classes[BUSY],
            (long)this->classes[STALL_IN], (long)this->classes[STALL_OUT],
            (long)this->classes[FLUSH]);
        return line;
    }

    // The current or last run: its start s and last cycle E, its jobs, each
    // unit's T and n, and its cycles per class; runs ended so far
    SnaxRunSpan span;
    uint32_t jobs;
    std::vector<uint32_t> beats;
    std::vector<uint32_t> counts;
    int64_t classes[NB_CLASSES];
    int runs;

private:
    struct UnitState
    {
        std::vector<bool> slots;    // the pipeline, slot latency - 1 the head
        bool has_fired = false;
        int64_t last_fire = 0;
        uint32_t firings = 0;
        int lane = 0;
    };

    struct LinkState
    {
        int occupancy = 0;
        int wptr = 0;
        int rptr = 0;
    };

    // Every unit has fired its n, nothing in flight, every buffer empty
    bool finished() const
    {
        for (size_t k = 0; k < this->u.size(); k++)
        {
            if (this->u[k].firings != this->counts[k])
            {
                return false;
            }
            for (bool slot : this->u[k].slots)
            {
                if (slot)
                {
                    return false;
                }
            }
        }
        for (const LinkState &ls : this->l)
        {
            if (ls.occupancy)
            {
                return false;
            }
        }
        return true;
    }

    std::vector<UnitCfg> cfg;
    std::vector<Link> links;
    std::vector<std::vector<int>> ins, outs;    // per unit, its in- and out-edges (link indices)
    std::vector<size_t> order;                  // the units in topological order
    size_t output = 0;                          // the unit owning the outer output
    std::vector<UnitState> u;
    std::vector<LinkState> l;
    // step()'s, sized at configure: its result and its passes' per-unit values
    Step stepped;
    std::vector<bool> avail, wants, would_fire, gives, head, offer;
};


// SnaxGroupDatapaths: a group's datapaths (snax_datapath.hpp) wired as the
// component wires them, one per unit and one LinkBuffer per link of depth >=
// 1, so the component (snax_group.cpp) and the tests run the same cycle:
//
//   en = the rule's step
//   for each unit, producer before consumer: eval(its inputs' sources, en)
//   for each unit and buffer: commit(en)
//
// An input's source is an outer port (the streamer's beat, moved when the
// unit fires), a wire (the producer's output from its eval this cycle) or a
// buffer (its slot rslot, written in an earlier cycle). A unit takes each
// in-edge on that edge's to_input; its other inputs are outer, in port order.
// wire() takes the edges and the order from the configured rule.
class SnaxGroupDatapaths
{
public:
    std::vector<std::unique_ptr<SnaxDatapath>> units;
    std::vector<std::unique_ptr<SnaxDatapath>> buffers;     // per link; null for a wire

    // The rule's links, its topological order and the unit owning the outer output; per
    // unit and input, the link feeding it (-1: an outer input)
    void wire(const SnaxGroupRule &rule)
    {
        this->links = rule.edges();
        this->order = rule.topological();
        this->output = rule.output_unit();
        this->feeds.assign(this->units.size(), {});
        this->in.assign(this->units.size(), {});
        for (size_t k = 0; k < this->units.size(); k++)
        {
            this->feeds[k].assign(this->units[k]->in_words.size(), -1);
            this->in[k].assign(this->units[k]->in_words.size(), nullptr);
        }
        for (size_t i = 0; i < this->links.size(); i++)
        {
            this->feeds[this->links[i].to][this->links[i].to_input] = i;
        }
        this->en.assign(this->units.size(), SnaxEnables());
        this->ben.assign(this->buffers.size(), SnaxEnables());
        this->buffer_in.assign(1, nullptr);
    }

    // One cycle with the rule's step; outer[k], unit k's outer inputs' beats in port order
    // (any words when it does not fire). The outer output's unit's output, valid when it
    // pushes.
    const std::vector<uint64_t> &cycle(const SnaxGroupRule::Step &step,
        const std::vector<std::vector<const uint64_t *>> &outer)
    {
        std::vector<SnaxEnables> &en = this->en, &ben = this->ben;
        for (size_t k = 0; k < this->units.size(); k++)
        {
            const SnaxGroupRule::UnitStep &u = step.units[k];
            en[k].fire = u.fire;
            en[k].first = u.first;
            en[k].read = u.read;
            en[k].lane = u.lane;
            en[k].en = u.fire;
        }
        for (size_t i = 0; i < this->buffers.size(); i++)
        {
            ben[i].load = step.links[i].load;
            ben[i].wslot = step.links[i].wslot;
            ben[i].rslot = step.links[i].rslot;
        }
        for (size_t k : this->order)
        {
            std::vector<const uint64_t *> &in = this->in[k];
            size_t o = 0;
            for (size_t j = 0; j < in.size(); j++)
            {
                int i = this->feeds[k][j];
                if (i >= 0)
                {
                    const SnaxDatapath *src = this->buffers[i] ? this->buffers[i].get()
                        : this->units[this->links[i].from].get();
                    in[j] = src->out().data();
                }
                else
                {
                    in[j] = outer[k][o++];
                }
            }
            this->units[k]->eval(in, en[k]);
            for (size_t i = 0; i < this->links.size(); i++)
            {
                if (this->links[i].from == (int)k && this->buffers[i])
                {
                    this->buffer_in[0] = this->units[k]->out().data();
                    this->buffers[i]->eval(this->buffer_in, ben[i]);
                }
            }
        }
        for (size_t k = 0; k < this->units.size(); k++)
        {
            this->units[k]->commit(en[k]);
        }
        for (size_t i = 0; i < this->buffers.size(); i++)
        {
            if (this->buffers[i])
            {
                this->buffers[i]->commit(ben[i]);
            }
        }
        return this->units[this->output]->out();
    }

private:
    std::vector<SnaxGroupRule::Link> links;
    std::vector<size_t> order;
    size_t output = 0;
    std::vector<std::vector<int>> feeds;
    // cycle()'s, sized at wire(): the enables, each unit's input words, a buffer's input
    std::vector<SnaxEnables> en, ben;
    std::vector<std::vector<const uint64_t *>> in;
    std::vector<const uint64_t *> buffer_in;
};
