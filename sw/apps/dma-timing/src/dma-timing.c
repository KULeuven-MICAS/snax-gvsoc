// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// DMA timing program: the same ELF runs on snax_cluster's RTL and on
// SNAX-GVSoC. The DMA core copies between DRAM (L2) and L1 at a few sizes,
// and transposes an N x N matrix by 2-D transfers of one element per burst,
// and measures each case with mcycle and the cluster's DMA perf counters;
// the core 0 prints one line per case after the barrier, checks busy, r and
// w against the RTL's and returns the errors and the cases off them.

#include "snrt.h"

#include "data.h"

// One DMA beat (512 bit).
#define BEAT 64

// The transposed matrix's side, and the L1 bytes of A and of its transpose
// at the largest row pitch (int64).
#define N 64
#define MAX_BYTES (8 * N * N)

// Counters 0 to NB_CNT-1, in the order they are printed.
#define NB_CNT 6
static const enum snrt_perf_cnt_type cnt_type[NB_CNT] = {
    SNRT_PERF_CNT_DMA_BUSY,      // cycles the iDMA's busy_o is high
    SNRT_PERF_CNT_DMA_R_DONE,    // read beats
    SNRT_PERF_CNT_DMA_W_DONE,    // write beats
    SNRT_PERF_CNT_DMA_AR_STALL,  // read requests waiting for the memory
    SNRT_PERF_CNT_DMA_W_STALL,   // memory takes writes, no data there
    SNRT_PERF_CNT_DMA_R_STALL,   // read data waiting on a full buffer
};

// T_L1 and T_L2 transpose A, in L1 or in DRAM, into T in L1: for each
// column k, snrt_dma_start_2d(T + pitch * k, A + bytes * k, bytes, bytes,
// A's pitch, N), N bursts of one element.
enum dir { IDLE, L2_TO_L1, L1_TO_L2, T_L1, T_L2 };

typedef struct {
    enum dir dir;
    // A copy: `copies` back-to-back copies, each `bytes` long, placed one
    // after the other. A transpose: `copies` columns of N elements of
    // `bytes` each, A and T at the row pitch `pitch` in L1.
    uint32_t copies;
    uint32_t bytes;
    uint32_t pitch;
    // NB (D123): the RTL's busy, r and w do not depend on the core, so any
    // other value is the DMA's own timing moving
    uint32_t rtl_busy, rtl_r, rtl_w;
} dma_case_t;

static const dma_case_t cases[] = {
    {IDLE, 0, 0, 0, 0, 0, 0},
    {L2_TO_L1, 1, 64, 0, 14, 1, 1},
    {L2_TO_L1, 1, 256, 0, 17, 4, 4},
    {L2_TO_L1, 1, 800, 0, 26, 13, 13},
    {L2_TO_L1, 1, 4096, 0, 77, 64, 64},
    {L2_TO_L1, 1, 8192, 0, 141, 128, 128},
    {L2_TO_L1, 2, 800, 0, 39, 26, 26},
    {L2_TO_L1, 4, 800, 0, 65, 52, 52},
    {L1_TO_L2, 1, 800, 0, 20, 13, 13},
    {T_L1, 1, 1, 64, 173, 64, 64},         // one int8 column
    {T_L1, N, 1, 64, 10925, 4096, 4096},   // int8, rows contiguous
    {T_L1, N, 1, 72, 10925, 4096, 4096},   // int8, rows of 9 words
    {T_L1, N, 8, 512, 10925, 4096, 4096},  // int64
    {T_L2, N, 1, 64, 17759, 4096, 4096},   // int8 from DRAM
};
#define NB_CASES (sizeof(cases) / sizeof(cases[0]))

typedef struct {
    uint32_t issue;  // mcycle from before the first start to after the last
    uint32_t done;   // mcycle from before the first start to after the wait
    uint32_t cnt[NB_CNT];
    uint32_t errors;
} result_t;

// The L1-to-L2 destination, in .bss, which base.ld places in DRAM.
static uint32_t dst_l2[800 / 4] __attribute__((aligned(BEAT)));

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

static void clear(uint32_t *dst, uint32_t bytes) {
    for (uint32_t i = 0; i < bytes / 4; i++) dst[i] = 0;
    // The DMA must not overtake these stores.
    asm volatile("fence" ::: "memory");
}

static uint32_t compare(const uint32_t *a, const uint32_t *b, uint32_t bytes) {
    uint32_t errors = 0;
    for (uint32_t i = 0; i < bytes / 4; i++) errors += a[i] != b[i];
    return errors;
}

// A from DRAM into L1 at the row pitch `pitch` (not measured).
static void load(uint8_t *a, uint32_t row, uint32_t pitch) {
    if (pitch == row)
        snrt_dma_start_1d(a, src_l2, N * row);
    else
        snrt_dma_start_2d(a, src_l2, row, pitch, row, N);
    snrt_dma_wait_all();
}

// The elements of T's first `cols` rows that differ from A's columns, both
// in L1 at the row pitch `pitch`.
static uint32_t check_transpose(const uint8_t *t, const uint8_t *a,
                                uint32_t elem, uint32_t cols, uint32_t pitch) {
    uint32_t errors = 0;
    for (uint32_t k = 0; k < cols; k++) {
        for (uint32_t r = 0; r < N; r++) {
            const uint8_t *x = t + k * pitch + r * elem;  // T[k][r]
            const uint8_t *y = a + r * pitch + k * elem;  // A[r][k]
            uint32_t bad = 0;
            for (uint32_t i = 0; i < elem; i++) bad |= x[i] != y[i];
            errors += bad;
        }
    }
    return errors;
}

