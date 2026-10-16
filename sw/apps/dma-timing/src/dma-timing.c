// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// DMA timing program for SG2: the same ELF runs on snax_cluster's RTL and on
// SNAX-GVSoC. The DMA core copies between DRAM (L2) and L1 at a few sizes and
// measures each case with mcycle and the cluster's DMA perf counters; the
// compute core prints one line per case after the barrier, checks busy, r
// and w against the RTL's and returns the errors and the cases off them.

#include "snrt.h"

#include "data.h"

// One DMA beat (512 bit).
#define BEAT 64

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

enum dir { IDLE, L2_TO_L1, L1_TO_L2 };

typedef struct {
    enum dir dir;
    uint32_t copies;  // back-to-back copies, each `bytes` long, placed
    uint32_t bytes;   // one after the other
    // The RTL's busy, r and w (SG2 step 3 at b2672f8, the same at 9fbf35d in
    // SG7 round 4): they do not depend on the core (D123), so any other value
    // is the DMA's own timing moving
    uint32_t rtl_busy, rtl_r, rtl_w;
} dma_case_t;

static const dma_case_t cases[] = {
    {IDLE, 0, 0, 0, 0, 0},
    {L2_TO_L1, 1, 64, 14, 1, 1},
    {L2_TO_L1, 1, 256, 17, 4, 4},
    {L2_TO_L1, 1, 800, 26, 13, 13},
    {L2_TO_L1, 1, 4096, 77, 64, 64},
    {L2_TO_L1, 1, 8192, 141, 128, 128},
    {L2_TO_L1, 2, 800, 39, 26, 26},
    {L2_TO_L1, 4, 800, 65, 52, 52},
    {L1_TO_L2, 1, 800, 20, 13, 13},
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

static void run_case(const dma_case_t *c, uint8_t *l1, result_t *r) {
    // Read the case before the first mark: `cases` is in DRAM, and
    // snrt_mcycle's memory clobber would make the compiler reload it inside
    // the measured window.
    const uint32_t copies = c->copies;
    const uint32_t bytes = c->bytes;
    const uint32_t total = copies * bytes;
    uint8_t *src = c->dir == L1_TO_L2 ? l1 : (uint8_t *)src_l2;
    uint8_t *dst = c->dir == L1_TO_L2 ? (uint8_t *)dst_l2 : l1;

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
    for (uint32_t k = 0; k < copies; k++)
        snrt_dma_start_1d(dst + k * bytes, src + k * bytes, bytes);
    uint32_t t1 = snrt_mcycle();
    snrt_dma_wait_all();
    uint32_t t2 = snrt_mcycle();

    for (int i = 0; i < NB_CNT; i++) snrt_stop_perf_counter(i);

    r->issue = t1 - t0;
    r->done = t2 - t0;
    for (int i = 0; i < NB_CNT; i++) r->cnt[i] = snrt_get_perf_counter(i);
    r->errors = compare((uint32_t *)dst, (uint32_t *)src, total);
}

int main() {
    // Both cores find the same L1 buffer and result table.
    uint8_t *l1 = (uint8_t *)align_up((uintptr_t)snrt_l1_next(), BEAT);
    result_t *results = (result_t *)(l1 + SRC_BYTES);

    if (snrt_is_dm_core()) {
        for (uint32_t i = 0; i < NB_CASES; i++) {
            // The first run fills the instruction cache; the second counts.
            run_case(&cases[i], l1, &results[i]);
            run_case(&cases[i], l1, &results[i]);
        }
    }

    snrt_cluster_hw_barrier();

    if (snrt_is_compute_core()) {
        uint32_t errors = 0;
        uint32_t mismatches = 0;
        for (uint32_t i = 0; i < NB_CASES; i++) {
            const dma_case_t *c = &cases[i];
            const result_t *r = &results[i];
            const char *dir = c->dir == IDLE       ? "idle"
                              : c->dir == L2_TO_L1 ? "l2l1"
                                                   : "l1l2";
            printf(
                "dma %s %ux%u B: issue %u done %u busy %u r %u w %u "
                "ar_stall %u w_stall %u r_stall %u err %u\n",
                dir, c->copies, c->bytes, r->issue, r->done, r->cnt[0],
                r->cnt[1], r->cnt[2], r->cnt[3], r->cnt[4], r->cnt[5],
                r->errors);
            errors += r->errors;
            if (r->cnt[0] != c->rtl_busy || r->cnt[1] != c->rtl_r ||
                r->cnt[2] != c->rtl_w) {
                printf("dma %s %ux%u B: busy r w %u %u %u, the RTL's %u %u %u\n",
                       dir, c->copies, c->bytes, r->cnt[0], r->cnt[1],
                       r->cnt[2], c->rtl_busy, c->rtl_r, c->rtl_w);
                mismatches++;
            }
        }
        printf("Number of errors: %u\n", errors);
        printf("Cases off the RTL's busy, r, w: %u\n", mismatches);
        return errors + mismatches;
    }

    return 0;
}
