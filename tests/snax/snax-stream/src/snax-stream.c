// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// snax-alu's three streamers on SNAX-GVSoC with the test datapath in the
// ALU's place (SG3): readers A and B and the writer O set up as snax-alu sets
// them, through snax-alu's library. The datapath copies A, then B, at one
// firing per cycle and per 3 cycles; each run checks O and prints the
// streamer's counter (977) and the datapath's (982). Not for the RTL: there
// the ALU computes, and mode 0x20 means nothing. Returns the error count.

#include "snrt.h"

#include "snax-alu-lib.h"
#include "streamer_csr_addr_map.h"

// Beats per stream, 4 words of 64 bit each, as snax-alu's LOOP_ITER
#define BEATS 25
#define WORDS (4 * BEATS)

typedef struct {
    const char *name;
    uint32_t from_b;  // the datapath copies B, else A (mode bit 0)
    uint32_t k;       // one firing at most every k cycles (mode bits 7:4)
} run_t;

static const run_t runs[] = {{"copy A, k=1", 0, 1}, {"copy B, k=3", 1, 3}};
#define NB_RUNS (sizeof(runs) / sizeof(runs[0]))

int main() {
    if (!snrt_is_compute_core()) return 0;

    // As snax-alu: A, B and O one after the other from the start of L1
    uint64_t *a = (uint64_t *)snrt_l1_next();
    uint64_t *b = a + WORDS;
    uint64_t *o = b + WORDS;
    for (uint32_t i = 0; i < WORDS; i++) {
        a[i] = 0xA000000000000000ull | i;
        b[i] = 0xB000000000000000ull | i;
    }

    uint32_t errors = 0;
    for (uint32_t r = 0; r < NB_RUNS; r++) {
        for (uint32_t i = 0; i < WORDS; i++) o[i] = 0;
        asm volatile("fence" ::: "memory");

        configure_streamer_a((uint32_t)a, 0, 8, BEATS, 32);
        configure_streamer_b((uint32_t)b, 0, 8, BEATS, 32);
        configure_streamer_o((uint32_t)o, 0, 8, BEATS, 32);
        configure_alu(runs[r].from_b | ((runs[r].k - 1) << 4), BEATS);
        start_streamer();
        start_alu();
        while (read_busy_alu()) {
        }
        while (read_busy_streamer()) {
        }

        uint64_t *src = runs[r].from_b ? b : a;
        uint32_t err = 0;
        for (uint32_t i = 0; i < WORDS; i++) {
            if (o[i] != src[i]) err++;
        }
        errors += err;
        printf("snax-stream %s: errors %u, streamer counter %u, datapath counter %u\n",
               runs[r].name, err, csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR),
               csrr_ss(ALU_RO_PERF_COUNT));
    }
    return errors;
}
