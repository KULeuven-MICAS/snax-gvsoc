// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The plain winner check (README.md): the same random
// requests and grants through common_cells' rr_arb_tree (plain_arb_top.sv)
// and through snax_plain_arb.hpp, the model's own pick, compared per cycle.
//
//   tb CYCLES SEED
//
// Each input holds its request until it is granted (req_i and gnt_o in one
// cycle), as the interconnect's masters do and LockIn requires; gnt_i is
// random, a refusal by the bank. Per cycle: the tree's req_o and idx_o
// against the model's pick, and per requesting input its gnt_o against the
// model (picked and granted). Exit 1 on any difference.

#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "Vplain_arb_top.h"
#include "verilated.h"

#include "snax_plain_arb.hpp"

#ifndef NUM_IN
#error "Build with -DNUM_IN=<the tree's NumIn>"
#endif

// Cycles per phase; each phase draws its own inputs, request and refusal
// rates
#define PHASE 500

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        fprintf(stderr, "usage: %s CYCLES SEED\n", argv[0]);
        return 2;
    }
    long cycles = atol(argv[1]);
    std::mt19937_64 rng(atoll(argv[2]));
    std::uniform_real_distribution<double> uniform(0.0, 1.0);
    auto chance = [&](double p) { return uniform(rng) < p; };

    VerilatedContext ctx;
    Vplain_arb_top *t = new Vplain_arb_top(&ctx);
    t->req_i = 0;
    t->gnt_i = 1;
    t->rst_ni = 0;
    for (int c = 0; c < 4; c++)
    {
        t->clk_i = 0;
        t->eval();
        t->clk_i = 1;
        t->eval();
    }
    t->rst_ni = 1;

    SnaxPlainArb arb(NUM_IN);
    uint64_t all = (1ULL << NUM_IN) - 1;
    uint64_t req = 0, active = all, last_req = 0;
    double p_new = 0, p_refuse = 0;
    bool last_refused = false;

    // What the stimulus covered, counted apart from the model
    long picks = 0, contested = 0, refusals = 0, after_refusal = 0, newcomer_locked = 0;
    long diffs = 0;

    for (long cycle = 0; cycle < cycles; cycle++)
    {
        if (cycle % PHASE == 0)
        {
            const double news[] = {0.05, 0.2, 0.5, 0.9};
            const double refuse[] = {0.0, 0.1, 0.4, 0.8};
            p_new = news[rng() % 4];
            p_refuse = refuse[rng() % 4];
            // All inputs, or a random few
            active = rng() % 2 ? all : (rng() & all);
        }

        // An input not asking may start; one asking keeps its request
        for (int i = 0; i < NUM_IN; i++)
        {
            if (!((req >> i) & 1) && ((active >> i) & 1) && chance(p_new))
            {
                req |= 1ULL << i;
            }
        }
        bool gnt = !chance(p_refuse);
        t->req_i = req;
        t->gnt_i = gnt;
        t->clk_i = 0;
        t->eval();

        int winner = -1;
        if (req != 0)
        {
            picks++;
            contested += __builtin_popcountll(req) > 1;
            after_refusal += last_refused;
            newcomer_locked += last_refused && (req & ~last_req) != 0;
            winner = arb.pick(cycle, req);
            if (!t->req_o || (int)t->idx_o != winner)
            {
                if (diffs++ < 10)
                {
                    printf("cycle %ld req 0x%lx: model %d, tree %s%d\n", cycle, req, winner,
                        t->req_o ? "" : "no request, idx ", t->idx_o);
                }
            }
        }
        else if (t->req_o)
        {
            if (diffs++ < 10)
            {
                printf("cycle %ld: no request, the tree has one (idx %d)\n", cycle, t->idx_o);
            }
        }

        uint64_t fired = 0;
        for (int i = 0; i < NUM_IN; i++)
        {
            if (!((req >> i) & 1))
            {
                continue;
            }
            bool tree = (t->gnt_o >> i) & 1;
            bool model = i == winner && gnt;
            if (tree != model && diffs++ < 10)
            {
                printf("cycle %ld input %d: gnt_o %d, model %d\n", cycle, i, tree, model);
            }
            fired |= (uint64_t)tree << i;
        }
        if (winner >= 0)
        {
            if (gnt)
            {
                arb.granted();
            }
            else
            {
                arb.refused();
                refusals++;
            }
        }
        last_refused = winner >= 0 && !gnt;
        last_req = req;
        req &= ~fired;

        t->clk_i = 1;
        t->eval();
    }

    printf("%ld cycles, %d inputs: %ld selections (%ld contested, %ld after a refusal, %ld of "
        "them with a new request), %ld refusals; differences %ld\n",
        cycles, NUM_IN, picks, contested, after_refusal, newcomer_locked, refusals, diffs);
    t->final();
    delete t;
    return diffs ? 1 : 0;
}
