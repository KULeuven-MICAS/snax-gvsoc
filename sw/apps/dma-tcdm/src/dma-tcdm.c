// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The DMA against the streamer in the TCDM: the same ELFs run
// on snax_cluster's RTL and on SNAX-GVSoC. One ELF per case, chosen with
// CASE_<name>; each prints the counter it compares, chosen not to depend on
// the cores' timing (D123).
//
//   dma_vs_reader   A, B and O of the accelerator of forge/vecadd/ (add, 256
//                   beats) each on its own
//                   four banks, every beat in the next 256 B row: A on banks
//                   0 to 3 (superbank 0), B on 8 to 11, O on 16 to 19. While
//                   they stream, the DMA core copies four 64 B blocks from
//                   DRAM into rows after them: in the first run at the rows'
//                   last 64 B (superbank 3, no mover there), in the measured
//                   run at their first 64 B (superbank 0, A's). Prints the
//                   streamer's counter (977) of both runs
//
// Both runs execute the same code, so the measured one runs from a warm
// instruction cache. In the window the cores make no TCDM access: the
// compute core reads CSRs, the DMA core waits on mcycle, issues the copies
// from registers and polls the DMA. Returns the error count (O and the
// copies).

#include "snrt.h"

#include "acc_csr.h"
#include "streamer_csr_addr_map.h"

// One beat: 4 lanes of 64 bit
#define BEAT 32
// Bytes per bank word and banks: the bank of an address is (addr / 8) % 32
#define BANK_WIDTH 8
#define NB_BANKS 32
// One bank row: the same bank 256 B further
#define ROW (NB_BANKS * BANK_WIDTH)
// One superbank: 8 banks, one DMA beat
#define SUPERBANK 64

#if defined(CASE_dma_vs_reader)
static const char *name = "dma_vs_reader";
// The movers' beats, one row each, and the accelerator's loop count
#define BEATS 256
// The DMA's copies, one 64 B beat each, one row apart, after the movers'
// rows; and the cycles the DMA core waits after the barrier before the
// first, so that they fall inside the movers' run
#define COPIES 4
#define DMA_DELAY 50
// Each mover's offset in a row: A on superbank 0, B 1, O 2
#define A_OFFSET 0
#define B_OFFSET 64
#define O_OFFSET 128
// The copies' offset in a row: superbank 3 in the first run, 0 (A's) in the
// measured one
#define FIRST_DMA_OFFSET 192
#define MEASURED_DMA_OFFSET 0
#else
#error "Build with -DCASE_<name>, see the Makefile"
#endif

// The copies' source, in .bss, which base.ld places in DRAM
static uint64_t src_l2[COPIES * SUPERBANK / 8] __attribute__((aligned(SUPERBANK)));

// One run's results, in L1 for both cores
typedef struct {
    uint32_t counter;      // STREAMER_PERFORMANCE_COUNTER_CSR
    uint32_t acc_counter;  // ACC_RO_PERF_COUNT
    uint32_t errors;
} result_t;

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

static inline uint64_t *word(uint32_t area, uint32_t row, uint32_t offset) {
    return (uint64_t *)(area + row * ROW + offset);
}

// Word i of the copies at copies: copy i / 8, one row each
static inline uint64_t *copy_word(uint32_t copies, uint32_t i) {
    return word(copies, i / 8, 8 * (i % 8));
}

