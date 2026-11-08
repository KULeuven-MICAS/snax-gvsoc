/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The datapaths of snax-forge's catalogue (C§17's datapath catalogue,
// hw/chisel/blocks.json; D129, D147, D149), one plain C++ class each, data and
// enables only: no valid, ready or counter inside, which are the control
// model's (snax_group.hpp's SnaxGroupRule, the `<tag>_<group>_ctrl` of
// snax-forge's Chisel). No GVSoC types, so the component (snax_group.cpp) and
// the standalone tests (tests/snax/datapath/, tests/snax/group/) run the same
// code, as snax_sparse_arb.hpp.
//
// A datapath is evaluated once per cycle and clocked once:
//
//   eval(in, en)   its output this cycle (out()), from its registers and its
//                  inputs this cycle; it changes no register
//   commit(en)     the clock edge: its registers take what eval worked out
//
// Every port carries whole 64-bit channel words, lane l of a b-bit type at
// bits [l * b, (l + 1) * b) (snax_types.hpp), but a fold's one-lane output,
// one word. The enables (SnaxEnables) come from the control model per cycle:
// fire (a beat taken from every input), first (the job's first beat, d = 0),
// read and lane (a SerialAccumulate reading lane `lane` in place), en (a
// plain Mac's output register, regOut), load, wslot and rslot (a LinkBuffer's
// write enable and its ring's write and read slots).
//
//   SimdLanes(inTypes, opType, outType, lanes, op[, k])   L 0: per lane
//       a op b at opType, cast to outType (snax_op_elementwise); with one
//       input (one stream), op(a, k) with the constant k at opType, a's type
//       (snax_op_elementwise_k); at op axpby, k1 * a + k2 * b (+ b without k2)
//       at opType (snax_op_axpby). A slot read from its CSR (k at one stream,
//       k1, k2) takes its value at each start (set_scalar), as the shell
//       sends it
//   TreeAccumulate(inType, outType, lanes, add[, seed])   L 1, pins fire,
//       first: on fire acc <- first ? tree(x) : acc + tree(x), the lanes cast to
//       outType first (snax_op_fold); the output, one word, is acc. Seeded (a
//       second input, the seed: one element of its type in one word, read
//       once per job), the first firing starts from it: acc <- seed + tree(x)
//   Mac(inTypes, opType, outType, lanes, accumulate, regOut)   per lane
//       p = cast_out(cast_op(a) * cast_op(b)); with accumulate, L 1, pins fire
//       and first: on fire s <- first ? p : s + p at outType, the output s;
//       plain, a * b + c at outType (c of out's type and lanes): L 0, or with
//       regOut L 1, pin en, the output its register
//   LaneAccumulate(inType, outType, lanes)   L 1, pins fire, first: per lane
//       x = cast_out(a); on fire s <- first ? x : s + x at outType, the output
//       s (Mac's accumulating form without the product; rowsum 2's W rows on
//       W lanes)
//   SerialAccumulate(inType, outType, lanes[, seed])   span = lanes, L 1
//       after the last lane, pins read, lane, first: on read acc <- (first and
//       lane = 0) ? cast_out(x_lane) : acc + cast_out(x_lane); the output, one
//       word, is acc. Seeded (a second input, as TreeAccumulate's), the job's
//       first firing (its first beat's last lane, pin fire, when the control
//       takes the seed) adds the seed too: the job's sum is seed + its lanes
//   LinkBuffer(depth, lanes, dtype)   D slots of one beat, L 1: the output is
//       slot rslot, and on load slot wslot takes the input; the occupancy and
//       the slots are the control model's
//
// The registry (snax_datapath_new) builds one by its catalogue name from a
// unit's params (SnaxDatapathParams), or says why it cannot.

#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "snax_types.hpp"


// What the control model gives a datapath in one cycle
struct SnaxEnables
{
    bool fire = false;
    bool first = false;
    bool read = false;
    int lane = 0;
    bool en = false;
    bool load = false;
    int wslot = 0;
    int rslot = 0;
};


