/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxUnit's cycle rule and op table: when a Chisel
// block's datapath takes a start, fires and pushes, how its busy cycles are
// classed, and what a lane and a beat compute. Plain C++, so the component
// (snax_unit.cpp) and the standalone test (tests/snax/unit/) run the same
// code, as snax_sparse_arb.hpp.
//
// The arithmetic is NumPy's on integer types (SnaxUnitType: 8 to 64 bits,
// signed or not), each port with its own (PACK0). A port of W lanes of b bits
// takes W * b / 64 channel words, lane l at bits [l * b, (l + 1) * b) of them
// side by side (the wire slice). An elementwise op runs per lane at T, the
// result type of its two inputs' types (snax_unit_result_type; none for a
// signed type with uint64), each operand extended to T by its own
// signedness; the result wraps at T and is cast to the output's type (its
// low bits, or extended by T's signedness). A fold casts each lane from the
// input's type to the output's, and runs its tree and acc at the output's
// type; its output beat is one word. min and max compare by the signedness
// of the type they run at.
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
// pipelined, as a BRM's timing (L, II; D103) without its drain: a
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


// An element's type: width 8, 16, 32 or 64 bits, and its signedness. A value
// of a type is held in the low width bits of a uint64_t, zeros above.
struct SnaxUnitType
{
    int width;
    bool is_signed;
};

// NumPy's name of a type: int32, uint8, ...
inline std::string snax_unit_type_name(SnaxUnitType t)
{
    return (t.is_signed ? "int" : "uint") + std::to_string(t.width);
}

inline uint64_t snax_unit_mask(int width)
{
    return width >= 64 ? ~(uint64_t)0 : ((uint64_t)1 << width) - 1;
}


// NumPy's result type of two integer types (np.result_type): the wider of
// two of the same signedness; of a signed and an unsigned one, the signed one
// when it is wider, else signed at twice the unsigned width. False when that
// is past 64 bits (a signed type with uint64: NumPy gives float64), and *t
// is then int64.
inline bool snax_unit_result_type(SnaxUnitType a, SnaxUnitType b, SnaxUnitType *t)
{
    if (a.is_signed == b.is_signed)
    {
        *t = {a.width > b.width ? a.width : b.width, a.is_signed};
        return true;
    }
    SnaxUnitType s = a.is_signed ? a : b;
    SnaxUnitType u = a.is_signed ? b : a;
    if (s.width > u.width)
    {
        *t = s;
        return true;
    }
    *t = {2 * u.width > 64 ? 64 : 2 * u.width, true};
    return 2 * u.width <= 64;
}


// A value of type s as type t: sign- or zero-extended by s's signedness when
// t is wider, its low t.width bits when t is narrower (NumPy's astype)
inline uint64_t snax_unit_cast(uint64_t v, SnaxUnitType s, SnaxUnitType t)
{
    v &= snax_unit_mask(s.width);
    if (s.is_signed && s.width < 64 && (v >> (s.width - 1)) & 1)
    {
        v |= ~snax_unit_mask(s.width);
    }
    return v & snax_unit_mask(t.width);
}


// One lane of ElementwiseAlu: a op b at type t, wrapping; min and max
// compare by t's signedness. The operands are cut to t's width first.
inline uint64_t snax_unit_compute(int op, SnaxUnitType t, uint64_t a, uint64_t b)
{
    uint64_t mask = snax_unit_mask(t.width);
    a &= mask;
    b &= mask;
    bool a_less = a < b;
    if (t.is_signed)
    {
        // Sign-extend to 64 bits, then compare
        int shift = 64 - t.width;
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
// beat, already of type t, reduced to one by op at t, halves first, so for n
// a power of two the pairs of Chisel's reduceTree. One lane gives that lane.
inline uint64_t snax_unit_tree(int op, SnaxUnitType t, const uint64_t *lanes, int n)
{
    if (n == 1)
    {
        return lanes[0] & snax_unit_mask(t.width);
    }
    int half = n / 2;
    return snax_unit_compute(op, t, snax_unit_tree(op, t, lanes, half),
        snax_unit_tree(op, t, lanes + half, n - half));
}


// Lane l of a beat of width-bit elements: bits [l * width, (l + 1) * width)
// of its 64-bit channel words side by side, word 0 lowest (the wire slice).
// A width of 8 to 64 divides 64, so a lane never straddles two words.
inline uint64_t snax_unit_lane(const uint64_t *words, int width, int lane)
{
    return (words[lane * width / 64] >> (lane * width % 64)) & snax_unit_mask(width);
}

inline void snax_unit_set_lane(uint64_t *words, int width, int lane, uint64_t v)
{
    words[lane * width / 64] |= (v & snax_unit_mask(width)) << (lane * width % 64);
}


// An elementwise beat, as NumPy's out = (a op b).astype(out_t): per lane, a
// and b each at its own port's type, both extended to T, their result type
// (snax_unit_result_type, which must give one), the op at T, and the result
// cast to out_t. The words: lanes * width / 64 per port, out's cleared here.
inline void snax_unit_elementwise(int op, int lanes, SnaxUnitType a_t, SnaxUnitType b_t,
    SnaxUnitType out_t, const uint64_t *a, const uint64_t *b, uint64_t *out)
{
    SnaxUnitType t;
    snax_unit_result_type(a_t, b_t, &t);
    for (int w = 0; w < lanes * out_t.width / 64; w++)
    {
        out[w] = 0;
    }
    for (int lane = 0; lane < lanes; lane++)
    {
        uint64_t x = snax_unit_cast(snax_unit_lane(a, a_t.width, lane), a_t, t);
        uint64_t y = snax_unit_cast(snax_unit_lane(b, b_t.width, lane), b_t, t);
        snax_unit_set_lane(out, out_t.width, lane,
            snax_unit_cast(snax_unit_compute(op, t, x, y), t, out_t));
    }
}


// A fold's firing: the beat's lanes, each cast from in_t to out_t, through
// the tree at out_t; the first firing of an output starts its value with
// that, the others fold it in, op(acc, x) at out_t. Returns the output's
// value so far: its one word, the element in the low out_t.width bits.
inline uint64_t snax_unit_fold(int op, int lanes, SnaxUnitType in_t, SnaxUnitType out_t,
    const uint64_t *in, bool first, uint64_t acc)
{
    std::vector<uint64_t> x(lanes);
    for (int lane = 0; lane < lanes; lane++)
    {
        x[lane] = snax_unit_cast(snax_unit_lane(in, in_t.width, lane), in_t, out_t);
    }
    uint64_t sum = snax_unit_tree(op, out_t, x.data(), lanes);
    return first ? sum : snax_unit_compute(op, out_t, acc, sum);
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
