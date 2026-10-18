// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The shell program of GEN3 step 2, for the snax_tiled_add target: SnaxShell
// and SnaxUnit (lockstep add, 4 lanes of 64 bit) behind snax-alu's streamer
// (snax/snax_tiled_add_acc.py). snax-alu's DMA and streamer setup; the
// shell's CSRs by hand below. One streamer run of LOOP_ITER beats feeds two
// unit runs of RUN_BEATS each:
//   - start 1, then start 2 at once: start 2 is held until run 1 is done (the
//     core stalls on the write), so the mcycle span around the two writes is
//     at least run 1's busy cycles. The span starts before start 1: between
//     the writes the core may wait for an instruction fetch (10 cycles in one
//     build), which a span around start 2 alone would leave out;
//   - the data: O = A + B over both runs;
//   - the counter after run 2: run 2's busy cycles (reset by its start);
//   - then a start with loopCount 0: busy stays 0, the counter reads 0.
// The busy cycles are the unit's busy + stall_in + stall_out of its trace
// lines (docs/notes/NOTES.md, GEN3 step 2). Returns the error count.

#include "snrt.h"

#include "data.h"
#include "snax-alu-lib.h"
#include "streamer_csr_addr_map.h"

// The shell's CSRs, after the streamer's (snax_tiled_add_acc.py): the field
// loopCount and start, read-write; busy and the counter, read-only
#define SHELL_LOOP_COUNT 978
#define SHELL_START 979
#define SHELL_BUSY 980
#define SHELL_COUNTER 981

// Two unit runs on one streamer run
#define RUN_BEATS (LOOP_ITER / 2)

// The busy cycles of the unit's two runs, from its trace lines
#define RUN0_BUSY_CYCLES 16
#define RUN1_BUSY_CYCLES 16

int main() {
    int err = 0;

    uint64_t *local_a, *local_b, *local_o;
    local_a = (uint64_t *)snrt_l1_next();
    local_b = local_a + DATA_LEN;
    local_o = local_b + DATA_LEN;

    // A and B into L1 by the DMA core, as snax-alu
    if (snrt_is_dm_core()) {
        size_t vector_size = DATA_LEN * sizeof(uint64_t);
        snrt_dma_start_1d(local_a, A, vector_size);
        snrt_dma_start_1d(local_b, B, vector_size);
        snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        configure_streamer_a((uint64_t)local_a, 0, 8, LOOP_ITER, 32);
        configure_streamer_b((uint64_t)local_b, 0, 8, LOOP_ITER, 32);
        configure_streamer_o((uint64_t)local_o, 0, 8, LOOP_ITER, 32);
        csrw_ss(SHELL_LOOP_COUNT, RUN_BEATS);

        start_streamer();
        uint32_t t0 = snrt_mcycle();
        csrw_ss(SHELL_START, 1);
        csrw_ss(SHELL_START, 1);
        uint32_t t1 = snrt_mcycle();

        while (csrr_ss(SHELL_BUSY)) {
        };
        while (read_busy_streamer()) {
        };

        int data_errors = 0;
        for (uint32_t i = 0; i < DATA_LEN; i++) {
            if (OUT[i] != *(local_o + i)) {
                data_errors++;
            }
        }
        err += data_errors;

        uint32_t counter = csrr_ss(SHELL_COUNTER);
        uint32_t held = t1 - t0;
        int counter_off = counter != RUN1_BUSY_CYCLES;
        int held_short = held < RUN0_BUSY_CYCLES;
        err += counter_off + held_short;

        // A start with loopCount 0: the unit ignores it, the shell takes it
        csrw_ss(SHELL_LOOP_COUNT, 0);
        csrw_ss(SHELL_START, 1);
        uint32_t busy_zero = csrr_ss(SHELL_BUSY);
        uint32_t counter_zero = csrr_ss(SHELL_COUNTER);
        int zero_off = busy_zero != 0 || counter_zero != 0;
        err += zero_off;

        printf("snax-shell data: %d errors (%d words)\n", data_errors, DATA_LEN);
        printf("snax-shell counter: %u (run 2's busy cycles %u)%s\n", counter,
               RUN1_BUSY_CYCLES, counter_off ? " OFF" : "");
        printf("snax-shell held start: mcycle span %u (run 1's busy cycles %u)%s\n",
               held, RUN0_BUSY_CYCLES, held_short ? " SHORT" : "");
        printf("snax-shell loopCount 0: busy %u, counter %u%s\n", busy_zero,
               counter_zero, zero_off ? " OFF" : "");
        printf("snax-shell errors: %d\n", err);
    }

    return err;
}
