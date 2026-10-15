// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// Streamer timing program for SG3: the same ELFs run on snax_cluster's RTL and
// on SNAX-GVSoC. The compute core sets up snax_alu's two readers, leaves the
// writer's bound at 0, starts the streamer and polls its busy CSR; it prints
// the streamer's counter (977) and the mcycle span.
//
// The ALU is never started, so nothing takes the readers' beats: each lane
// reads at most fifo_depth (8) beats, then the reader is done. The beats stay
// in the reader's queues and keep its credit after the run; the RTL does not
// clear them at start. So each case is its own ELF, chosen with CASE_<name>.

#include "snrt.h"

#include "streamer_csr_addr_map.h"

// One beat: 4 lanes of 64 bit
#define BEAT 32
// Beats per lane: the readers' fifo_depth
#define NB_BEATS 8
// Bytes per bank word and banks: the bank of an address is (addr / 8) % 32
#define BANK_WIDTH 8
#define NB_BANKS 32

typedef struct {
    const char *name;
    uint32_t b_on;        // reader B runs
    uint32_t b_offset;    // B's pointer from A's
    uint32_t a_sstride;   // A's spatial stride (8: one bank per lane)
    uint32_t a_bound;     // A's temporal bound (0: A does not start)
} stream_case_t;

#if defined(CASE_zero_bound)
// Every temporal bound 0: the streamer is busy one cycle, the counter is 0
static const stream_case_t c = {"zero_bound", 0, 0, 8, 0};
#elif defined(CASE_a_alone)
// A alone: 8 beats on banks 0 to 31, no conflict
static const stream_case_t c = {"a_alone", 0, 0, 8, NB_BEATS};
#elif defined(CASE_ab_other_banks)
// A and B, B 16 banks away: every beat of each on other banks
static const stream_case_t c = {"ab_other_banks", 1, 16 * BANK_WIDTH, 8, NB_BEATS};
#elif defined(CASE_ab_same_banks)
// A and B, B a whole multiple of the 32 banks away: lane i of A and of B ask
// for the same bank in the same cycle
static const stream_case_t c = {"ab_same_banks", 1, 4 * NB_BANKS * BANK_WIDTH, 8, NB_BEATS};
#elif defined(CASE_a_stride0)
// A alone with spatial stride 0: the four lanes read the same word, so they
// ask for the same bank
static const stream_case_t c = {"a_stride0", 0, 0, 0, NB_BEATS};
#else
#error "Build with -DCASE_<name>, see the Makefile"
#endif

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

int main() {
    if (!snrt_is_compute_core()) return 0;

    // A on bank 0; the area holds A, B and the writer's unused pointer
    uint32_t a = align_up((uintptr_t)snrt_l1_next(), NB_BANKS * BANK_WIDTH);
    uint32_t b = a + c.b_offset;
    uint32_t o = a + 2048;
    volatile uint64_t *area = (volatile uint64_t *)a;
    for (uint32_t i = 0; i < 4096 / 8; i++) area[i] = i;
    // The core's stores are done before the streamer reads the banks
    asm volatile("fence" ::: "memory");

    // Reader A
    csrw_ss(BASE_PTR_READER_0_LOW, a);
    csrw_ss(BASE_PTR_READER_0_HIGH, 0);
    csrw_ss(S_STRIDE_READER_0_0, c.a_sstride);
    csrw_ss(T_BOUND_READER_0_0, c.a_bound);
    csrw_ss(T_STRIDE_READER_0_0, BEAT);
    // Reader B
    csrw_ss(BASE_PTR_READER_1_LOW, b);
    csrw_ss(BASE_PTR_READER_1_HIGH, 0);
    csrw_ss(S_STRIDE_READER_1_0, 8);
    csrw_ss(T_BOUND_READER_1_0, c.b_on ? NB_BEATS : 0);
    csrw_ss(T_STRIDE_READER_1_0, BEAT);
    // The writer does not start: its temporal bound is 0
    csrw_ss(BASE_PTR_WRITER_0_LOW, o);
    csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
    csrw_ss(S_STRIDE_WRITER_0_0, 8);
    csrw_ss(T_BOUND_WRITER_0_0, 0);
    csrw_ss(T_STRIDE_WRITER_0_0, BEAT);

    uint32_t t0 = snrt_mcycle();
    csrw_ss(STREAMER_START_CSR, 1);
    uint32_t polls = 0;
    while (csrr_ss(STREAMER_BUSY_CSR)) polls++;
    uint32_t t1 = snrt_mcycle();
    uint32_t counter = csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR);

    printf("stream-timing %s: counter %u, polls %u, mcycle %u\n", c.name, counter,
           polls, t1 - t0);
    return 0;
}
