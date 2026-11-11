/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The per-bank pick of snax_cluster's sparse interconnect, as rules
// (hw/chisel/.../snax/sparse_interconnect/: SparseConfig.scala,
// PriorityRoundRobinArbiter.scala, RoundRobinArbiter.scala). Plain C++, so
// the crossbar (snax_tcdm_xbar.cpp) and the winner check against the RTL
// (tests/snax/sparse_arb/) run the same code. Priority is one bit, as
// snaxgen elaborates it. docs/notes/NOTES.md (The crossbar and the sparse
// interconnect) has the reading and the check against the RTL.

#pragma once

#include <bitset>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>


// The most inputs the crossbar takes (snax-forge D85: l1.max_xbar_inputs), and
// a set of them, one bit each: per bank its requesters, per arbiter its valid
// and high local inputs
constexpr int kMaxInputs = 128;
using SnaxInputMask = std::bitset<kMaxInputs>;


// The first input of mask at or after from, -1 if none
inline int snax_first_input(const SnaxInputMask &mask, int from = 0)
{
    for (int i = from; i < kMaxInputs; i++)
    {
        if (mask[i])
        {
            return i;
        }
    }
    return -1;
}


// One port of the sparse configuration: width inputs, each reaching every
// granularity-th bank
struct SnaxSparsePort
{
    int width;
    int granularity;
};


// The sparse configuration: ports in input order (SparseConfig)
class SnaxSparseConfig
{
public:
    SnaxSparseConfig() {}

    SnaxSparseConfig(std::vector<SnaxSparsePort> ports, int nb_banks)
        : ports(ports), nb_banks(nb_banks)
    {
        for (const SnaxSparsePort &port : ports)
        {
            if (port.width <= 0 || port.granularity <= 0 || port.width % port.granularity != 0
                || nb_banks % port.granularity != 0)
            {
                throw std::invalid_argument("sparse port [" + std::to_string(port.width) + ", "
                    + std::to_string(port.granularity) + "] does not divide into "
                    + std::to_string(nb_banks) + " banks");
            }
        }
        if (this->inputs_per_bank() > kMaxInputs)
        {
            throw std::invalid_argument("more than " + std::to_string(kMaxInputs)
                + " inputs per bank");
        }
    }

    int nb_inputs() const
    {
        int count = 0;
        for (const SnaxSparsePort &port : this->ports)
        {
            count += port.width;
        }
        return count;
    }

    int inputs_per_bank() const
    {
        int count = 0;
        for (const SnaxSparsePort &port : this->ports)
        {
            count += port.width / port.granularity;
        }
        return count;
    }

    // The global inputs bank sees, in its local order (get_global_idx_list)
    std::vector<int> bank_inputs(int bank) const
    {
        std::vector<int> inputs;
        int first = 0;
        for (const SnaxSparsePort &port : this->ports)
        {
            for (int i = 0; i < port.width / port.granularity; i++)
            {
                inputs.push_back(first + i * port.granularity + bank % port.granularity);
            }
            first += port.width;
        }
        return inputs;
    }

    // Whether global input may reach bank (the RTL asserts it)
    bool reaches(int input, int bank) const
    {
        int first = 0;
        for (const SnaxSparsePort &port : this->ports)
        {
            if (input < first + port.width)
            {
                return bank % port.granularity == (input - first) % port.granularity;
            }
            first += port.width;
        }
        return false;
    }

    std::vector<SnaxSparsePort> ports;
    int nb_banks = 0;
};


// One bank's arbiter. pick() is called only in cycles where the bank has a
// request; a cycle skipped is a cycle the bank had none.
class SnaxSparseArb
{
public:
    explicit SnaxSparseArb(int nb_inputs = 1) : nb_inputs(nb_inputs) { this->reset(); }

    void reset()
    {
        this->previous = this->nb_inputs - 1;
        this->lock = false;
        this->last_cycle = -2;
    }

    // The winner among the local inputs in valid (one bit each, nonzero),
    // high the ones with priority 1
    int pick(int64_t cycle, const SnaxInputMask &valid, const SnaxInputMask &high)
    {
        // With no request, the RTL's selection is the last input and nothing
        // was refused: the pointer restarts.
        if (this->last_cycle != cycle - 1)
        {
            this->previous = this->nb_inputs - 1;
            this->lock = false;
        }

        // Only the highest priority among the valid requests competes
        SnaxInputMask mask = (valid & high).any() ? valid & high : valid;

        int winner;
        if (this->lock && mask[this->previous])
        {
            winner = this->previous;
        }
        else
        {
            // Round robin: the first after the last pick, else the first
            winner = snax_first_input(mask, this->previous + 1);
            if (winner < 0)
            {
                winner = snax_first_input(mask);
            }
        }

        this->previous = winner;
        this->lock = false;
        this->last_cycle = cycle;
        return winner;
    }

    // The winner of this cycle's pick was refused by the bank: it keeps its
    // turn next cycle if it still competes
    void refused() { this->lock = true; }

private:
    int nb_inputs;
    int previous;           // the last pick
    bool lock;              // the last pick was refused
    int64_t last_cycle;     // the cycle of the last pick
};
