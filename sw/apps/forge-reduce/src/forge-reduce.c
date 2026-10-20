// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The program for a generated one-lane reduction
// (forge/<design>/, snax-forge's GVSoC generator): O[k] = the sum of A over
// RATE consecutive words, for BEATS / RATE sums, on the generated headers
// only (streamer_csr_addr_map.h and acc_csr.h from forge/<design>/include/).
// It follows the design point's derived task list (snax-forge
// snax_forge/lower/derive.py), the bases replaced by the L1 pointers. BEATS
// (the task's n) and RATE (its T) come from the fixture's manifest through
// the Makefile (-D):
//   - the two streamers, reader 0 = A: temporal bound BEATS; writer 0 = O:
//     temporal bound BEATS / RATE; both spatial stride 8 and temporal stride
//     8 (one 64-bit word per beat);
//   - the unit's loopCount, BEATS, then its len, RATE;
//   - the starts in the task list's order, the streamer's movers (one start
//     CSR for both) and then the accelerator;
//   - busy polled, the accelerator's, then the streamer's.
// Then the shell's counter (busy cycles of the run, at least its beats) and
// the sums against OUT (data/datagen.py). Returns the error count.

#include "snrt.h"

#include "acc_csr.h"
#include "data.h"
#include "streamer_csr_addr_map.h"

#if !defined(BEATS) || !defined(RATE)
#error "BEATS and RATE come from the manifest (the Makefile's -DBEATS -DRATE)"
#endif

#define SUMS (BEATS / RATE)

int main() {
    int err = 0;

    int64_t *local_a, *local_o;
    local_a = (int64_t *)snrt_l1_next();
    local_o = local_a + DATA_LEN;

    // load_A: A into L1 by the DMA core
    if (snrt_is_dm_core()) {
        snrt_dma_start_1d(local_a, A, DATA_LEN * sizeof(int64_t));
        snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        // The streamer tasks: reader 0 = A, writer 0 = O
        csrw_ss(BASE_PTR_READER_0_LOW, (uint32_t)local_a);
        csrw_ss(BASE_PTR_READER_0_HIGH, 0);
        csrw_ss(S_STRIDE_READER_0_0, 8);
        csrw_ss(T_BOUND_READER_0_0, BEATS);
        csrw_ss(T_STRIDE_READER_0_0, 8);

        csrw_ss(BASE_PTR_WRITER_0_LOW, (uint32_t)local_o);
        csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
        csrw_ss(S_STRIDE_WRITER_0_0, 8);
        csrw_ss(T_BOUND_WRITER_0_0, SUMS);
        csrw_ss(T_STRIDE_WRITER_0_0, 8);

        // The accelerator task: n beats, one sum per T
        csrw_ss(ACC_RW_LOOP_COUNT, BEATS);
        csrw_ss(ACC_RW_LEN, RATE);

        // The starts, in the task list's order
        csrw_ss(STREAMER_START_CSR, 1);
        csrw_ss(ACC_RW_START, 1);

        while (csrr_ss(ACC_RO_BUSY)) {
        };
        while (csrr_ss(STREAMER_BUSY_CSR)) {
        };

        uint32_t counter = csrr_ss(ACC_RO_PERF_COUNT);
        int counter_short = counter < BEATS;
        err += counter_short;

        int data_errors = 0;
        for (uint32_t i = 0; i < SUMS; i++) {
            if (OUT[i] != *(local_o + i)) {
                data_errors++;
            }
        }
        err += data_errors;

        printf("forge-reduce data: %d errors (%u sums)\n", data_errors,
               (uint32_t)SUMS);
        printf("forge-reduce counter: %u\n", counter);
        printf("forge-reduce errors: %d\n", err);
    }

    return err;
}
