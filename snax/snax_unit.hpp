/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxUnit's cycle rule and op table: when a Chisel
// block's datapath takes a start, fires and pushes, how its busy cycles are
// classed, and what a lane computes. Plain C++, so the component
// (snax_unit.cpp) and the standalone test (tests/snax/unit/) run the same
// code, as snax_sparse_arb.hpp.
//
// A run: a start offered in cycle s is taken only when the unit is idle in s
// and its count and rate are not 0 (a count or rate of 0 is ignored: busy
// stays 0); a start while busy, or a second one in s, is refused. A run of
// count firings gives a result on every rate-th firing only (count / rate
// results; rate 1, every firing); the component refuses a count that is not
// a multiple of the rate before it starts. The unit is busy from s + 1
// to the run's last cycle E. step() is called once per busy cycle, in order,
// with whether every input has a beat and whether the output has room (the
// component probes all ports first); it says whether the unit fires (takes a
// beat from every input) and pushes (gives a beat to the output) then.
//
// lockstep, as snax-forge's ElementwiseTiledSpatial: it fires when every
// input has a beat and the output has room, and pushes the result in the
// same cycle (latency 0, II 1, rate 1); E is the firing that reaches count.
//
// pipelined, as snax-forge's snax_model/accel.py without its drain: a
// join on the inputs, an L-stage pipeline that stalls as a whole when its
// head cannot be pushed, at most one firing per II. A firing that gives a
// result (every rate-th) puts it into the pipeline; the others put nothing.
// A result from a firing in t is pushed in t + L when nothing stalls. II
// counts cycles from the last firing; a stall does not restart it, and it
// carries over to the next run. With L = 0 the result is pushed in its
// firing cycle, and a firing that gives a result with no room on the output
// is a stall: lockstep's rule. E is the push of the last result. A firing
// enters slot 0 in the cycle the head is pushed, so with L = 1 and II 1 the
// next input is taken in the cycle a result leaves: no drain cycle (snax-forge
// D133, the Chisel Accumulator).
//
// Each busy cycle is one class, in D59's order: stall_out (the head, or for
// L = 0 a firing that gives a result, has no room) > busy (fired, or in the
// II gap after a firing) > stall_in (II allows, an input has no beat) > flush
// (pipelined only: results in flight after the last firing's II gap,
// accel.py's idle).
// So busy + stall_in + stall_out + flush is the run's busy cycles, E - s.

#pragma once

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>


// ElementwiseOp's encodings (snax-forge hw/chisel/.../elementwise/ElementwiseOp.scala)
enum SnaxUnitOp { UNIT_ADD, UNIT_SUB, UNIT_MUL, UNIT_AND, UNIT_OR, UNIT_XOR, UNIT_MIN, UNIT_MAX,
    UNIT_NB_OPS };

static const char *const snax_unit_op_names[UNIT_NB_OPS] =
    {"add", "sub", "mul", "and", "or", "xor", "min", "max"};


// One lane of ElementwiseAlu: a op b on width-bit integers (1 to 64),
// wrapping; min and max compare as two's complement when is_signed. The
// result is width bits, zero-extended.
inline uint64_t snax_unit_compute(int op, bool is_signed, int width, uint64_t a, uint64_t b)
{
    uint64_t mask = width >= 64 ? ~(uint64_t)0 : ((uint64_t)1 << width) - 1;
    a &= mask;
    b &= mask;
    bool a_less = a < b;
    if (is_signed)
    {
        // Sign-extend to 64 bits, then compare
        int shift = 64 - width;
        a_less = ((int64_t)(a << shift) >> shift) < ((int64_t)(b << shift) >> shift);
    }
    uint64_t r;
    switch (op)
    {
        case UNIT_ADD: r = a + b; break;
        case UNIT_SUB: r = a - b; break;
        case UNIT_MUL: r = a * b; break;
        case UNIT_AND: r = a & b; break;
        case UNIT_OR:  r = a | b; break;
        case UNIT_XOR: r = a ^ b; break;
        case UNIT_MIN: r = a_less ? a : b; break;
        default:       r = a_less ? b : a; break;  // UNIT_MAX
    }
    return r & mask;
}


// A fold's tree (snax-forge's Accumulator with lanes): the n lanes of a
// beat reduced to one by op on width-bit integers, halves first, so for n a
// power of two the pairs of Chisel's reduceTree. One lane gives that lane.
inline uint64_t snax_unit_tree(int op, bool is_signed, int width, const uint64_t *lanes, int n)
{
    if (n == 1)
    {
        return lanes[0] & (width >= 64 ? ~(uint64_t)0 : ((uint64_t)1 << width) - 1);
    }
    int half = n / 2;
    return snax_unit_compute(op, is_signed, width,
        snax_unit_tree(op, is_signed, width, lanes, half),
        snax_unit_tree(op, is_signed, width, lanes + half, n - half));
}


