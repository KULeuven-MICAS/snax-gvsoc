/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxGroupRule: the control model of one group of an accelerator, snax-forge's
// control rule: the `<tag>_<group>_ctrl` of its
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
// outer inputs, if any, come from the streamer. A group is one or more
// chains, each a path of links from a head to a sink, the unit without an
// out-edge, which owns one outer output: configure() refuses a unit with two
// out-edges or two in-edges (a fork or a join of links), a cycle, and chains
// no fork joins. Chains meet only at a forked outer input, one
// reader's for the heads of several chains (each of span 1): its beat is
// taken only when every one of them fires, so a head that would fire waits
// while another cannot (step() decides the cycle again with it blocked, as
// snax_group_rule.py does).
//
// A run: a start offered in cycle s carries a JOBS per output (each chain's)
// and each unit's T; unit k fires n_k times, JOBS * T for a sink, n_succ * T_k
// for a unit before it (each firing of its consumer takes one of its
// results): over a chain, its JOBS * prod T_v over k and every unit after
// it. It is taken only when the group is idle in s and no number is 0 (a
// JOBS 0 or any T 0 is the empty run, which the shell ends without the
// group: here it is ignored, busy stays 0); a start while busy is refused. The group is busy from s + 1 to the
// run's last cycle E, when every unit has fired its n and nothing is in
// flight. step() is called once per busy cycle with, per unit, whether its
// outer inputs all have a beat and whether its outer output has room (true for
// a unit without one).
//
// A seeded fold (TreeAccumulate, SerialAccumulate, or a Mac) has
// one more outer input, its seed, one beat per job: its input has a beat when its other
// inputs have one and, on its job's first beat (d = 0), its seed has one
// (fire = a.valid and (not first or seed.valid)); the seed is taken with the
// job's first firing (seed.ready = fire and first, UnitStep::seed). A seed
// missing when wanted is stall_in, as a missing outer beat.
//
// A bank, a unit of rows R > 1 (a Mac's, a chain's sink), keeps R
// rows of sums, one a firing in turn: its row is d mod ROWS, ROWS (at most R,
// from its CSR at the start) the rows a run uses, T a multiple of it. first =
// [d < ROWS] (a seed taken on each), and it gives on its job's last ROWS
// firings (d >= T - ROWS), so a job gives ROWS results. Its held
// inputs (a broadcast read once a row and kept) count only on a row's first
// firing (d mod ROWS = 0): outer_ok also needs holds[k] there, and the firing
// takes them (UnitStep::take); on its other firings the unit uses the beat it
// kept. A carried seed is any seed to the rule; the component gives its
// datapath 0 in its place while the job (UnitStep::job) is below CARRY.
//
// Per unit: its job_beats_counter d (its firings mod T, here derived
// from its firings; first = [d = 0], it gives a result on firings with d =
// T - 1; the Chisel keeps it as a counter, and counts each unit's results in
// nested counters, never against n_k; the RTL counts the same
// way, so a change here must match the Chisel), an L-deep pipeline that stalls
// as a whole when its head cannot be pushed, at most one firing per II (the
// II counts cycles from the unit's last firing; a stall does not restart it,
// and it carries over to the next run), and a lane counter when span > 1. A
// unit wants to fire while it has firings left and its II allows. Its input
// has a beat when each of its outer inputs has one and each in-edge offers
// one: a wire offers what its producer presents this cycle (its pipeline's
// head, or with L = 0 a firing that gives a result), a buffer its oldest beat
// (occupancy > 0: a beat written in an earlier cycle). A unit reads its
// input in each cycle it wants to, its input has a beat and it is not frozen,
// at every span: one of span S reads lane l of the beat in place (the lane
// counter) and fires (takes the beat) on lane S - 1, so its throughput is one
// beat per max(II, S); at span 1 the read is its firing. A
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
// Each busy cycle is one class, judged at the units owning the outer
// outputs, in this order: stall_out (one has a result and no room: it is frozen) >
// busy (any unit fires or reads, or is in its II gap) > stall_in (a unit with
// outer inputs wants to fire and one of them has no beat) > flush (results in
// flight, beats in a buffer: accel.py's idle). busy + stall_in + stall_out +
// flush is the run's busy cycles, E - s, E the cycle the last chain ends;
// the run line's firings are the head's (the first unit in the topological
// order).
//
// SnaxPacker: the outer output's packer, when its d_out results fill one 64-bit
// word (a one-lane int32 fold at d_out 2, int16 at 4, int8 at 8), placed
// between the owning unit and its writer as the Chisel's FifoPacker. A run clears
// its slice pointer; each push puts the result's low 64 / d_out bits at the
// slice; the word goes to the writer when the slice is d_out - 1 (full) or the
// push is the run's last, the slices above it zero, and the pointer clears. Only
// such a sending push needs the writer: room(ready, last) is the unit's outer
// room, true on a filling push, so no cycle is added and only the writer's
// beats drop by d_out. last is the run's last result, from the count of pushes
// (pushes == results - 1), never from this cycle's push, so room does not
// depend on itself. At d_out 1 every push sends, unchanged.
//
// SnaxSlicer: an outer input's slicer, when its lanes W are fewer than a
// word's elements and divide them (int32 W = 1; int16 W = 1, 2; int8 W = 1,
// 2, 4), placed between the reader and the unit as the Chisel's
// FifoSlicer, the packer's mirror. It holds one 64-bit word and gives d_in =
// elements / W pops of it, low slice first, each slice W lanes in the low
// bits of the unit's beat. The unit sees full, not the reader's valid; a
// firing (a seed input: the firing that takes the seed) pops the slice at
// count, the d_in-th empties it. It takes the reader's word when it is empty
// or on its last pop, judged on its state before the cycle's pop, and only in
// busy cycles, so the word shows the cycle after (the RTL's registered
// output). A run's start drops what it holds.
//
// snax_broadcast: a broadcast input's wires, on an input of a datapath
// whose lanes compute on their own (SimdLanes, Mac): its reader, or its slicer
// sized by one lane (d_in = 64 / width), gives one lane a beat, and each of the
// unit's W lanes takes that lane, in the unit's words of its type. No register
// and no cycle of its own, so the rule does not see it; a linked port is never
// one.

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
        bool seeded = false;    // one more outer input, its seed, taken once per job
        int rows = 1;           // a bank's rows R: ROWS at most R per run
        bool held = false;      // it has held inputs, taken on a row's first firing
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
        bool gives = false;     // the firing gives a result (d = T - 1)
        bool push = false;      // a result given to the outer output or the link
        bool read = false;      // lane `lane` read in place (at span 1, the firing)
        int lane = 0;
        bool first = false;     // the beat fired or read is its job's first (d = 0)
        bool frozen = false;    // its head (or, L = 0, a giving firing) had no room
        bool seed = false;      // its seed taken (a seeded unit's fire on its job's first beat)
        bool take = false;      // its held inputs taken (a firing on a row's first beat)
        int row = 0;            // a bank's row of the beat fired or read: d mod ROWS
        uint32_t job = 0;       // the job of the beat fired or read in this run: firings / T
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

    // The units, the links between them, the units owning the outer outputs (the chains'
    // sinks, in the order of the start's JOBS and their room; empty: the sinks in unit
    // order) and the forks, each the units an outer input's one reader feeds.
    // Returns why the graph is refused, or "" (then the rule is configured).
    std::string configure(const std::vector<UnitCfg> &units, const std::vector<Link> &links,
        const std::vector<int> &outputs = {}, const std::vector<std::vector<int>> &forks = {})
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
            if (units[k].rows < 1 || (units[k].rows > 1 && !outs[k].empty()) ||
                (units[k].held && units[k].rows == 1))
            {
                return "unit " + std::to_string(k) + ": rows " + std::to_string(units[k].rows) +
                    (units[k].held ? ", held inputs" : "") + "; a bank has one row or more, is a "
                    "chain's sink, and a hold counts its rows";
            }
            if (outs[k].size() > 1 || ins[k].size() > 1)
            {
                bool fork = outs[k].size() > 1;
                return "unit " + std::to_string(k) + " has " +
                    std::to_string(fork ? outs[k].size() : ins[k].size()) +
                    (fork ? " out-edges (a fork)" : " in-edges (a join)") +
                    ": a chain has neither";
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
        std::vector<int> sinks;
        for (size_t k = 0; k < n; k++)
        {
            if (outs[k].empty())
            {
                sinks.push_back(k);
            }
        }
        std::vector<int> mine = outputs.empty() ? sinks : outputs;
        std::vector<int> sorted = mine;
        std::sort(sorted.begin(), sorted.end());
        if (sorted != sinks)
        {
            return "the outer outputs' units: each chain's sink owns one, and only it";
        }
        // Each unit's chain: the output its path of links ends at
        std::vector<int> chain(n, 0);
        for (size_t o = 0; o < mine.size(); o++)
        {
            for (int k = mine[o];; k = links[ins[k][0]].from)
            {
                chain[k] = o;
                if (ins[k].empty())
                {
                    break;
                }
            }
        }
        // The forks: two or more heads of span 1 each; their chains joined
        std::vector<int> joined(mine.size());
        for (size_t o = 0; o < joined.size(); o++)
        {
            joined[o] = o;
        }
        auto root = [&](int o) {
            while (joined[o] != o)
            {
                o = joined[o];
            }
            return o;
        };
        for (const std::vector<int> &f : forks)
        {
            std::vector<int> members = f;
            std::sort(members.begin(), members.end());
            if (f.size() < 2 || std::unique(members.begin(), members.end()) != members.end())
            {
                return "a fork gives one input to two or more units";
            }
            for (int k : f)
            {
                if (k < 0 || k >= (int)n || !ins[k].empty() || units[k].span != 1)
                {
                    return "fork: unit " + std::to_string(k) + " is not a chain's head of span 1";
                }
                joined[root(chain[k])] = root(chain[f[0]]);
            }
        }
        for (size_t o = 1; o < mine.size(); o++)
        {
            if (root(o) != root(0))
            {
                return "the chains ending at units " + std::to_string(mine[0]) + " and " +
                    std::to_string(mine[o]) + ": no fork joins them; a group's chains share an "
                    "input";
            }
        }
        this->cfg = units;
        this->links = links;
        this->ins = ins;
        this->outs = outs;
        this->order = order;
        this->outputs = mine;
        this->chain = chain;
        this->forks = forks;
        this->u.assign(n, UnitState());
        this->l.assign(links.size(), LinkState());
        this->stepped.units.assign(n, UnitStep());
        this->stepped.links.assign(links.size(), LinkStep());
        for (std::vector<bool> *v : {&this->avail, &this->wants, &this->would_fire, &this->gives,
            &this->head, &this->offer, &this->outer_ok, &this->blocked})
        {
            v->assign(n, false);
        }
        this->reset();
        return "";
    }

    void reset()
    {
        this->span.reset();
        this->jobs.assign(this->outputs.size(), 0);
        this->job_beats.assign(this->cfg.size(), 1);
        this->rows.assign(this->cfg.size(), 1);
        this->firings_per_run.assign(this->cfg.size(), 0);
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

    // The units in topological order, the head first; the units owning the outer outputs, in
    // the start's order (the first: output_unit); each unit's output (its chain's index there)
    const std::vector<size_t> &topological() const { return this->order; }
    const std::vector<int> &output_units() const { return this->outputs; }
    size_t output_unit() const { return this->outputs[0]; }
    const std::vector<int> &chains() const { return this->chain; }
    const std::vector<Link> &edges() const { return this->links; }

    // Idle in cycle: no run, or the last one ended before it
    bool idle(int64_t cycle) const { return this->span.idle(cycle); }

    // Busy in cycle: from the cycle after the start to the run's last cycle
    bool busy(int64_t cycle) const { return this->span.busy(cycle); }

    // Each unit's firings in a run of jobs (one per output), unit k a result every
    // job_beats[k] firings: from each sink back, each firing of a consumer takes one result
    // of its producer
    std::vector<uint64_t> firings_for(const std::vector<uint32_t> &jobs,
        const std::vector<uint32_t> &job_beats) const
    {
        std::vector<uint64_t> n(this->cfg.size(), 0);
        for (size_t r = this->order.size(); r-- > 0;)
        {
            size_t k = this->order[r];
            uint64_t next = this->outs[k].empty() ? jobs[this->chain[k]]
                : n[this->links[this->outs[k][0]].to];
            n[k] = next * job_beats[k];
        }
        return n;
    }

    // A start of jobs (one per output, in output_units' order), unit k a result every
    // job_beats[k] firings, its bank's ROWS rows[k] (empty: 1 each), offered in cycle; the
    // caller keeps every n_k within 32 bits and each ROWS from 1 to its rows, dividing its T
    Start start(int64_t cycle, const std::vector<uint32_t> &jobs,
        const std::vector<uint32_t> &job_beats, const std::vector<uint32_t> &rows = {})
    {
        if (!this->idle(cycle))
        {
            return REFUSED;
        }
        bool empty = false;
        for (uint32_t x : jobs)
        {
            empty = empty || x == 0;
        }
        for (uint32_t x : job_beats)
        {
            empty = empty || x == 0;
        }
        if (empty)
        {
            return IGNORED;
        }
        this->span.start(cycle);
        this->jobs = jobs;
        this->job_beats = job_beats;
        this->rows = rows.empty() ? std::vector<uint32_t>(this->cfg.size(), 1) : rows;
        std::vector<uint64_t> n = this->firings_for(jobs, job_beats);
        for (size_t k = 0; k < n.size(); k++)
        {
            this->firings_per_run[k] = (uint32_t)n[k];
            this->u[k].firings = 0;
            this->u[k].lane = 0;
        }
        for (int c = 0; c < NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
        return TAKEN;
    }

    // A start of one chain's jobs
    Start start(int64_t cycle, uint32_t jobs, const std::vector<uint32_t> &job_beats)
    {
        return this->start(cycle, std::vector<uint32_t>(this->outputs.size(), jobs), job_beats);
    }

    // One busy cycle: inputs[k], every outer input of unit k but its seed has
    // a beat (true for a unit without one; a forked input's for each of its
    // units); outer_room[k], unit k's outer output has room (true for a unit
    // without one); seeds[k], a seeded unit's seed has a beat (any value for
    // one not seeded). The step is valid until the next call.
    const Step &step(int64_t cycle, const std::vector<bool> &inputs,
        const std::vector<bool> &outer_room)
    {
        this->no_seeds.assign(this->cfg.size(), true);
        return this->step(cycle, inputs, this->no_seeds, outer_room);
    }

    const Step &step(int64_t cycle, const std::vector<bool> &inputs,
        const std::vector<bool> &seeds, const std::vector<bool> &outer_room)
    {
        this->no_holds.assign(this->cfg.size(), true);
        return this->step(cycle, inputs, seeds, this->no_holds, outer_room);
    }

    // holds[k], a unit's held inputs have a beat (any value for one without); its other
    // outer inputs are in inputs[k]
    const Step &step(int64_t cycle, const std::vector<bool> &inputs,
        const std::vector<bool> &seeds, const std::vector<bool> &holds,
        const std::vector<bool> &outer_room)
    {
        size_t n = this->cfg.size();
        Step &s = this->stepped;
        bool busy = false, waits = false;
        // NB (D189): a forked input's units fire together; one that would fire waits while
        // another cannot, so the cycle is decided again with it blocked
        std::fill(this->blocked.begin(), this->blocked.end(), false);
        while (true)
        {
            this->decide(cycle, inputs, seeds, holds, outer_room, &busy, &waits);
            bool held = false;
            for (const std::vector<int> &f : this->forks)
            {
                bool all = true;
                for (int k : f)
                {
                    all = all && s.units[k].fire;
                }
                for (int k : f)
                {
                    if (!all && s.units[k].fire)
                    {
                        this->blocked[k] = true;
                        held = true;
                    }
                }
            }
            if (!held)
            {
                break;
            }
        }

        // The units' state: the pipeline advances unless frozen, a firing counts
        for (size_t k = 0; k < n; k++)
        {
            const UnitCfg &c = this->cfg[k];
            UnitState &us = this->u[k];
            const UnitStep &st = s.units[k];
            if (!st.frozen)
            {
                for (int i = c.latency - 1; i > 0; i--)
                {
                    us.slots[i] = us.slots[i - 1];
                }
                if (c.latency > 0)
                {
                    us.slots[0] = st.gives;
                }
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

        bool frozen = false;
        for (int k : this->outputs)
        {
            frozen = frozen || s.units[k].frozen;
        }
        s.cls = frozen ? STALL_OUT : busy ? BUSY : waits ? STALL_IN : FLUSH;
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
    uint32_t count() const { return this->order.empty() ? 0 : this->firings_per_run[this->order[0]]; }

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

    // The current or last run: its start s and last cycle E, its jobs (per output), each
    // unit's T and n, and its cycles per class; runs ended so far
    SnaxRunSpan span;
    std::vector<uint32_t> jobs;
    std::vector<uint32_t> job_beats;        // per unit, its T: a result every T-th firing
    std::vector<uint32_t> rows;             // per unit, its ROWS: the bank's rows used
    std::vector<uint32_t> firings_per_run;  // per unit, its n
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

    // One cycle's choices into stepped.units, changing no state, the units blocked not
    // firing: forward, what each unit offers whatever its room; backward, in reverse order,
    // room, frozen, fire, read, push (an out-edge takes on its consumer's firing); *busy and
    // *waits for the cycle's class
    void decide(int64_t cycle, const std::vector<bool> &inputs, const std::vector<bool> &seeds,
        const std::vector<bool> &holds, const std::vector<bool> &outer_room, bool *busy,
        bool *waits)
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

        for (size_t k : this->order)
        {
            const UnitCfg &c = this->cfg[k];
            const UnitState &us = this->u[k];
            bool linked = true;
            for (int i : this->ins[k])
            {
                const Link &e = this->links[i];
                linked = linked && (e.depth == 0 ? offer[e.from] : this->l[i].occupancy > 0);
            }
            // a seeded unit's job's first beats (a bank's row's each) wait for its seed too;
            // NB (D190): a held input's beat is needed only on a row's first firing
            uint32_t d = us.firings % this->job_beats[k];
            bool first = d < this->rows[k];
            bool taking = us.firings % this->rows[k] == 0;
            this->outer_ok[k] = inputs[k] && (!c.seeded || !first || seeds[k]) &&
                (!c.held || !taking || holds[k]);
            avail[k] = this->outer_ok[k] && linked;
            bool ii_ok = !us.has_fired || cycle >= us.last_fire + c.ii;
            wants[k] = us.firings < this->firings_per_run[k] && ii_ok && !this->blocked[k];
            would_fire[k] = wants[k] && avail[k] && (c.span == 1 || us.lane == c.span - 1);
            // NB (D191): a bank gives on its job's last ROWS firings
            gives[k] = would_fire[k] && d >= this->job_beats[k] - this->rows[k];
            head[k] = c.latency > 0 && us.slots[c.latency - 1];
            offer[k] = c.latency > 0 ? head[k] : gives[k];
        }

        *busy = *waits = false;
        for (size_t r = n; r-- > 0;)
        {
            size_t k = this->order[r];
            const UnitCfg &c = this->cfg[k];
            const UnitState &us = this->u[k];
            UnitStep &st = s.units[k];
            bool room = outer_room[k];
            for (int i : this->outs[k])
            {
                const Link &e = this->links[i];
                bool take = s.units[e.to].fire;
                room = room && (e.depth == 0 ? take : this->l[i].occupancy < e.depth || take);
            }
            st.frozen = c.latency > 0 ? head[k] && !room : gives[k] && !room;
            st.first = us.firings % this->job_beats[k] < this->rows[k];
            st.row = us.firings % this->rows[k];
            st.job = us.firings / this->job_beats[k];
            if (!st.frozen)
            {
                st.fire = would_fire[k];
                st.gives = gives[k];
                st.push = c.latency > 0 ? head[k] : gives[k];
                st.read = wants[k] && avail[k];
                st.lane = us.lane;
                bool in_gap = us.has_fired && cycle < us.last_fire + c.ii;
                *busy = *busy || st.fire || st.read || in_gap;
                *waits = *waits || (wants[k] && !this->outer_ok[k]);
            }
            st.seed = st.fire && st.first && c.seeded;
            st.take = st.fire && st.row == 0 && c.held;
        }
    }

    // Every unit has fired its n, nothing in flight, every buffer empty
    bool finished() const
    {
        for (size_t k = 0; k < this->u.size(); k++)
        {
            if (this->u[k].firings != this->firings_per_run[k])
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
    std::vector<int> outputs;                   // the units owning the outer outputs
    std::vector<int> chain;                     // per unit, its chain's output (an index there)
    std::vector<std::vector<int>> forks;        // per fork, its units
    std::vector<UnitState> u;
    std::vector<LinkState> l;
    // step()'s, sized at configure: its result and its passes' per-unit values
    Step stepped;
    std::vector<bool> avail, wants, would_fire, gives, head, offer, outer_ok, blocked;
    std::vector<bool> no_seeds;     // the three-argument step's seeds, all there
    std::vector<bool> no_holds;     // the four-argument step's held inputs, all there
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
// in-edge on that edge's to_input; its other inputs are outer, in port order
// (a forked input's beat given to each of its units). wire() takes the edges
// and the order from the configured rule.
class SnaxGroupDatapaths
{
public:
    std::vector<std::unique_ptr<SnaxDatapath>> units;
    std::vector<std::unique_ptr<SnaxDatapath>> buffers;     // per link; null for a wire

    // The rule's links, its topological order and the unit owning the first outer output;
    // per unit and input, the link feeding it (-1: an outer input)
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
    // (any words when it does not fire). The first outer output's unit's output, valid when
    // it pushes; any unit's is out(k).
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
            en[k].row = u.row;
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

    // Unit k's output after the last cycle()
    const std::vector<uint64_t> &out(size_t k) const { return this->units[k]->out(); }

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



// The Chisel's FifoPacker, cycle for cycle (module doc)
struct SnaxPacker
{
    int d_out = 1;
    int slice = 0;
    uint64_t word = 0;

    void clear()
    {
        this->slice = 0;
        this->word = 0;
    }

    bool sending(bool last) const
    {
        return this->slice == this->d_out - 1 || last;
    }

    bool room(bool ready, bool last) const
    {
        return ready || !this->sending(last);
    }

    // A push of value: true, with the word in *out, when it sends
    bool push(uint64_t value, bool last, uint64_t *out)
    {
        const int bits = 64 / this->d_out;
        const uint64_t mask = bits == 64 ? ~(uint64_t)0 : (((uint64_t)1 << bits) - 1);
        if (this->slice == 0)
        {
            this->word = 0;
        }
        this->word |= (value & mask) << (this->slice * bits);
        if (this->sending(last))
        {
            *out = this->word;
            this->slice = 0;
            return true;
        }
        this->slice++;
        return false;
    }
};


// The RTL's <unit>_<port>_bcast, wires: lane 0 of beat, given to each of lanes
// lanes of type t in out (snax_words(lanes, t) words), within the cycle (module doc)
inline void snax_broadcast(const uint64_t *beat, int lanes, SnaxType t, uint64_t *out)
{
    const uint64_t x = snax_lane_get(beat, t.width, 0);
    std::fill(out, out + snax_words(lanes, t), 0);     // snax_lane_set ORs into a word
    for (int l = 0; l < lanes; l++)
    {
        snax_lane_set(out, t.width, l, x);
    }
}


// The Chisel's FifoSlicer, cycle for cycle (module doc)
struct SnaxSlicer
{
    int d_in = 1;
    bool full = false;
    int count = 0;
    uint64_t word = 0;

    void clear()
    {
        this->full = false;
        this->count = 0;
        this->word = 0;
    }

    // Whether it takes the reader's word this cycle, on its state before the cycle's pop:
    // empty, or pop is its last
    bool open(bool pop) const
    {
        return !this->full || (pop && this->count == this->d_in - 1);
    }

    // A pop: the slice at count, in the low bits; the last empties it
    uint64_t pop()
    {
        const int bits = 64 / this->d_in;
        const uint64_t mask = bits == 64 ? ~(uint64_t)0 : (((uint64_t)1 << bits) - 1);
        uint64_t slice = (this->word >> (this->count * bits)) & mask;
        if (this->count == this->d_in - 1)
        {
            this->full = false;
            this->count = 0;
        }
        else
        {
            this->count++;
        }
        return slice;
    }

    // A word taken from the reader, its first slice next
    void take(uint64_t word)
    {
        this->word = word;
        this->full = true;
        this->count = 0;
    }
};
