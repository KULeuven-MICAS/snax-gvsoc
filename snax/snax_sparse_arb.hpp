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
// snaxgen elaborates it. docs/plans/SG7.md has the reading.

#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>


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
        if (this->inputs_per_bank() > 64)
        {
            throw std::invalid_argument("more than 64 inputs per bank");
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
    int pick(int64_t cycle, uint64_t valid, uint64_t high)
    {
        // With no request, the RTL's selection is the last input and nothing
        // was refused: the pointer restarts.
        if (this->last_cycle != cycle - 1)
        {
            this->previous = this->nb_inputs - 1;
            this->lock = false;
        }

        // Only the highest priority among the valid requests competes
        uint64_t mask = (valid & high) != 0 ? valid & high : valid;

        int winner;
        if (this->lock && ((mask >> this->previous) & 1))
        {
            winner = this->previous;
        }
        else
        {
            uint64_t above = mask & ~((2ULL << this->previous) - 1);
            winner = __builtin_ctzll(above != 0 ? above : mask);
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