// A unit's datapath params, as accelerator.json's unit gives them (C§17): the
// inputs' types in port order, the op's and the output's, the lanes, and what
// a datapath takes of the rest
struct SnaxDatapathParams
{
    std::vector<SnaxType> in_types;
    SnaxType op_type = {64, true};
    SnaxType out_type = {64, true};
    int lanes = 1;
    int op = SNAX_OP_ADD;
    bool accumulate = true;
    bool reg_out = false;
    int depth = 1;
    bool has_k = false;     // one stream: SimdLanes' second operand is the constant k
    uint64_t k = 0;         // its bits, two's complement in 64 bits, a value of op_type
    bool k_csr = false;     // ... k from its CSR, set at each start (has_k too)
    bool has_k1 = false;    // axpby's k1: baked (k1) or from its CSR (k1_csr)
    uint64_t k1 = 0;
    bool k1_csr = false;
    bool has_k2 = false;    // axpby's k2, as k1; neither: + b
    uint64_t k2 = 0;
    bool k2_csr = false;
    bool seed = false;      // a fold's seed: its last input, one element in one word (D149)
};


class SnaxDatapath
{
public:
    virtual ~SnaxDatapath() = default;

    // Its output this cycle; registers unchanged
    virtual void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) = 0;
    // The clock edge
    virtual void commit(const SnaxEnables &en) = 0;
    // A slot read from its CSR (k, k1, k2) at a start: its bits; false if the
    // datapath has no such slot
    virtual bool set_scalar(const std::string &, uint64_t) { return false; }

    const std::vector<uint64_t> &out() const { return this->out_; }

    // Words per beat of each input, in port order, and of the output
    std::vector<int> in_words;
    int out_words = 1;
    // Its latency and span (C§17's timing), for the control model's check
    int latency = 0;
    int span = 1;

protected:
    std::vector<uint64_t> out_;
};


inline int snax_words(int lanes, SnaxType t)
{
    return lanes * t.width / 64;
}


class SnaxSimdLanes : public SnaxDatapath
{
public:
    explicit SnaxSimdLanes(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0])};
        if (!p.has_k)
        {
            this->in_words.push_back(snax_words(p.lanes, p.in_types[1]));
        }
        this->out_words = snax_words(p.lanes, p.out_type);
        this->out_.assign(this->out_words, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &) override
    {
        if (this->p.op == SNAX_OP_AXPBY)
        {
            snax_op_axpby(this->p.lanes, this->p.in_types[0], this->p.in_types[1],
                this->p.op_type, this->p.out_type, in[0], in[1], this->p.k1, this->p.has_k2,
                this->p.k2, this->out_.data());
            return;
        }
        if (this->p.has_k)
        {
            snax_op_elementwise_k(this->p.op, this->p.lanes, this->p.in_types[0],
                this->p.op_type, this->p.out_type, in[0], this->p.k, this->out_.data());
            return;
        }
        snax_op_elementwise(this->p.op, this->p.lanes, this->p.in_types[0],
            this->p.in_types[1], this->p.out_type, in[0], in[1], this->out_.data());
    }

    void commit(const SnaxEnables &) override {}

    bool set_scalar(const std::string &slot, uint64_t bits) override
    {
        if (slot == "k" && this->p.k_csr)
        {
            this->p.k = bits;
        }
        else if (slot == "k1" && this->p.k1_csr)
        {
            this->p.k1 = bits;
        }
        else if (slot == "k2" && this->p.k2_csr)
        {
            this->p.k2 = bits;
        }
        else
        {
            return false;
        }
        return true;
    }

private:
    SnaxDatapathParams p;
};


// A seeded fold's seed: lane 0 of its last input, cast to the output's type
inline uint64_t snax_seed(const SnaxDatapathParams &p, const std::vector<const uint64_t *> &in)
{
    const SnaxType &t = p.in_types.back();
    return snax_lane_cast(snax_lane_get(in.back(), t.width, 0), t, p.out_type);
}


