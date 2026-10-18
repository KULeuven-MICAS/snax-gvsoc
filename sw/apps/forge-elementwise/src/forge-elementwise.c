// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The program of GEN3 step 5 for a generated elementwise accelerator
// (forge/<design>/, snax-forge's GVSoC generator): O = A op B over DATA_LEN
// words, on the generated headers only (streamer_csr_addr_map.h and
// acc_csr.h from forge/<design>/include/). It follows the design point's
// derived task list (snax-forge snax_forge/lower/derive.py), the bases
// replaced by the L1 pointers. BEATS (the task's n) and LANES (N / BEATS)
// come from the fixture's manifest through the Makefile (-D):
//   - the three streamers, reader 0 = A, reader 1 = B, writer 0 = O: base,
//     spatial stride 8 (one 64-bit word per lane), temporal bound BEATS,
//     temporal stride 8 * LANES;
//   - the unit's loopCount, BEATS;
//   - the starts in the task list's order, the streamer's movers (one start
//     CSR for the three) and then the accelerator;
//   - busy polled, the accelerator's, then the streamer's.
// Then the shell's counter (busy cycles of the run, at least its beats) and
// the data against OUT. Returns the error count. Only OUT and the data come
// from datagen.py (its LOOP_ITER, from SPATIAL_PAR 4, is not used).

#include "snrt.h"

#include "acc_csr.h"
#include "data.h"
#include "streamer_csr_addr_map.h"

#if !defined(BEATS) || !defined(LANES)
#error "BEATS and LANES come from the manifest (the Makefile's -DBEATS -DLANES)"
#endif

int main() {
    int err = 0;

    uint64_t *local_a, *local_b, *local_o;
    local_a = (uint64_t *)snrt_l1_next();
    local_b = local_a + DATA_LEN;
    local_o = local_b + DATA_LEN;

    // load_A and load_B: A and B into L1 by the DMA core
    if (snrt_is_dm_core()) {
        size_t vector_size = DATA_LEN * sizeof(uint64_t);
        snrt_dma_start_1d(local_a, A, vector_size);
        snrt_dma_start_1d(local_b, B, vector_size);
        snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        // The streamer tasks: reader 0 = A, reader 1 = B, writer 0 = O
        csrw_ss(BASE_PTR_READER_0_LOW, (uint32_t)local_a);
        csrw_ss(BASE_PTR_READER_0_HIGH, 0);
        csrw_ss(S_STRIDE_READER_0_0, 8);
        csrw_ss(T_BOUND_READER_0_0, BEATS);
        csrw_ss(T_STRIDE_READER_0_0, 8 * LANES);

        csrw_ss(BASE_PTR_READER_1_LOW, (uint32_t)local_b);
        csrw_ss(BASE_PTR_READER_1_HIGH, 0);
        csrw_ss(S_STRIDE_READER_1_0, 8);
        csrw_ss(T_BOUND_READER_1_0, BEATS);
        csrw_ss(T_STRIDE_READER_1_0, 8 * LANES);

        csrw_ss(BASE_PTR_WRITER_0_LOW, (uint32_t)local_o);
        csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
        csrw_ss(S_STRIDE_WRITER_0_0, 8);
        csrw_ss(T_BOUND_WRITER_0_0, BEATS);
        csrw_ss(T_STRIDE_WRITER_0_0, 8 * LANES);

        // The accelerator task: n beats
        csrw_ss(ACC_RW_LOOP_COUNT, BEATS);

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
        for (uint32_t i = 0; i < DATA_LEN; i++) {
            if (OUT[i] != *(local_o + i)) {
                data_errors++;
            }
        }
        err += data_errors;

        printf("forge-elementwise data: %d errors (%u words)\n", data_errors,
               (uint32_t)DATA_LEN);
        printf("forge-elementwise counter: %u\n", counter);
        printf("forge-elementwise errors: %d\n", err);
    }

    return err;
}
