// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// Streamer timing program: the same ELFs run on snax_cluster's RTL and
// on SNAX-GVSoC. The compute core sets up the streamer's two readers, leaves the
// writer's bound at 0, starts the streamer and polls its busy CSR; it prints
// the streamer's counter (977) and the mcycle span.
//
// The accelerator is never started, so nothing takes the readers' beats:
// each lane reads at most fifo_depth (8) beats, then the reader is done. The beats stay
// in the reader's queues and keep its credit after the run; the RTL does not
// clear them at start. So each case is its own ELF, chosen with CASE_<name>.
//
// prio_queued and idle_restart start with a first run that leaves beats in one reader's
// queues, then the measured run, with no access to the TCDM in between;
// they print the first run's counter too.

#include "snrt.h"

#include "streamer_csr_addr_map.h"

// One beat: 4 lanes of 64 bit
#define BEAT 32
// Beats per lane: the readers' fifo_depth
#define NB_BEATS 8
// Bytes per bank word and banks: the bank of an address is (addr / 8) % 32
#define BANK_WIDTH 8
#define NB_BANKS 32

// One start of the streamer: the readers' pointers (from the area's start)
// and temporal bounds; a bound 0 leaves that reader out
typedef struct {
    uint32_t a_offset;
    uint32_t a_bound;
    uint32_t b_offset;
    uint32_t b_bound;
} stream_run_t;

typedef struct {
    const char *name;
    uint32_t a_sstride;   // A's spatial stride (8: one bank per lane)
    stream_run_t first;   // a run before the measured one; bounds 0: none
    stream_run_t run;     // the measured run
} stream_case_t;

// A whole multiple of the 32 banks: the same banks, lane by lane
#define SAME_BANKS (4 * NB_BANKS * BANK_WIDTH)
#define NO_RUN {0, 0, 0, 0}

#if defined(CASE_zero_bound)
// Every temporal bound 0: the streamer is busy one cycle, the counter is 0
static const stream_case_t c = {"zero_bound", 8, NO_RUN, {0, 0, 0, 0}};
#elif defined(CASE_a_alone)
// A alone: 8 beats on banks 0 to 31, no conflict
static const stream_case_t c = {"a_alone", 8, NO_RUN, {0, NB_BEATS, 0, 0}};
#elif defined(CASE_ab_other_banks)
// A and B, B 16 banks away: every beat of each on other banks
static const stream_case_t c = {"ab_other_banks", 8, NO_RUN,
                                {0, NB_BEATS, 16 * BANK_WIDTH, NB_BEATS}};
#elif defined(CASE_ab_same_banks)
// A and B on the same banks: lane i of A and of B ask for the same bank in the
// same cycle
static const stream_case_t c = {"ab_same_banks", 8, NO_RUN,
                                {0, NB_BEATS, SAME_BANKS, NB_BEATS}};
#elif defined(CASE_a_stride0)
// A alone with spatial stride 0: the four lanes read the same word, so they
// ask for the same bank
static const stream_case_t c = {"a_stride0", 0, NO_RUN, {0, NB_BEATS, 0, 0}};
#elif defined(CASE_prio_queued)
// Priority: A alone leaves 4 beats in its queues; then A (4 beats) and B
// (1 beat) on banks 0 to 3 at once. On the sparse interconnect B asks with
// priority 1 (queue count 0) and A with 0 (count 4)
static const stream_case_t c = {"prio_queued", 8, {0, 4, 0, 0},
                                {SAME_BANKS, 4, 2 * SAME_BANKS, 1}};
#elif defined(CASE_idle_restart)
// Idle restart: B alone takes banks 0 to 3 (one beat, left in its
// queues); after idle cycles, A (1 beat) and B (4 beats) on banks 0 to 3 at
// once, both with priority 1. The sparse pointer restarts, the plain one
// keeps B's turn
static const stream_case_t c = {"idle_restart", 8, {0, 0, SAME_BANKS, 1},
                                {0, 1, 2 * SAME_BANKS, 4}};
#else
#error "Build with -DCASE_<name>, see the Makefile"
#endif

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

// Sets up the readers for one run, starts the streamer and polls its busy
// CSR; returns the counter. Only CSRs: no access to the TCDM.
static inline uint32_t stream(uint32_t area, const stream_run_t *r, uint32_t *polls,
                              uint32_t *span) {
    // Reader A
    csrw_ss(BASE_PTR_READER_0_LOW, area + r->a_offset);
    csrw_ss(BASE_PTR_READER_0_HIGH, 0);
    csrw_ss(S_STRIDE_READER_0_0, c.a_sstride);
    csrw_ss(T_BOUND_READER_0_0, r->a_bound);
    csrw_ss(T_STRIDE_READER_0_0, BEAT);
    // Reader B
    csrw_ss(BASE_PTR_READER_1_LOW, area + r->b_offset);
    csrw_ss(BASE_PTR_READER_1_HIGH, 0);
    csrw_ss(S_STRIDE_READER_1_0, 8);
    csrw_ss(T_BOUND_READER_1_0, r->b_bound);
    csrw_ss(T_STRIDE_READER_1_0, BEAT);
    // The writer does not start: its temporal bound is 0
    csrw_ss(BASE_PTR_WRITER_0_LOW, area + 3072);
    csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
    csrw_ss(S_STRIDE_WRITER_0_0, 8);
    csrw_ss(T_BOUND_WRITER_0_0, 0);
    csrw_ss(T_STRIDE_WRITER_0_0, BEAT);

    uint32_t t0 = snrt_mcycle();
    csrw_ss(STREAMER_START_CSR, 1);
    uint32_t n = 0;
    while (csrr_ss(STREAMER_BUSY_CSR)) n++;
    *span = snrt_mcycle() - t0;
    *polls = n;
    return csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR);
}

int main() {
    if (!snrt_is_compute_core()) return 0;

    // The area holds A, B and the writer's unused pointer, from bank 0
    uint32_t a = align_up((uintptr_t)snrt_l1_next(), NB_BANKS * BANK_WIDTH);
    volatile uint64_t *area = (volatile uint64_t *)a;
    for (uint32_t i = 0; i < 4096 / 8; i++) area[i] = i;
    // The core's stores are done before the streamer reads the banks
    asm volatile("fence" ::: "memory");

    uint32_t polls, span, first = 0;
    int has_first = c.first.a_bound || c.first.b_bound;
    if (has_first) first = stream(a, &c.first, &polls, &span);
    uint32_t counter = stream(a, &c.run, &polls, &span);

    if (has_first)
        printf("stream-timing %s: first run counter %u, counter %u, polls %u, mcycle %u\n",
               c.name, first, counter, polls, span);
    else
        printf("stream-timing %s: counter %u, polls %u, mcycle %u\n", c.name, counter,
               polls, span);
    return 0;
}