class SnaxTreeAccumulate : public SnaxDatapath
{
public:
    explicit SnaxTreeAccumulate(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0])};
        if (p.seed)
        {
            this->in_words.push_back(1);
        }
        this->out_words = 1;
        this->latency = 1;
        this->out_.assign(1, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        const SnaxDatapathParams &p = this->p;
        this->out_[0] = this->acc;
        bool seeded = p.seed && en.first;   // the job's first firing starts from the seed
        uint64_t from = seeded ? snax_seed(p, in) : this->acc;
        this->next = en.fire ? snax_op_fold(p.op, p.lanes, p.in_types[0], p.out_type, in[0],
            en.first && !seeded, from) : this->acc;
    }

    void commit(const SnaxEnables &en) override
    {
        if (en.fire)
        {
            this->acc = this->next;
        }
    }

private:
    SnaxDatapathParams p;
    uint64_t acc = 0;
    uint64_t next = 0;
};


class SnaxMac : public SnaxDatapath
{
public:
    explicit SnaxMac(const SnaxDatapathParams &p) : p(p)
    {
        for (const SnaxType &t : p.in_types)
        {
            this->in_words.push_back(snax_words(p.lanes, t));
        }
        this->out_words = snax_words(p.lanes, p.out_type);
        this->latency = p.accumulate || p.reg_out ? 1 : 0;
        this->out_.assign(this->out_words, 0);
        this->reg.assign(this->out_words, 0);
        this->next.assign(this->out_words, 0);
    }

    // Lane l's product, at opType, cast to outType
    uint64_t product(const std::vector<const uint64_t *> &in, int l) const
    {
        const SnaxDatapathParams &p = this->p;
        uint64_t a = snax_lane_cast(snax_lane_get(in[0], p.in_types[0].width, l), p.in_types[0],
            p.op_type);
        uint64_t b = snax_lane_cast(snax_lane_get(in[1], p.in_types[1].width, l), p.in_types[1],
            p.op_type);
        return snax_lane_cast(snax_op_compute(SNAX_OP_MUL, p.op_type, a, b), p.op_type,
            p.out_type);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        const SnaxDatapathParams &p = this->p;
        int w = p.out_type.width;
        std::fill(this->next.begin(), this->next.end(), 0);
        bool computes = p.accumulate ? en.fire : true;
        for (int l = 0; computes && l < p.lanes; l++)
        {
            uint64_t q = this->product(in, l);
            uint64_t v;
            if (p.accumulate)
            {
                v = en.first ? q : snax_op_compute(SNAX_OP_ADD, p.out_type,
                    snax_lane_get(this->reg.data(), w, l), q);
            }
            else
            {
                uint64_t c = snax_lane_cast(snax_lane_get(in[2], p.in_types[2].width, l),
                    p.in_types[2], p.out_type);
                v = snax_op_compute(SNAX_OP_ADD, p.out_type, q, c);
            }
            snax_lane_set(this->next.data(), w, l, v);
        }
        const std::vector<uint64_t> &out = p.accumulate || p.reg_out ? this->reg : this->next;
        std::copy(out.begin(), out.end(), this->out_.begin());
    }

    void commit(const SnaxEnables &en) override
    {
        if ((this->p.accumulate && en.fire) || (!this->p.accumulate && this->p.reg_out && en.en))
        {
            std::copy(this->next.begin(), this->next.end(), this->reg.begin());
        }
    }

private:
    SnaxDatapathParams p;
    std::vector<uint64_t> reg;      // s with accumulate, the output register with regOut
    std::vector<uint64_t> next;
};


