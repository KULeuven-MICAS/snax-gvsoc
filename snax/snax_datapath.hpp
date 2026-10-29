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
//   ElementwiseLanes(inTypes, opType, outType, lanes, op)   L 0: per lane
//       a op b at opType, cast to outType (snax_unit_elementwise)
//   TreeAccumulate(inType, outType, lanes, add)   L 1, pins fire, first: on
//       fire acc <- first ? tree(x) : acc + tree(x), the lanes cast to outType
//       first (snax_unit_fold); the output, one word, is acc
//   Mac(inTypes, opType, outType, lanes, accumulate, regOut)   per lane
//       p = cast_out(cast_op(a) * cast_op(b)); with accumulate, L 1, pins fire
//       and first: on fire s <- first ? p : s + p at outType, the output s;
//       plain, a * b + c at outType (c of out's type and lanes): L 0, or with
//       regOut L 1, pin en, the output its register
//   SerialAccumulate(inType, outType, lanes)   span = lanes, L 1 after the
//       last lane, pins read, lane, first: on read acc <- (first and lane = 0)
//       ? cast_out(x_lane) : acc + cast_out(x_lane); the output, one word, is
//       acc
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
    std::vector<SnaxUnitType> in_types;
    SnaxUnitType op_type = {64, true};
    SnaxUnitType out_type = {64, true};
    int lanes = 1;
    int op = UNIT_ADD;
    bool accumulate = true;
    bool reg_out = false;
    int depth = 1;
};


class SnaxDatapath
{
public:
    virtual ~SnaxDatapath() = default;

    // Its output this cycle; registers unchanged
    virtual void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) = 0;
    // The clock edge
    virtual void commit(const SnaxEnables &en) = 0;

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


inline int snax_words(int lanes, SnaxUnitType t)
{
    return lanes * t.width / 64;
}


class SnaxElementwiseLanes : public SnaxDatapath
{
public:
    explicit SnaxElementwiseLanes(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0]), snax_words(p.lanes, p.in_types[1])};
        this->out_words = snax_words(p.lanes, p.out_type);
        this->out_.assign(this->out_words, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &) override
    {
        snax_unit_elementwise(this->p.op, this->p.lanes, this->p.in_types[0],
            this->p.in_types[1], this->p.out_type, in[0], in[1], this->out_.data());
    }

    void commit(const SnaxEnables &) override {}

private:
    SnaxDatapathParams p;
};


class SnaxTreeAccumulate : public SnaxDatapath
{
public:
    explicit SnaxTreeAccumulate(const SnaxDatapathParams &p) : p(p)
    {
        this->in_words = {snax_words(p.lanes, p.in_types[0])};
        this->out_words = 1;
        this->latency = 1;
        this->out_.assign(1, 0);
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        this->out_[0] = this->acc;
        this->next = en.fire ? snax_unit_fold(this->p.op, this->p.lanes, this->p.in_types[0],
            this->p.out_type, in[0], en.first, this->acc) : this->acc;
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
        for (const SnaxUnitType &t : p.in_types)
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
        uint64_t a = snax_unit_cast(snax_unit_lane(in[0], p.in_types[0].width, l), p.in_types[0],
            p.op_type);
        uint64_t b = snax_unit_cast(snax_unit_lane(in[1], p.in_types[1].width, l), p.in_types[1],
            p.op_type);
        return snax_unit_cast(snax_unit_compute(UNIT_MUL, p.op_type, a, b), p.op_type,
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
                v = en.first ? q : snax_unit_compute(UNIT_ADD, p.out_type,
                    snax_unit_lane(this->reg.data(), w, l), q);
            }
            else
            {
                uint64_t c = snax_unit_cast(snax_unit_lane(in[2], p.in_types[2].width, l),
                    p.in_types[2], p.out_type);
                v = snax_unit_compute(UNIT_ADD, p.out_type, q, c);
            }
            snax_unit_set_lane(this->next.data(), w, l, v);
        }
        bool registered = p.accumulate || p.reg_out;
        this->out_ = registered ? this->reg : this->next;
    }

    void commit(const SnaxEnables &en) override
    {
        if ((this->p.accumulate && en.fire) || (!this->p.accumulate && this->p.reg_out && en.en))
        {
            this->reg = this->next;
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
            uint64_t x = snax_unit_cast(snax_unit_lane(in[0], p.in_types[0].width, en.lane),
                p.in_types[0], p.out_type);
            this->next = en.first && en.lane == 0 ? x
                : snax_unit_compute(UNIT_ADD, p.out_type, this->acc, x);
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
    }

    void eval(const std::vector<const uint64_t *> &in, const SnaxEnables &en) override
    {
        this->out_ = this->slots[en.rslot];
        this->in.assign(in[0], in[0] + this->out_words);
    }

    void commit(const SnaxEnables &en) override
    {
        if (en.load)
        {
            this->slots[en.wslot] = this->in;
        }
    }

private:
    SnaxDatapathParams p;
    std::vector<std::vector<uint64_t>> slots;
    std::vector<uint64_t> in;
};


// The registry: catalogue name -> a datapath built from params, or an empty
// pointer and *why set when the params do not fit it
using SnaxDatapathFactory =
    std::function<std::unique_ptr<SnaxDatapath>(const SnaxDatapathParams &, std::string *)>;

// Whether the elements of lanes of t fill whole 64-bit words
inline bool snax_whole_words(int lanes, SnaxUnitType t)
{
    return lanes > 0 && lanes * t.width % 64 == 0;
}

inline const std::map<std::string, SnaxDatapathFactory> &snax_datapaths()
{
    static const std::map<std::string, SnaxDatapathFactory> registry = {
        {"ElementwiseLanes", [](const SnaxDatapathParams &p, std::string *why) {
            SnaxUnitType t;
            if (p.in_types.size() != 2 || !snax_unit_result_type(p.in_types[0], p.in_types[1], &t))
            {
                *why = "two inputs with an integer result type";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxElementwiseLanes(p));
        }},
        {"TreeAccumulate", [](const SnaxDatapathParams &p, std::string *why) {
            if (p.in_types.size() != 1 || p.op != UNIT_ADD)
            {
                *why = "one input, op add";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxTreeAccumulate(p));
        }},
        {"Mac", [](const SnaxDatapathParams &p, std::string *why) {
            size_t n = p.accumulate ? 2 : 3;
            if (p.in_types.size() != n || (p.accumulate && p.reg_out) ||
                (!p.accumulate && (p.in_types[2].width != p.out_type.width ||
                    p.in_types[2].is_signed != p.out_type.is_signed)))
            {
                *why = "a and b (and, plain, c of out's type); regOut only plain";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxMac(p));
        }},
        {"SerialAccumulate", [](const SnaxDatapathParams &p, std::string *why) {
            if (p.in_types.size() != 1)
            {
                *why = "one input";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxSerialAccumulate(p));
        }},
        {"LinkBuffer", [](const SnaxDatapathParams &p, std::string *why) {
            if (p.depth < 1)
            {
                *why = "depth 1 or more";
                return std::unique_ptr<SnaxDatapath>();
            }
            return std::unique_ptr<SnaxDatapath>(new SnaxLinkBuffer(p));
        }},
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
    for (const SnaxUnitType &t : p.in_types)
    {
        if (name != "LinkBuffer" && !snax_whole_words(p.lanes, t))
        {
            *why = "an input's lanes are not whole 64-bit words";
            return nullptr;
        }
    }
    return it->second(p, why);
}
