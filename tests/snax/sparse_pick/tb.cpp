/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The crossbar's pick at up to 128 inputs (README.md), g++ only: the pick of
// snax/snax_sparse_arb.hpp on SnaxInputMask against
//   - OldArb, the pick as it was on 64-bit masks (snax-gvsoc 85552fc4), for
//     1 to 64 inputs: the same winners;
//   - RefArb, the rule written as a plain loop over the inputs, for 1 to 128.
// Random stimulus per arbiter: valid and priority bits, idle cycles (no pick),
// refusals. Then the sparse configuration of 128 inputs (bank_inputs, reaches)
// and its refusal past 128. Exit 1 on a difference.

#include <cstdio>
#include <random>
#include "snax_sparse_arb.hpp"


// SnaxSparseArb::pick on uint64_t masks, as in snax-gvsoc 85552fc4
class OldArb
{
public:
    explicit OldArb(int nb_inputs) : nb_inputs(nb_inputs) { this->reset(); }

    void reset()
    {
        this->previous = this->nb_inputs - 1;
        this->lock = false;
        this->last_cycle = -2;
    }

    int pick(int64_t cycle, uint64_t valid, uint64_t high)
    {
        if (this->last_cycle != cycle - 1)
        {
            this->previous = this->nb_inputs - 1;
            this->lock = false;
        }
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

    void refused() { this->lock = true; }

private:
    int nb_inputs;
    int previous;
    bool lock;
    int64_t last_cycle;
};


// The rule as a loop: among the valid inputs (the high ones if any), the one
// refused last cycle if it competes, else the first after the last pick,
// counting round from it; the pointer restarts after a cycle with no pick
class RefArb
{
public:
    explicit RefArb(int nb_inputs) : nb_inputs(nb_inputs), previous(nb_inputs - 1) {}

    int pick(int64_t cycle, const std::vector<bool> &valid, const std::vector<bool> &high)
    {
        if (this->last_cycle != cycle - 1)
        {
            this->previous = this->nb_inputs - 1;
            this->lock = false;
        }
        bool any_high = false;
        for (int i = 0; i < this->nb_inputs; i++)
        {
            any_high |= valid[i] && high[i];
        }
        auto competes = [&](int i) { return valid[i] && (!any_high || high[i]); };
        int winner = -1;
        if (this->lock && competes(this->previous))
        {
            winner = this->previous;
        }
        for (int k = 1; winner < 0 && k <= this->nb_inputs; k++)
        {
            int i = (this->previous + k) % this->nb_inputs;
            if (competes(i))
            {
                winner = i;
            }
        }
        this->previous = winner;
        this->lock = false;
        this->last_cycle = cycle;
        return winner;
    }

    void refused() { this->lock = true; }

private:
    int nb_inputs;
    int previous;
    bool lock = false;
    int64_t last_cycle = -2;
};


static int failures = 0;

static void fail(const char *what, int n, int64_t cycle, int got, int want)
{
    if (failures++ < 10)
    {
        printf("%s, %d inputs, cycle %ld: pick %d, expected %d\n", what, n, (long)cycle, got,
            want);
    }
}


// One arbiter of n inputs over cycles random cycles, against OldArb when n <= 64
static long run(std::mt19937_64 &rng, int n, int cycles)
{
    std::uniform_real_distribution<double> u(0, 1);
    double p_valid = 0.05 + 0.9 * u(rng), p_high = 0.5 * u(rng);
    double p_idle = 0.2 * u(rng), p_refuse = 0.3 * u(rng);

    SnaxSparseArb arb(n);
    RefArb ref(n);
    OldArb old(n);
    long picks = 0;
    for (int64_t cycle = 0; cycle < cycles; cycle++)
    {
        if (u(rng) < p_idle)
        {
            continue;
        }
        SnaxInputMask valid, high;
        std::vector<bool> v(n), h(n);
        uint64_t v64 = 0, h64 = 0;
        for (int i = 0; i < n; i++)
        {
            v[i] = u(rng) < p_valid;
            h[i] = v[i] && u(rng) < p_high;
            valid.set(i, v[i]);
            high.set(i, h[i]);
            if (i < 64)
            {
                v64 |= (uint64_t)v[i] << i;
                h64 |= (uint64_t)h[i] << i;
            }
        }
        if (valid.none())
        {
            continue;
        }
        int got = arb.pick(cycle, valid, high);
        int want = ref.pick(cycle, v, h);
        if (got != want)
        {
            fail("reference", n, cycle, got, want);
        }
        if (n <= 64)
        {
            int was = old.pick(cycle, v64, h64);
            if (got != was)
            {
                fail("64-bit pick", n, cycle, got, was);
            }
        }
        if (u(rng) < p_refuse)
        {
            arb.refused();
            ref.refused();
            old.refused();
        }
        picks++;
    }
    return picks;
}


int main()
{
    std::mt19937_64 rng(20261111);
    long picks = 0;
    for (int n = 1; n <= kMaxInputs; n++)
    {
        for (int phase = 0; phase < 4; phase++)
        {
            picks += run(rng, n, 2000);
        }
    }
    printf("picks: %ld over 1 to %d inputs (1 to 64 also against the 64-bit pick)\n", picks,
        kMaxInputs);

    // The sparse configuration at 128 inputs: 96 SNAX ports of granularity 1, 32 of 32 (one
    // per bank), as snax-forge writes them; then one input too many
    SnaxSparseConfig cfg({{96, 1}, {32, 32}}, 32);
    if (cfg.nb_inputs() != 128 || cfg.inputs_per_bank() != 97)
    {
        printf("config: %d inputs, %d per bank, expected 128, 97\n", cfg.nb_inputs(),
            cfg.inputs_per_bank());
        failures++;
    }
    for (int bank = 0; bank < 32; bank++)
    {
        std::vector<int> inputs = cfg.bank_inputs(bank);
        if ((int)inputs.size() != 97 || inputs[96] != 96 + bank)
        {
            printf("config: bank %d's inputs are not 0-95 and %d\n", bank, 96 + bank);
            failures++;
        }
        for (int input : inputs)
        {
            if (!cfg.reaches(input, bank))
            {
                printf("config: input %d does not reach its bank %d\n", input, bank);
                failures++;
            }
        }
    }
    try
    {
        SnaxSparseConfig({{129, 1}}, 32);
        printf("config: 129 inputs per bank taken\n");
        failures++;
    }
    catch (const std::invalid_argument &)
    {
    }

    if (failures)
    {
        printf("%d differences\n", failures);
        return 1;
    }
    printf("OK\n");
    return 0;
}