class SnaxSerialAccumulate : public SnaxDatapath
{
public:
    explicit SnaxSerialAccumulate(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0])};
        if (p.seed)
        {
            this->in_words.push_back(1);
        }
        this->out_words = 1;
        this->latency = 1;
        this->span = p.lanes;
        this->out_.assign(1, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        const SnaxDatapathParams &p = this->p;
        this->out_[0] = this->acc;
        this->next = this->acc;
        if (en.read)
        {
            uint64_t x = snax_lane_cast(snax_lane_get(in[0], p.in_types[0].width, en.lane),
                p.in_types[0], p.out_type);
            this->next = en.first && en.lane == 0 ? x
                : snax_op_compute(SNAX_OP_ADD, p.out_type, this->acc, x);
            if (p.seed && en.first && en.fire)  // the job's first beat taken: its seed too
            {
                this->next = snax_op_compute(SNAX_OP_ADD, p.out_type, this->next,
                    snax_seed(p, in));
            }
        }
    }

    void commit(const SnaxEnables &en) override
    {
        if (en.read)
        {
            this->acc = this->next;
        }
    }

private:
    SnaxDatapathParams p;
    uint64_t acc = 0;
    uint64_t next = 0;
};


class SnaxLinkBuffer : public SnaxDatapath
{
public:
    explicit SnaxLinkBuffer(const SnaxDatapathParams &p) : p(p)
    {
        int words = snax_words(p.lanes, p.out_type);
        this->in_words = {words};
        this->out_words = words;
        this->latency = 1;
        this->slots.assign(p.depth, std::vector<uint64_t>(words, 0));
        this->out_.assign(words, 0);
        this->in.assign(words, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        const std::vector<uint64_t> &slot = this->slots[en.rslot];
        std::copy(slot.begin(), slot.end(), this->out_.begin());
        std::copy(in[0], in[0] + this->out_words, this->in.begin());
    }

    void commit(const SnaxEnables &en) override
    {
        if (en.load)
        {
            std::copy(this->in.begin(), this->in.end(), this->slots[en.wslot].begin());
        }
    }

private:
    SnaxDatapathParams p;
    std::vector<std::vector<uint64_t>> slots;
    std::vector<uint64_t> in;
};


class SnaxLaneAccumulate : public SnaxDatapath
{
public:
    explicit SnaxLaneAccumulate(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0])};
        this->out_words = snax_words(p.lanes, p.out_type);
        this->latency = 1;
        this->out_.assign(this->out_words, 0);
        this->s.assign(this->out_words, 0);
        this->next.assign(this->out_words, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        const SnaxDatapathParams &p = this->p;
        int w = p.out_type.width;
        std::copy(this->s.begin(), this->s.end(), this->out_.begin());
        std::fill(this->next.begin(), this->next.end(), 0);  // snax_lane_set ORs into a word
        for (int l = 0; en.fire && l < p.lanes; l++)
        {
            uint64_t x = snax_lane_cast(snax_lane_get(in[0], p.in_types[0].width, l),
                p.in_types[0], p.out_type);
            uint64_t v = en.first ? x : snax_op_compute(SNAX_OP_ADD, p.out_type,
                snax_lane_get(this->s.data(), w, l), x);
            snax_lane_set(this->next.data(), w, l, v);
        }
    }

    void commit(const SnaxEnables &en) override
    {
        if (en.fire)
        {
            std::copy(this->next.begin(), this->next.end(), this->s.begin());
        }
    }

private:
    SnaxDatapathParams p;
    std::vector<uint64_t> s;
    std::vector<uint64_t> next;
};


// The registry: catalogue name -> its facts and a datapath built from params,
// or an empty pointer and *why set when the params do not fit it. Its Python
// side is snax_cfg.py's CATALOGUE: a new datapath is an entry in each.
using SnaxDatapathFactory =
    std::function<std::unique_ptr<SnaxDatapath>(const SnaxDatapathParams &, std::string *)>;

struct SnaxDatapathEntry
{
    bool whole_words;           // each input's lanes fill whole 64-bit words
    SnaxDatapathFactory make;
};

// Whether the elements of lanes of t fill whole 64-bit words
inline bool snax_whole_words(int lanes, SnaxType t)
{
    return lanes > 0 && lanes * t.width % 64 == 0;
}

