// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The shell program, on snax_hjson with forge/vecadd/snax_forge.hjson: SnaxShell
// and SnaxUnit (ElementwiseLanes add, L = 0, II 1, 4 lanes of 64 bit) behind
// the streamer (snax/snax_accelerator.py). snax_cluster's snax-alu DMA and
// streamer setup; the streamer's and the group's CSRs (START, JOBS, STATUS,
// COUNTER, snax-forge C§17) from forge/vecadd/include/. One streamer run of
// LOOP_ITER beats feeds three unit runs of RUN_BEATS jobs each:
//   - start 1, alone: once STATUS bit 0 (busy) is 0, the counter is run 1's
//     busy cycles, printed (`snax-shell counter: <n>`); regress.py checks it
//     against the unit's trace line of its first run (busy + stall_in +
//     stall_out + flush); STATUS then reads 2 (done, sticky);
//   - start 2, then start 3 at once: start 3 is held until run 2 is done (the
//     core stalls on the write), so the mcycle span from before start 2 to
//     after start 3 is at least run 2's busy cycles, so at least RUN_BEATS;
//   - the data: O = A + B over the three runs;
//   - then a start with JOBS 0, the empty run: STATUS reads 2 (not busy,
//     done) and the counter 0.
// Each check holds whatever the code layout: a run of RUN_BEATS firings is
// busy at least RUN_BEATS cycles, and how many more follows the core's and
// the streamer's timing. Returns the error count.

#include "snrt.h"

#include "acc_csr.h"
#include "data.h"
#include "streamer_csr_addr_map.h"

// Three unit runs on one streamer run (LOOP_ITER is a uint64_t)
#define RUN_BEATS ((uint32_t)(LOOP_ITER / 3))

int main() {
    int err = 0;

    uint64_t *local_a, *local_b, *local_o;
    local_a = (uint64_t *)snrt_l1_next();
    local_b = local_a + DATA_LEN;
    local_o = local_b + DATA_LEN;

    // A and B into L1 by the DMA core, as snax_cluster's snax-alu
    if (snrt_is_dm_core()) {
        size_t vector_size = DATA_LEN * sizeof(uint64_t);
        snrt_dma_start_1d(local_a, A, vector_size);
        snrt_dma_start_1d(local_b, B, vector_size);
        snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        csrw_ss(BASE_PTR_READER_0_LOW, (uint32_t)local_a);
        csrw_ss(BASE_PTR_READER_0_HIGH, 0);
        csrw_ss(S_STRIDE_READER_0_0, 8);
        csrw_ss(T_BOUND_READER_0_0, LOOP_ITER);
        csrw_ss(T_STRIDE_READER_0_0, 32);
        csrw_ss(BASE_PTR_READER_1_LOW, (uint32_t)local_b);
        csrw_ss(BASE_PTR_READER_1_HIGH, 0);
        csrw_ss(S_STRIDE_READER_1_0, 8);
        csrw_ss(T_BOUND_READER_1_0, LOOP_ITER);
        csrw_ss(T_STRIDE_READER_1_0, 32);
        csrw_ss(BASE_PTR_WRITER_0_LOW, (uint32_t)local_o);
        csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
        csrw_ss(S_STRIDE_WRITER_0_0, 8);
        csrw_ss(T_BOUND_WRITER_0_0, LOOP_ITER);
        csrw_ss(T_STRIDE_WRITER_0_0, 32);
        csrw_ss(ACC_RW_JOBS, RUN_BEATS);

        csrw_ss(STREAMER_START_CSR, 1);

        // Run 1 alone: its counter, then STATUS done
        csrw_ss(ACC_RW_START, 1);
        while (csrr_ss(ACC_RO_STATUS) & 1) {
        };
        uint32_t counter = csrr_ss(ACC_RO_COUNTER);
        int counter_short = counter < RUN_BEATS;
        err += counter_short;
        uint32_t status_done = csrr_ss(ACC_RO_STATUS);
        int not_done = status_done != 2;
        err += not_done;

        // Runs 2 and 3: start 3 held
        uint32_t t0 = snrt_mcycle();
        csrw_ss(ACC_RW_START, 1);
        csrw_ss(ACC_RW_START, 1);
        uint32_t t1 = snrt_mcycle();
        uint32_t held = t1 - t0;
        int held_short = held < RUN_BEATS;
        err += held_short;

        while (csrr_ss(ACC_RO_STATUS) & 1) {
        };
        while (csrr_ss(STREAMER_BUSY_CSR)) {
        };

        int data_errors = 0;
        for (uint32_t i = 0; i < DATA_LEN; i++) {
            if (OUT[i] != *(local_o + i)) {
                data_errors++;
            }
        }
        err += data_errors;

        // A start with JOBS 0: the empty run, ended by the shell in its cycle
        csrw_ss(ACC_RW_JOBS, 0);
        csrw_ss(ACC_RW_START, 1);
        uint32_t status_zero = csrr_ss(ACC_RO_STATUS);
        uint32_t counter_zero = csrr_ss(ACC_RO_COUNTER);
        int zero_off = status_zero != 2 || counter_zero != 0;
        err += zero_off;

        printf("snax-shell data: %d errors (%u words)\n", data_errors,
               (uint32_t)DATA_LEN);
        printf("snax-shell counter: %u\n", counter);
        printf("snax-shell first run: counter %u, at least %u beats%s\n", counter,
               RUN_BEATS, counter_short ? " SHORT" : "");
        printf("snax-shell first run: STATUS %u after it, done (2)%s\n", status_done,
               not_done ? " OFF" : "");
        printf("snax-shell held start: mcycle span %u, at least %u beats%s\n", held,
               RUN_BEATS, held_short ? " SHORT" : "");
        printf("snax-shell JOBS 0: STATUS %u, counter %u%s\n", status_zero,
               counter_zero, zero_off ? " OFF" : "");
        printf("snax-shell errors: %d\n", err);
    }

    return err;
}
