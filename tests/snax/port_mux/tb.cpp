/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxPortMuxRule (snax/snax_port_mux.hpp) against hand-worked cases, g++
// only (README.md). The setting is mvt_1_dot2's shared streamer at W = 8
// (snax-forge D169): groups dot (0) and vadd (1); movers reader0 (8),
// reader1 (8), writer0 (8); dot's ports vmul.a, vmul.b on the readers and
// vsum.out (1 channel) on the writer, vadd's vadd.a, vadd.b, vadd.out (8).
// Exit 1 on a difference.

#include <cstdio>
#include <vector>
#include "snax_port_mux.hpp"


static int failures = 0;

#define CHECK(cond)                                                     \
    do                                                                  \
    {                                                                   \
        if (!(cond))                                                    \
        {                                                               \
            printf("line %d: %s\n", __LINE__, #cond);                   \
            failures++;                                                 \
        }                                                               \
    } while (0)


static bool refused(int nb_groups, std::vector<SnaxMuxMover> movers,
    std::vector<SnaxMuxPort> ports)
{
    try
    {
        SnaxPortMuxRule(nb_groups, movers, ports);
    }
    catch (const std::invalid_argument &)
    {
        return true;
    }
    return false;
}


int main()
{
    enum { VMUL_A, VMUL_B, VSUM_OUT, VADD_A, VADD_B, VADD_OUT };
    std::vector<SnaxMuxMover> movers = {{true, 8}, {true, 8}, {false, 8}};
    std::vector<SnaxMuxPort> ports = {
        {0, 0, 8}, {0, 1, 8}, {0, 2, 1},    // dot
        {1, 0, 8}, {1, 1, 8}, {1, 2, 8},    // vadd
    };
    SnaxPortMuxRule rule(2, movers, ports);
    rule.reset();

    // After reset group 0 is selected: dot's ports pass, vadd's are fatal
    CHECK(rule.selected() == 0);
    CHECK(rule.check(VMUL_A, false, 64) == SNAX_MUX_OK);
    CHECK(rule.check(VMUL_B, false, 0) == SNAX_MUX_OK);
    CHECK(rule.check(VSUM_OUT, true, 8) == SNAX_MUX_OK);
    CHECK(rule.check(VADD_A, false, 0) == SNAX_MUX_NOT_SELECTED);
    CHECK(rule.check(VADD_OUT, true, 64) == SNAX_MUX_NOT_SELECTED);

    // Direction and size: a port's own beat or a probe, never the mover's size for a narrow one
    CHECK(rule.check(VMUL_A, true, 64) == SNAX_MUX_WRONG_ACCESS);
    CHECK(rule.check(VSUM_OUT, false, 8) == SNAX_MUX_WRONG_ACCESS);
    CHECK(rule.check(VSUM_OUT, true, 64) == SNAX_MUX_WRONG_ACCESS);
    CHECK(rule.check(VMUL_A, false, 32) == SNAX_MUX_WRONG_ACCESS);

    // The mover's access: a probe stays a probe, a beat is the mover's 8 words
    CHECK(rule.mover_of(VSUM_OUT) == 2 && rule.mover_of(VADD_B) == 1);
    CHECK(rule.mover_size(VSUM_OUT, 0) == 0);
    CHECK(rule.mover_size(VSUM_OUT, 8) == 64);

    // vsum's one-word sum goes to writer0's lane 0, its other 7 lanes 0
    uint64_t sum = 0x1234;
    uint64_t wide[8];
    for (uint64_t &w : wide)
    {
        w = 0xdead;
    }
    rule.to_mover(VSUM_OUT, &sum, wide);
    CHECK(wide[0] == 0x1234);
    for (int l = 1; l < 8; l++)
    {
        CHECK(wide[l] == 0);
    }

    // Selecting: refused while the streamer is busy and past the last group, kept after
    CHECK(rule.select(1, true) == SNAX_MUX_BUSY && rule.selected() == 0);
    CHECK(rule.select(2, false) == SNAX_MUX_NO_GROUP && rule.selected() == 0);
    CHECK(rule.select(1, false) == SNAX_MUX_OK && rule.selected() == 1);

    // vadd selected: its ports pass, dot's are fatal
    CHECK(rule.check(VADD_A, false, 64) == SNAX_MUX_OK);
    CHECK(rule.check(VADD_OUT, true, 64) == SNAX_MUX_OK);
    CHECK(rule.check(VMUL_A, false, 0) == SNAX_MUX_NOT_SELECTED);
    CHECK(rule.check(VSUM_OUT, true, 8) == SNAX_MUX_NOT_SELECTED);

    // A full-width beat both ways, word for word
    uint64_t in[8], out[8];
    for (int l = 0; l < 8; l++)
    {
        in[l] = 100 + l;
    }
    rule.to_port(VADD_A, in, out);
    rule.to_mover(VADD_OUT, out, wide);
    for (int l = 0; l < 8; l++)
    {
        CHECK(out[l] == (uint64_t)(100 + l) && wide[l] == (uint64_t)(100 + l));
    }

    // A narrow reader port: its first words only (dot 1's shared reader, 4 of a mover's 8)
    SnaxPortMuxRule narrow(2, {{true, 8}}, {{0, 0, 8}, {1, 0, 4}});
    narrow.reset();
    CHECK(narrow.select(1, false) == SNAX_MUX_OK);
    uint64_t four[4] = {0, 0, 0, 0};
    narrow.to_port(1, in, four);
    for (int l = 0; l < 4; l++)
    {
        CHECK(four[l] == (uint64_t)(100 + l));
    }
    CHECK(narrow.check(1, false, 32) == SNAX_MUX_OK);
    CHECK(narrow.check(1, false, 64) == SNAX_MUX_WRONG_ACCESS);

    // Reset selects group 0 again
    rule.reset();
    CHECK(rule.selected() == 0);

    // Configurations that cannot be
    CHECK(refused(0, movers, {}));
    CHECK(refused(2, movers, {{2, 0, 8}}));         // no group 2
    CHECK(refused(2, movers, {{0, 3, 8}}));         // no mover 3
    CHECK(refused(2, movers, {{0, 0, 9}}));         // wider than its mover
    CHECK(refused(2, movers, {{0, 0, 0}}));         // no channel
    CHECK(refused(2, movers, {{0, 0, 8}, {0, 0, 4}}));  // two of dot's ports on reader0
    CHECK(!refused(2, movers, ports));

    if (failures)
    {
        printf("%d differences\n", failures);
        return 1;
    }
    printf("OK\n");
    return 0;
}
