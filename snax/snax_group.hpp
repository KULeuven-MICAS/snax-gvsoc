/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxGroupRule: the control model of one group of an accelerator, snax-forge
// C§17's Control paragraph (D146, D147): the `<tag>_<group>_ctrl` of its
// Chisel, which drives the group's datapaths (snax_datapath.hpp) with their
// enables, every cycle. Plain C++, so the component (snax_group.cpp) and the
// standalone tests (tests/snax/unit/, tests/snax/group/) run the same code,
// as snax_sparse_arb.hpp. SnaxUnitRule, below, is its one-unit case.
//
// A group is a chain of units, unit 0 the head: link k (if the group has
// more than one unit) joins unit k's output to unit k + 1's input, of depth D
// (0 a wire, >= 1 a buffer of D beats, a LinkBuffer). Each unit has its
// latency L, its II, its span (the cycles it reads one input beat in place,
// SerialAccumulate's lanes) and, per run, its T: a result every T-th firing
// (a fold's JOB_BEATS or params.T; 1 for a unit without a fold). Each unit's
// outer inputs, if any, come from the streamer; the last unit's output is the
// group's outer output.
//
// A run (snax-forge D146): a start offered in cycle s carries JOBS and each
// unit's T; unit k fires n_k = JOBS * prod T_v times over k and every unit v
// after it (C§17's firings; the head's n is JOBS * prod T). It is taken only
// when the group is idle in s and no number is 0 (JOBS 0 or any T 0 is the
// empty run, which the shell ends without the group: here it is ignored, busy
// stays 0); a start while busy is refused. The group is busy from s + 1 to the
// run's last cycle E, the push of the last unit's n-th result (done is the
// last unit's JOBS-th result). step() is called once per busy cycle with,
// per unit, whether its outer inputs all have a beat, and whether the outer
// output has room.
//
// Per unit (C§17): its beat digit d (its firings mod T: first = [d = 0], it
// gives a result on firings with d = T - 1), an L-deep pipeline that stalls
// as a whole when its head cannot be pushed, at most one firing per II (the
// II counts cycles from the unit's last firing; a stall does not restart it,
// and it carries over to the next run), and a lane counter when span > 1. A
// unit wants to fire while it has firings left and its II allows. Its input
// has a beat when each of its outer inputs has one and, for unit k > 0, its
// link offers one: a wire offers what unit k - 1 presents this cycle (its
// pipeline's head, or with L = 0 a firing that gives a result), a buffer its
// oldest beat (occupancy > 0: a beat written in an earlier cycle). A unit of
// span 1 fires when it wants to and its input has a beat; one of span S reads
// lane l of the beat in place (the lane counter) in each such cycle and fires
// (takes the beat) on lane S - 1, so its throughput is one beat per
// max(II, S). A result from a firing in t is pushed in t + L when nothing
// stalls, into the outer output (the last unit) or the link: a unit gives
// into a link when it has room or the next unit takes in that cycle (a wire:
// only when the next unit takes; a buffer: occupancy < D, or a take). So at
// depth 0 a unit holds its result until its reader takes it, at span S its
// last lane. With L = 0 a firing that gives a result with no room is a stall
// (L = 0, II 1 is lockstep). A firing enters slot 0 in the cycle the head is
// pushed: with L = 1 and II 1 the next input is taken as a result leaves.
// A wire chain is B1's nest with L = sum L_k, plus one enable per stage:
// fire_{k+1}(c) = fire_k(c - L_k) and gives_k(c - L_k).
//
// The cycle is decided in two passes: forward, what each unit offers on its
// output whatever its room (its head, or with L = 0 a firing that gives), so
// each unit knows whether its input has a beat; backward from the last unit,
// whether each is frozen (its head, or with L = 0 a giving firing, has no
// room), fires and reads, and so whether it takes, which is its producer's
// room. Then each buffer's occupancy: + 1 on a load (its producer's push), -
// 1 on a take, its write and read slots a ring.
//
// Each busy cycle is one class, judged at the group's boundary, in D59's
// order: stall_out (the last unit has a result and no room: it is frozen) >
// busy (any unit fires or reads, or is in its II gap) > stall_in (a unit with
// outer inputs wants to fire and one of them has no beat) > flush (results in
// flight, beats in a buffer: accel.py's idle). For one unit these are
// SnaxUnitRule's classes as they were. busy + stall_in + stall_out + flush
// is the run's busy cycles, E - s; the run line's firings are the head's.