// One run: the movers and the copies to dma_offset in the rows after them.
// Not inlined, so that both runs execute this code.
static __attribute__((noinline)) void run(uint32_t area, uint32_t dma_offset,
                                          result_t *r) {
    uint32_t copies = area + BEATS * ROW + dma_offset;

    if (snrt_is_compute_core()) {
        for (uint32_t row = 0; row < BEATS; row++)
            for (uint32_t lane = 0; lane < 4; lane++) *word(area, row, O_OFFSET + 8 * lane) = 0;
        for (uint32_t i = 0; i < COPIES * SUPERBANK / 8; i++)
            *copy_word(copies, i) = 0;
        asm volatile("fence" ::: "memory");
        csrw_ss(BASE_PTR_READER_0_LOW, area + A_OFFSET);
        csrw_ss(BASE_PTR_READER_0_HIGH, 0);
        csrw_ss(S_STRIDE_READER_0_0, 8);
        csrw_ss(T_BOUND_READER_0_0, BEATS);
        csrw_ss(T_STRIDE_READER_0_0, ROW);
        csrw_ss(BASE_PTR_READER_1_LOW, area + B_OFFSET);
        csrw_ss(BASE_PTR_READER_1_HIGH, 0);
        csrw_ss(S_STRIDE_READER_1_0, 8);
        csrw_ss(T_BOUND_READER_1_0, BEATS);
        csrw_ss(T_STRIDE_READER_1_0, ROW);
        csrw_ss(BASE_PTR_WRITER_0_LOW, area + O_OFFSET);
        csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
        csrw_ss(S_STRIDE_WRITER_0_0, 8);
        csrw_ss(T_BOUND_WRITER_0_0, BEATS);
        csrw_ss(T_STRIDE_WRITER_0_0, ROW);
        csrw_ss(ACC_RW_LOOP_COUNT, BEATS);
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        csrw_ss(ACC_RW_START, 1);
        csrw_ss(STREAMER_START_CSR, 1);
        while (csrr_ss(ACC_RO_BUSY)) {
        }
        while (csrr_ss(STREAMER_BUSY_CSR)) {
        }
    } else if (snrt_is_dm_core()) {
        uint32_t t0 = snrt_mcycle();
        while (snrt_mcycle() - t0 < DMA_DELAY) {
        }
        for (uint32_t k = 0; k < COPIES; k++)
            snrt_dma_start_1d((void *)(copies + k * ROW), src_l2 + k * SUPERBANK / 8,
                              SUPERBANK);
        snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        uint32_t errors = 0;
        for (uint32_t row = 0; row < BEATS; row++)
            for (uint32_t lane = 0; lane < 4; lane++)
                errors += *word(area, row, O_OFFSET + 8 * lane) !=
                          *word(area, row, A_OFFSET + 8 * lane) +
                              *word(area, row, B_OFFSET + 8 * lane);
        for (uint32_t i = 0; i < COPIES * SUPERBANK / 8; i++)
            errors += *copy_word(copies, i) != src_l2[i];
        r->counter = csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR);
        r->acc_counter = csrr_ss(ACC_RO_PERF_COUNT);
        r->errors = errors;
    }
}

int main() {
    // Both cores find the same area and results
    uint32_t area = align_up((uintptr_t)snrt_l1_next(), ROW);
    result_t *results = (result_t *)(area + (BEATS + COPIES) * ROW);

    if (snrt_is_compute_core()) {
        uint64_t x = 1;
        for (uint32_t row = 0; row < BEATS; row++)
            for (uint32_t lane = 0; lane < 4; lane++) {
                *word(area, row, A_OFFSET + 8 * lane) = x = x * 6364136223846793005ull + 1;
                *word(area, row, B_OFFSET + 8 * lane) = x = x * 6364136223846793005ull + 1;
            }
    } else if (snrt_is_dm_core()) {
        for (uint32_t i = 0; i < COPIES * SUPERBANK / 8; i++) src_l2[i] = 0x1000 + i;
    }
    asm volatile("fence" ::: "memory");

    run(area, FIRST_DMA_OFFSET, &results[0]);
    run(area, MEASURED_DMA_OFFSET, &results[1]);

    if (!snrt_is_compute_core()) return 0;
    uint32_t errors = results[0].errors + results[1].errors;
    printf("dma-tcdm %s: counter %u (first run %u), acc counter %u (first run %u), errors %u\n",
           name, results[1].counter, results[0].counter, results[1].acc_counter,
           results[0].acc_counter, errors);
    return errors;
}