inline const std::map<std::string, SnaxDatapathEntry> &snax_datapaths()
{
    static const std::map<std::string, SnaxDatapathEntry> registry = {
        {"SimdLanes", {true, [](const SnaxDatapathParams &p, std::string *why) {
            SnaxType t;
            if (p.op == SNAX_OP_AXPBY)
            {
                if (p.in_types.size() != 2 || !snax_op_result_type(p.in_types[0], p.in_types[1], &t) ||
                    t.width != p.op_type.width || t.is_signed != p.op_type.is_signed || !p.has_k1 ||
                    p.has_k)
                {
                    *why = "axpby: two inputs at their result type, k1 baked or from its CSR";
                    return std::unique_ptr<SnaxDatapath>();
                }
            }
            else if (p.has_k1 || p.has_k2)
            {
                *why = "k1 and k2 are axpby's";
                return std::unique_ptr<SnaxDatapath>();
            }
            else if (p.has_k)
            {
                if (p.in_types.size() != 1 || p.op_type.width != p.in_types[0].width ||
                    p.op_type.is_signed != p.in_types[0].is_signed)
                {
                    *why = "one input with k, at its own type";
                    return std::unique_ptr<SnaxDatapath>();
                }
            }
            else if (p.in_types.size() != 2 || !snax_op_result_type(p.in_types[0], p.in_types[1], &t))
            {
                *why = "two inputs with an integer result type, or one with k";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxSimdLanes(p));
        }}},
        {"TreeAccumulate", {true, [](const SnaxDatapathParams &p, std::string *why) {
            if (p.in_types.size() != (p.seed ? 2u : 1u) || p.op != SNAX_OP_ADD)
            {
                *why = "one input (two seeded: a, then the seed), op add";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxTreeAccumulate(p));
        }}},
        {"Mac", {true, [](const SnaxDatapathParams &p, std::string *why) {
            size_t n = p.accumulate ? 2 : 3;
            if (p.in_types.size() != n || (p.accumulate && p.reg_out) ||
                (!p.accumulate && (p.in_types[2].width != p.out_type.width ||
                    p.in_types[2].is_signed != p.out_type.is_signed)))
            {
                *why = "a and b (and, plain, c of out's type); regOut only plain";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxMac(p));
        }}},
        {"LaneAccumulate", {true, [](const SnaxDatapathParams &p, std::string *why) {
            if (p.in_types.size() != 1 || p.op != SNAX_OP_ADD ||
                p.out_type.width < p.in_types[0].width)
            {
                *why = "one input, op add, an output at least as wide";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxLaneAccumulate(p));
        }}},
        {"SerialAccumulate", {true, [](const SnaxDatapathParams &p, std::string *why) {
            if (p.in_types.size() != (p.seed ? 2u : 1u))
            {
                *why = "one input (two seeded: a, then the seed)";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxSerialAccumulate(p));
        }}},
        // A link's buffer holds the beat as it comes, whatever its packing
        {"LinkBuffer", {false, [](const SnaxDatapathParams &p, std::string *why) {
            if (p.depth < 1)
            {
                *why = "depth 1 or more";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxLinkBuffer(p));
        }}},
    };
    return registry;
}

// The datapath name builds from p; empty and *why set when it cannot
inline std::unique_ptr<SnaxDatapath> snax_datapath_new(const std::string &name,
    const SnaxDatapathParams &p, std::string *why)
{
    auto it = snax_datapaths().find(name);
    if (it == snax_datapaths().end())
    {
        *why = "not a datapath of the catalogue";
        return nullptr;
    }
    if (p.seed && name != "TreeAccumulate" && name != "SerialAccumulate")
    {
        *why = "a seed is TreeAccumulate's and SerialAccumulate's (D149)";
        return nullptr;
    }
    for (size_t i = 0; i < p.in_types.size(); i++)
    {
        const SnaxType &t = p.in_types[i];
        bool seed = p.seed && i + 1 == p.in_types.size();  // one element in one word
        if (it->second.whole_words && !seed && !snax_whole_words(p.lanes, t))
        {
            *why = "an input's lanes are not whole 64-bit words";
            return nullptr;
        }
    }
    return it->second.make(p, why);
}