static void run_case(const dma_case_t *c, uint8_t *l1, uint8_t *t,
                     result_t *r) {
    // Read the case before the first mark: `cases` is in DRAM, and
    // snrt_mcycle's memory clobber would make the compiler reload it inside
    // the measured window.
    const uint32_t copies = c->copies;
    const uint32_t bytes = c->bytes;
    const uint32_t pitch = c->pitch;
    const int transpose = c->dir == T_L1 || c->dir == T_L2;
    const uint32_t total = transpose ? N * pitch : copies * bytes;
    const uint32_t src_pitch = c->dir == T_L2 ? N * bytes : pitch;
    uint8_t *src =
        c->dir == L1_TO_L2 || c->dir == T_L1 ? l1 : (uint8_t *)src_l2;
    uint8_t *dst = c->dir == L1_TO_L2 ? (uint8_t *)dst_l2 : transpose ? t : l1;

    clear((uint32_t *)dst, total);

    for (int i = 0; i < NB_CNT; i++) snrt_reset_perf_counter(i);
    for (int i = 0; i < NB_CNT; i++)
        snrt_start_perf_counter(i, cnt_type[i], snrt_hartid());
    // The enables are posted stores: read one back so they have landed
    // before the DMA turns busy. The `mv` uses the loaded value, so the core
    // waits for the load's response (a load into x0 would not stall it).
    uint32_t en = snrt_perf_counters()->enable[0].value;
    asm volatile("mv %0, %0" : "+r"(en));

    uint32_t t0 = snrt_mcycle();
    if (transpose) {
        for (uint32_t k = 0; k < copies; k++)  // column k -> row k
            snrt_dma_start_2d(dst + k * pitch, src + k * bytes, bytes, bytes,
                              src_pitch, N);
    } else {
        for (uint32_t k = 0; k < copies; k++)
            snrt_dma_start_1d(dst + k * bytes, src + k * bytes, bytes);
    }
    uint32_t t1 = snrt_mcycle();
    snrt_dma_wait_all();
    uint32_t t2 = snrt_mcycle();

    for (int i = 0; i < NB_CNT; i++) snrt_stop_perf_counter(i);

    r->issue = t1 - t0;
    r->done = t2 - t0;
    for (int i = 0; i < NB_CNT; i++) r->cnt[i] = snrt_get_perf_counter(i);
    r->errors = transpose ? check_transpose(t, l1, bytes, copies, pitch)
                          : compare((uint32_t *)dst, (uint32_t *)src, total);
}

// A case's name: "dma l2l1 1x64 B", and a transpose's row pitch after it.
static void label(const dma_case_t *c, const char *dir) {
    printf("dma %s %ux%u B", dir, c->copies, c->bytes);
    if (c->dir == T_L1 || c->dir == T_L2) printf(" p%u", c->pitch);
}

int main() {
    // Both cores find the same L1 buffers (a copy's or A, and T) and result
    // table.
    uint8_t *l1 = (uint8_t *)align_up((uintptr_t)snrt_l1_next(), BEAT);
    uint8_t *t = l1 + MAX_BYTES;
    result_t *results = (result_t *)(t + MAX_BYTES);

    if (snrt_is_dm_core()) {
        for (uint32_t i = 0; i < NB_CASES; i++) {
            const dma_case_t *c = &cases[i];
            // A in L1 for a transpose, also from DRAM: the check reads it
            // there.
            if (c->dir == T_L1 || c->dir == T_L2)
                load(l1, N * c->bytes, c->pitch);
            // The first run fills the instruction cache; the second counts.
            run_case(c, l1, t, &results[i]);
            run_case(c, l1, t, &results[i]);
        }
    }

    snrt_cluster_hw_barrier();

    if (snrt_cluster_core_idx() == 0) {
        uint32_t errors = 0;
        uint32_t mismatches = 0;
        for (uint32_t i = 0; i < NB_CASES; i++) {
            const dma_case_t *c = &cases[i];
            const result_t *r = &results[i];
            const char *dir = c->dir == IDLE       ? "idle"
                              : c->dir == L2_TO_L1 ? "l2l1"
                              : c->dir == L1_TO_L2 ? "l1l2"
                              : c->dir == T_L1     ? "t-l1l1"
                                                   : "t-l2l1";
            label(c, dir);
            printf(
                ": issue %u done %u busy %u r %u w %u ar_stall %u w_stall %u "
                "r_stall %u err %u\n",
                r->issue, r->done, r->cnt[0], r->cnt[1], r->cnt[2], r->cnt[3],
                r->cnt[4], r->cnt[5], r->errors);
            errors += r->errors;
            if (r->cnt[0] != c->rtl_busy || r->cnt[1] != c->rtl_r ||
                r->cnt[2] != c->rtl_w) {
                label(c, dir);
                printf(": busy r w %u %u %u, the RTL's %u %u %u\n", r->cnt[0],
                       r->cnt[1], r->cnt[2], c->rtl_busy, c->rtl_r, c->rtl_w);
                mismatches++;
            }
        }
        printf("Number of errors: %u\n", errors);
        printf("Cases off the RTL's busy, r, w: %u\n", mismatches);
        return errors + mismatches;
    }

    return 0;
}