// SnaxUnitRule's classes by name, as its run line and the class lines give them
static const char *const snax_unit_class_names[] = {"busy", "stall_in", "stall_out", "flush"};


class SnaxUnitRule
{
public:
    enum Wait { LOCKSTEP, PIPELINED };
    enum Class { BUSY, STALL_IN, STALL_OUT, FLUSH, NB_CLASSES };
    enum Start { TAKEN, IGNORED, REFUSED };

    // What one busy cycle does
    struct Step
    {
        bool fire;      // a beat taken from every input
        bool result;    // the firing gives a result (every rate-th firing)
        bool push;      // a beat given to the output
        Class cls;
        bool end;       // the run's last cycle: idle from the next one
    };

    // latency and ii are used by pipelined only (lockstep: 0 and 1)
    void configure(Wait wait, int latency, int ii)
    {
        this->wait = wait;
        this->latency = wait == LOCKSTEP ? 0 : latency;
        this->ii = wait == LOCKSTEP ? 1 : ii;
        this->reset();
    }

    void reset()
    {
        this->started = false;
        this->start_cycle = 0;
        this->end_cycle = -1;
        this->count = 0;
        this->rate = 1;
        this->firings = 0;
        this->has_fired = false;
        this->last_fire = 0;
        this->slots.assign(this->latency, false);
        this->runs = 0;
        for (int c = 0; c < NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
    }

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

    // A start of count firings, a result every rate firings, offered in cycle
    Start start(int64_t cycle, uint32_t count, uint32_t rate = 1)
    {
        if (!this->idle(cycle))
        {
            return REFUSED;
        }
        if (count == 0 || rate == 0)
        {
            return IGNORED;
        }
        this->started = true;
        this->start_cycle = cycle;
        this->end_cycle = -1;
        this->count = count;
        this->rate = rate;
        this->firings = 0;
        for (int c = 0; c < NB_CLASSES; c++)
        {
            this->classes[c] = 0;
        }
        return TAKEN;
    }

    // One busy cycle: inputs, every input has a beat; room, the output has room
    Step step(int64_t cycle, bool inputs, bool room)
    {
        Step s = {false, false, false, FLUSH, false};
        if (this->wait == LOCKSTEP)
        {
            s.fire = s.result = s.push = inputs && room;
            s.cls = s.fire ? BUSY : inputs ? STALL_OUT : STALL_IN;
        }
        else
        {
            bool ii_ok = !this->has_fired || cycle >= this->last_fire + this->ii;
            bool can_fire = this->firings < this->count && ii_ok && inputs;
            bool gives = can_fire && (this->firings + 1) % this->rate == 0;
            bool head = this->latency > 0 && this->slots[this->latency - 1];
            bool frozen = this->latency > 0 ? head && !room : gives && !room;
            if (frozen)
            {
                s.cls = STALL_OUT;
            }
            else
            {
                s.fire = can_fire;
                s.result = gives;
                s.push = this->latency > 0 ? head : gives;
                for (int i = this->latency - 1; i > 0; i--)
                {
                    this->slots[i] = this->slots[i - 1];
                }
                if (this->latency > 0)
                {
                    this->slots[0] = s.result;
                }
                bool in_gap = this->has_fired && cycle < this->last_fire + this->ii;
                bool waits_input = this->firings < this->count && ii_ok && !inputs;
                s.cls = s.fire || in_gap ? BUSY : waits_input ? STALL_IN : FLUSH;
            }
            if (s.fire)
            {
                this->has_fired = true;
                this->last_fire = cycle;
            }
        }

        if (s.fire)
        {
            this->firings++;
        }
        this->classes[s.cls]++;
        if (this->firings == this->count && !this->in_flight())
        {
            s.end = true;
            this->end_cycle = cycle;
            this->runs++;
        }
        return s;
    }

    // The summary line of the run that ended, run index from 0
    // (docs/EVENTS.md): its classes add up to its busy cycles
    std::string run_line() const
    {
        char line[160];
        snprintf(line, sizeof(line),
            "run index=%d firings=%u busy=%ld stall_in=%ld stall_out=%ld flush=%ld",
            this->runs - 1, this->firings, (long)this->classes[BUSY],
            (long)this->classes[STALL_IN], (long)this->classes[STALL_OUT],
            (long)this->classes[FLUSH]);
        return line;
    }

    // The current or last run: its start s, its last cycle E (-1 while busy),
    // its count, its rate, its firings and its cycles per class; runs ended
    // so far
    int64_t start_cycle;
    int64_t end_cycle;
    uint32_t count;
    uint32_t rate;
    uint32_t firings;
    int64_t classes[NB_CLASSES];
    int runs;

private:
    bool in_flight() const
    {
        for (bool slot : this->slots)
        {
            if (slot)
            {
                return true;
            }
        }
        return false;
    }

    Wait wait;
    int latency;
    int ii;
    bool started;
    bool has_fired;
    int64_t last_fire;
    std::vector<bool> slots;    // the pipeline, slot latency - 1 the head
};
