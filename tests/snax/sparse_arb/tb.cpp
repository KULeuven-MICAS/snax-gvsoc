// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The sparse winner check (README.md): the same random requests
// through an elaborated SparseInterconnect.sv and through snax_sparse_arb.hpp,
// the model's own pick, compared per bank and cycle.
//
//   tb MODULE_CONFIG MODEL_CONFIG CYCLES SEED
//
// MODULE_CONFIG is the sparse_config the module was elaborated with,
// MODEL_CONFIG the model's: the same, or its first ports only, the module's
// other inputs then held idle. Each input's bank-local address is its own
// index, so the bank's request address names the selection, also in a cycle
// the bank refuses. Only accesses the granularity allows. Per cycle and
// bank: the module's request valid and address against the model's pick;
// per input: its ready against the model (picked and not refused). Exit 1
// on any difference.

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

#include "VSparseInterconnect.h"
#include "verilated.h"

#include "ports.h"
#include "snax_sparse_arb.hpp"

// Cycles per phase; each phase draws its own load, bank spread, priority
// and refusal rates
#define PHASE 500
// Byte offset bits and bank bits below the bank-local word address
#define WORD_SHIFT 8

static SnaxSparseConfig parse(const std::string &text, int nb_banks)
{
    std::vector<int> numbers;
    for (size_t i = 0; i < text.size();)
    {
        if (isdigit(text[i]))
        {
            size_t end;
            numbers.push_back(std::stoi(text.substr(i), &end));
            i += end;
        }
        else
        {
            i++;
        }
    }
    std::vector<SnaxSparsePort> ports;
    for (size_t i = 0; i + 1 < numbers.size(); i += 2)
    {
        ports.push_back({numbers[i], numbers[i + 1]});
    }
    return SnaxSparseConfig(ports, nb_banks);
}

// The granularity of global input i in cfg, and its index within its port
static void port_of(const SnaxSparseConfig &cfg, int input, int &granularity, int &index)
{
    int first = 0;
    for (const SnaxSparsePort &port : cfg.ports)
    {
        if (input < first + port.width)
        {
            granularity = port.granularity;
            index = input - first;
            return;
        }
        first += port.width;
    }
}