#pragma once

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>


// The classes by name, as a run line and the class lines give them
static const char *const snax_unit_class_names[] = {"busy", "stall_in", "stall_out", "flush"};


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

    // What one buffer does: its LinkBuffer's load, wslot, rslot
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

    // The units, head first, and the depth of each link (one fewer)
    void configure(const std::vector<UnitCfg> &units, const std::vector<int> &depths)
    {
        this->cfg = units;
        this->depths = depths;
        this->u.assign(units.size(), UnitState());
        for (size_t k = 0; k < units.size(); k++)
        {
            this->u[k].slots.assign(units[k].latency, false);
        }
        this->l.assign(depths.size(), LinkState());
        this->reset();
    }

    void reset()
    {
        this->started = false;
        this->start_cycle = 0;
        this->end_cycle = -1;
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

    // Idle in cycle: no run, or the last one ended before it
    bool idle(int64_t cycle) const
    {
        return !this->started || (this->end_cycle != -1 && this->end_cycle < cycle);
    }

    // Busy in cycle: from the cycle after the start to the run's last cycle
    bool busy(int64_t cycle) const
    {
        return this->started && cycle > this->start_cycle &&
            (this->end_cycle == -1 || cycle <= this->end_cycle);
    }

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
        this->started = true;
        this->start_cycle = cycle;
        this->end_cycle = -1;
        this->jobs = jobs;
        this->beats = t;
        uint32_t n = jobs;
        for (size_t k = this->cfg.size(); k-- > 0;)
        {
            n *= t[k];
            this->counts[k] = n;
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
    // for a unit without one); room, the outer output has room
    Step step(int64_t cycle, const std::vector<bool> &inputs, bool room)
    {
        size_t n = this->cfg.size();
        Step s;
        s.units.assign(n, UnitStep());
        s.links.assign(this->depths.size(), LinkStep());
        std::vector<bool> avail(n), wants(n), would_fire(n), gives(n), head(n), offer(n);

        // Forward: what each unit offers whatever its room
        for (size_t k = 0; k < n; k++)
        {
            const UnitCfg &c = this->cfg[k];
            UnitState &us = this->u[k];
            bool linked = true;
            if (k > 0)
            {
                linked = this->depths[k - 1] == 0 ? offer[k - 1] : this->l[k - 1].occupancy > 0;
            }
            avail[k] = inputs[k] && linked;
            bool ii_ok = !us.has_fired || cycle >= us.last_fire + c.ii;
            wants[k] = us.firings < this->counts[k] && ii_ok;
            would_fire[k] = wants[k] && avail[k] && (c.span == 1 || us.lane == c.span - 1);
            gives[k] = would_fire[k] && (us.firings + 1) % this->beats[k] == 0;
            head[k] = c.latency > 0 && us.slots[c.latency - 1];
            offer[k] = c.latency > 0 ? head[k] : gives[k];
        }

        // Backward: frozen, fire, read, push; each unit's take is its producer's room
        bool unit_room = room;
        bool busy = false, waits = false;
        for (size_t k = n; k-- > 0;)
        {
            const UnitCfg &c = this->cfg[k];
            UnitState &us = this->u[k];
            UnitStep &st = s.units[k];
            st.frozen = c.latency > 0 ? head[k] && !unit_room : gives[k] && !unit_room;
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
            if (k > 0)
            {
                bool take = st.fire;
                const LinkState &ls = this->l[k - 1];
                unit_room = this->depths[k - 1] == 0 ? take
                    : ls.occupancy < this->depths[k - 1] || take;
            }
        }

        // The buffers: a load is the producer's push, a take the consumer's firing
        for (size_t k = 0; k < this->depths.size(); k++)
        {
            int depth = this->depths[k];
            LinkStep &ls = s.links[k];
            LinkState &state = this->l[k];
            if (depth == 0)
            {
                continue;
            }
            ls.load = s.units[k].push;
            ls.take = s.units[k + 1].fire;
            ls.wslot = state.wptr;
            ls.rslot = state.rptr;
            if (ls.load)
            {
                state.wptr = (state.wptr + 1) % depth;
            }
            if (ls.take)
            {
                state.rptr = (state.rptr + 1) % depth;
            }
            state.occupancy += (int)ls.load - (int)ls.take;
            ls.occupancy = state.occupancy;
        }

        s.cls = s.units[n - 1].frozen ? STALL_OUT : busy ? BUSY : waits ? STALL_IN : FLUSH;
        this->classes[s.cls]++;
        if (this->finished())
        {
            s.end = true;
            this->end_cycle = cycle;
            this->runs++;
        }
        return s;
    }

    // The head unit's firings in this run
    uint32_t firings() const { return this->u.empty() ? 0 : this->u[0].firings; }
    uint32_t unit_firings(size_t k) const { return this->u[k].firings; }
    uint32_t count() const { return this->counts.empty() ? 0 : this->counts[0]; }

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

    // The current or last run: its start s, its last cycle E (-1 while busy),
    // its jobs, each unit's T and n, and its cycles per class; runs ended so far
    int64_t start_cycle;
    int64_t end_cycle;
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
    std::vector<int> depths;
    std::vector<UnitState> u;
    std::vector<LinkState> l;
    bool started = false;
};


// SnaxUnitRule: SnaxGroupRule of one unit (the nest controller of B1, D147),
// with its interface as it was: a start carries jobs and job_beats (T), and
// step() one bool for every input's beat. A run fires jobs * job_beats times
// and gives a result on every job_beats-th firing; with L = 0 the result is
// pushed in its firing cycle, else L cycles later, the pipeline stalling as a
// whole when its head has no room; II counts from the last firing and carries
// over to the next run. Its classes are the group's: stall_out > busy (fired,
// or in the II gap) > stall_in (II allows, an input has no beat) > flush.
class SnaxUnitRule
{
public:
    using Class = SnaxGroupRule::Class;
    using Start = SnaxGroupRule::Start;
    static const Class BUSY = SnaxGroupRule::BUSY;
    static const Class STALL_IN = SnaxGroupRule::STALL_IN;
    static const Class STALL_OUT = SnaxGroupRule::STALL_OUT;
    static const Class FLUSH = SnaxGroupRule::FLUSH;
    static const int NB_CLASSES = SnaxGroupRule::NB_CLASSES;
    static const Start TAKEN = SnaxGroupRule::TAKEN;
    static const Start IGNORED = SnaxGroupRule::IGNORED;
    static const Start REFUSED = SnaxGroupRule::REFUSED;

    struct Step
    {
        bool fire;      // a beat taken from every input
        bool result;    // the firing gives a result (every job_beats-th firing)
        bool push;      // a beat given to the output
        Class cls;
        bool end;       // the run's last cycle: idle from the next one
    };

    // L >= 0 and II >= 1; L = 0, II 1 is lockstep
    void configure(int latency, int ii)
    {
        SnaxGroupRule::UnitCfg c;
        c.latency = latency;
        c.ii = ii;
        this->group.configure({c}, {});
        this->sync();
    }

    void reset()
    {
        this->group.reset();
        this->sync();
    }

    bool idle(int64_t cycle) const { return this->group.idle(cycle); }
    bool busy(int64_t cycle) const { return this->group.busy(cycle); }

    Start start(int64_t cycle, uint32_t jobs, uint32_t job_beats = 1)
    {
        Start s = this->group.start(cycle, jobs, {job_beats});
        this->sync();
        return s;
    }

    Step step(int64_t cycle, bool inputs, bool room)
    {
        SnaxGroupRule::Step g = this->group.step(cycle, {inputs}, room);
        this->sync();
        const SnaxGroupRule::UnitStep &u = g.units[0];
        return {u.fire, u.result, u.push, g.cls, g.end};
    }

    std::string run_line() const { return this->group.run_line(); }

    // The current or last run, as SnaxGroupRule's: start s, last cycle E (-1
    // while busy), jobs, job_beats, its count (jobs * job_beats firings), its
    // firings, its cycles per class; runs ended so far
    int64_t start_cycle;
    int64_t end_cycle;
    uint32_t jobs;
    uint32_t job_beats;
    uint32_t count;
    uint32_t firings;
    int64_t classes[SnaxGroupRule::NB_CLASSES];
    int runs;

    SnaxGroupRule group;

private:
    void sync()
    {
        this->start_cycle = this->group.start_cycle;
        this->end_cycle = this->group.end_cycle;
        this->jobs = this->group.jobs;
        this->job_beats = this->group.beats.empty() ? 1 : this->group.beats[0];
        this->count = this->group.count();
        this->firings = this->group.firings();
        for (int c = 0; c < SnaxGroupRule::NB_CLASSES; c++)
        {
            this->classes[c] = this->group.classes[c];
        }
        this->runs = this->group.runs;
    }
};