int main(int argc, char **argv)
{
    if (argc != 5)
    {
        fprintf(stderr, "usage: %s MODULE_CONFIG MODEL_CONFIG CYCLES SEED\n", argv[0]);
        return 2;
    }
    SnaxSparseConfig module_cfg = parse(argv[1], NUM_OUT);
    SnaxSparseConfig model_cfg = parse(argv[2], NUM_OUT);
    long cycles = atol(argv[3]);
    std::mt19937_64 rng(atoll(argv[4]));

    if (module_cfg.nb_inputs() != NUM_INP)
    {
        fprintf(stderr, "module config has %d inputs, the module %d\n", module_cfg.nb_inputs(),
            NUM_INP);
        return 2;
    }
    for (size_t p = 0; p < model_cfg.ports.size(); p++)
    {
        if (p >= module_cfg.ports.size() || model_cfg.ports[p].width != module_cfg.ports[p].width
            || model_cfg.ports[p].granularity != module_cfg.ports[p].granularity)
        {
            fprintf(stderr, "the model's ports must be the module's first ports\n");
            return 2;
        }
    }
    int active = model_cfg.nb_inputs();

    std::vector<SnaxSparseArb> arbs;
    std::vector<std::vector<int>> bank_inputs;
    for (int b = 0; b < NUM_OUT; b++)
    {
        arbs.push_back(SnaxSparseArb(model_cfg.inputs_per_bank()));
        bank_inputs.push_back(model_cfg.bank_inputs(b));
    }

    VerilatedContext ctx;
    VSparseInterconnect *t = new VSparseInterconnect(&ctx);
    for (int i = 0; i < NUM_INP; i++)
    {
        drive_req(t, i, false, 0, false);
    }
    for (int b = 0; b < NUM_OUT; b++)
    {
        drive_bank(t, b, true);
    }
    t->reset = 1;
    for (int c = 0; c < 4; c++)
    {
        t->clock = 0;
        t->eval();
        t->clock = 1;
        t->eval();
    }
    t->reset = 0;

    std::uniform_real_distribution<double> uniform(0.0, 1.0);
    auto chance = [&](double p) { return uniform(rng) < p; };
    double p_valid = 0, p_priority = 0, p_refuse = 0;
    std::vector<int> window;

    // What the stimulus covered, counted apart from the arbiter
    long picks = 0, contested = 0, by_priority = 0, after_refusal = 0, after_idle = 0,
        refusals = 0;
    long sel_diffs = 0, ready_diffs = 0;
    std::vector<long> last_request(NUM_OUT, -10), last_refusal(NUM_OUT, -10);

    std::vector<bool> valid(NUM_INP), priority(NUM_INP), bank_ready(NUM_OUT);
    std::vector<int> bank(NUM_INP), winner(NUM_OUT);

    for (long cycle = 0; cycle < cycles; cycle++)
    {
        if (cycle % PHASE == 0)
        {
            const double loads[] = {0.05, 0.3, 0.6, 0.95};
            const int spreads[] = {1, 2, 4, 32};
            const double priorities[] = {0.0, 0.2, 0.5, 1.0};
            const double refuse[] = {0.0, 0.1, 0.4};
            p_valid = loads[rng() % 4];
            p_priority = priorities[rng() % 4];
            p_refuse = refuse[rng() % 3];
            int spread = spreads[rng() % 4];
            window.clear();
            while ((int)window.size() < spread)
            {
                int b = rng() % NUM_OUT;
                bool seen = false;
                for (int w : window)
                {
                    seen |= w == b;
                }
                if (!seen)
                {
                    window.push_back(b);
                }
            }
        }

        // Requests: a bank in the phase's window the input may reach, else
        // any bank it may reach
        for (int i = 0; i < NUM_INP; i++)
        {
            valid[i] = i < active && chance(p_valid);
            priority[i] = chance(p_priority);
            int g, j;
            port_of(module_cfg, i, g, j);
            std::vector<int> legal;
            for (int w : window)
            {
                if (w % g == j % g)
                {
                    legal.push_back(w);
                }
            }
            if (legal.empty())
            {
                for (int b = j % g; b < NUM_OUT; b += g)
                {
                    legal.push_back(b);
                }
            }
            bank[i] = legal[rng() % legal.size()];
            drive_req(t, i, valid[i], ((uint32_t)i << WORD_SHIFT) | (bank[i] << 3), priority[i]);
        }
        for (int b = 0; b < NUM_OUT; b++)
        {
            bank_ready[b] = !chance(p_refuse);
            drive_bank(t, b, bank_ready[b]);
        }
        t->clock = 0;
        t->eval();

        // The model's pick per bank against the module's request
        for (int b = 0; b < NUM_OUT; b++)
        {
            uint64_t req = 0, high = 0;
            int count = 0;
            for (size_t local = 0; local < bank_inputs[b].size(); local++)
            {
                int i = bank_inputs[b][local];
                if (valid[i] && bank[i] == b)
                {
                    req |= 1ULL << local;
                    high |= (uint64_t)priority[i] << local;
                    count++;
                }
            }
            winner[b] = -1;
            if (req == 0)
            {
                if (bank_valid(t, b))
                {
                    if (sel_diffs++ < 10)
                    {
                        printf("cycle %ld bank %d: no request, the module sends 0x%x\n", cycle, b,
                            bank_addr(t, b));
                    }
                }
                continue;
            }

            picks++;
            contested += count > 1;
            by_priority += high != 0 && (req & ~high) != 0;
            after_refusal += last_refusal[b] == cycle - 1 && count > 1;
            after_idle += last_request[b] < cycle - 1 && last_request[b] >= 0 && count > 1;
            last_request[b] = cycle;

            winner[b] = bank_inputs[b][arbs[b].pick(cycle, req, high)];
            if (!bank_valid(t, b) || (int)bank_addr(t, b) != winner[b])
            {
                if (sel_diffs++ < 10)
                {
                    printf("cycle %ld bank %d: model %d, module %s%d\n", cycle, b, winner[b],
                        bank_valid(t, b) ? "" : "no request, address ", bank_addr(t, b));
                }
            }
            if (!bank_ready[b])
            {
                arbs[b].refused();
                last_refusal[b] = cycle;
                refusals++;
            }
        }

        for (int i = 0; i < NUM_INP; i++)
        {
            bool expected = valid[i] && winner[bank[i]] == i && bank_ready[bank[i]];
            if (req_ready(t, i) != expected)
            {
                if (ready_diffs++ < 10)
                {
                    printf("cycle %ld input %d: ready %d, model %d\n", cycle, i, req_ready(t, i),
                        expected);
                }
            }
        }

        t->clock = 1;
        t->eval();
    }

    printf("%ld cycles, %d of %d inputs active: %ld selections (%ld contested, %ld decided by "
        "priority, %ld after a refusal, %ld after an idle cycle), %ld refusals; "
        "selection differences %ld, ready differences %ld\n",
        cycles, active, NUM_INP, picks, contested, by_priority, after_refusal, after_idle,
        refusals, sel_diffs, ready_diffs);
    t->final();
    delete t;
    return sel_diffs || ready_diffs ? 1 : 0;
}
