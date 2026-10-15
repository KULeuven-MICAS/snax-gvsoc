// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The cores' TCDM accesses through the interconnect (SG7 round 3): the same
// ELFs run on snax_cluster's RTL and on SNAX-GVSoC. One ELF per case, chosen
// with CASE_<name>; each prints the value it compares, chosen not to depend
// on the core's timing (D123; core_vs_reader's depends on its instruction
// fetch, see the README).
//
//   subword          the compute core's stores and loads of bytes, halves,
//                    words and doublewords (two words on rv32ima), an
//                    amoadd.w and an LR/SC pair, all on L1, checked; returns
//                    the error count
//   core_vs_reader   readers A and B, 2 beats each, every lane on bank 0;
//                    the core loads from bank 16, then from bank 0 while they
//                    stream; prints the streamer's counter (977)
//   after_stores     the core's stores to the area leave banks 0 to 3 to the
//                    core; then A (1 beat) and B (4 beats) on those banks;
//                    prints 977
//
// The streamer cases leave the ALU off, as stream-timing does; between the
// core's stores and the start write there are only CSR instructions.

#include "snrt.h"

#include "streamer_csr_addr_map.h"

// Bytes per bank word and banks: the bank of an address is (addr / 8) % 32
#define BANK_WIDTH 8
#define NB_BANKS 32
// One bank row: the same bank 256 B further
#define ROW (NB_BANKS * BANK_WIDTH)
// The area the core stores to first, from bank 0
#define AREA_BYTES 8192

#define STR_(x) #x
#define STR(x) STR_(x)

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

// The area holds A, B, the writer's unused pointer and the core's words
static uint32_t area_init(void) {
    uint32_t a = align_up((uintptr_t)snrt_l1_next(), ROW);
    volatile uint64_t *area = (volatile uint64_t *)a;
    for (uint32_t i = 0; i < AREA_BYTES / 8; i++) area[i] = i;
    asm volatile("fence" ::: "memory");
    return a;
}

#if defined(CASE_subword)

#define CHECK(group, cond) \
    do {                   \
        if (!(cond)) group++; \
    } while (0)

int main() {
    if (!snrt_is_compute_core()) return 0;

    uint32_t a = area_init();
    uint32_t bytes = 0, halves = 0, words = 0, dwords = 0, amo = 0, lrsc = 0;

    // Bytes: one bank word written byte by byte, read back as bytes, words
    // and a signed byte
    volatile uint8_t *b = (volatile uint8_t *)(a + 0);
    for (int i = 0; i < 8; i++) b[i] = 0x10 + i;
    b[3] = 0x83;
    volatile uint32_t *bw = (volatile uint32_t *)b;
    CHECK(bytes, bw[0] == 0x83121110);
    CHECK(bytes, bw[1] == 0x17161514);
    CHECK(bytes, b[6] == 0x16);
    CHECK(bytes, ((volatile int8_t *)b)[3] == -125);

    // Halves: a word written as halves, read back as halves (signed and
    // not) and as a word
    volatile uint16_t *h = (volatile uint16_t *)(a + 8);
    for (int i = 0; i < 4; i++) h[i] = 0xa000 + i;
    volatile uint32_t *hw = (volatile uint32_t *)h;
    CHECK(halves, hw[0] == 0xa001a000);
    CHECK(halves, hw[1] == 0xa003a002);
    CHECK(halves, h[2] == 0xa002);
    CHECK(halves, ((volatile int16_t *)h)[1] == (int16_t)0xa001);

    // Words: written as words, read back as words, halves and bytes
    volatile uint32_t *w = (volatile uint32_t *)(a + 16);
    w[0] = 0x01234567;
    w[1] = 0x89abcdef;
    CHECK(words, w[1] == 0x89abcdef);
    CHECK(words, ((volatile uint16_t *)w)[1] == 0x0123);
    CHECK(words, ((volatile uint8_t *)w)[4] == 0xef);

    // Doublewords: rv32ima has no 8-byte access, so two words each way
    volatile uint64_t *d = (volatile uint64_t *)(a + 24);
    d[0] = 0x0011223344556677ull;
    CHECK(dwords, d[0] == 0x0011223344556677ull);
    CHECK(dwords, ((volatile uint32_t *)d)[1] == 0x00112233);

    // amoadd.w: the old value back, the sum in memory
    volatile uint32_t *x = (volatile uint32_t *)(a + 32);
    *x = 100;
    uint32_t old = __atomic_fetch_add(x, 23, __ATOMIC_RELAXED);
    CHECK(amo, old == 100);
    CHECK(amo, *x == 123);

    // LR/SC on one word: the reservation holds, so the SC writes and gives 0
    volatile uint32_t *y = (volatile uint32_t *)(a + 40);
    *y = 7;
    uint32_t loaded, sc;
    asm volatile(
        "lr.w %[loaded], (%[y])\n\t"
        "sc.w %[sc], %[val], (%[y])"
        : [loaded] "=&r"(loaded), [sc] "=&r"(sc)
        : [y] "r"(y), [val] "r"(9)
        : "memory");
    CHECK(lrsc, loaded == 7);
    CHECK(lrsc, sc == 0);
    CHECK(lrsc, *y == 9);

    uint32_t errors = bytes + halves + words + dwords + amo + lrsc;
    printf(
        "core-tcdm subword: errors %u (bytes %u, halves %u, words %u, "
        "doublewords %u, amoadd %u, lr/sc %u), sc %u\n",
        errors, bytes, halves, words, dwords, amo, lrsc, sc);
    return errors;
}

#else

// One start of the streamer: the readers' pointers (from the area's start),
// spatial and temporal strides and temporal bounds; the writer stays off
typedef struct {
    uint32_t ptr, sstride, bound, tstride;
} mover_t;

#if defined(CASE_core_vs_reader)
// Every lane of A and B on bank 0, 2 beats each: 16 requests, each asking
// with priority 1 on the sparse interconnect (queue counts 0 and 1)
static const char *name = "core_vs_reader";
static const mover_t ra = {0, ROW, 2, 4 * ROW};
static const mover_t rb = {0x1000, ROW, 2, 4 * ROW};
// The core's loads after the start write: first bank 16 (so its load on
// bank 0 comes after the readers' first requests), then bank 0
#define CORE_LOADS 1
#define OTHER_BANK_WORD 0x80
#define BANK0_WORD 0x1800
#elif defined(CASE_after_stores)
// A (1 beat) and B (4 beats) on banks 0 to 3, last written by the core
static const char *name = "after_stores";
static const mover_t ra = {0, 8, 1, 32};
static const mover_t rb = {0x800, 8, 4, 32};
#define CORE_LOADS 0
#else
#error "Build with -DCASE_<name>, see the Makefile"
#endif

int main() {
    if (!snrt_is_compute_core()) return 0;

    uint32_t a = area_init();

    csrw_ss(BASE_PTR_READER_0_LOW, a + ra.ptr);
    csrw_ss(BASE_PTR_READER_0_HIGH, 0);
    csrw_ss(S_STRIDE_READER_0_0, ra.sstride);
    csrw_ss(T_BOUND_READER_0_0, ra.bound);
    csrw_ss(T_STRIDE_READER_0_0, ra.tstride);
    csrw_ss(BASE_PTR_READER_1_LOW, a + rb.ptr);
    csrw_ss(BASE_PTR_READER_1_HIGH, 0);
    csrw_ss(S_STRIDE_READER_1_0, rb.sstride);
    csrw_ss(T_BOUND_READER_1_0, rb.bound);
    csrw_ss(T_STRIDE_READER_1_0, rb.tstride);
    csrw_ss(BASE_PTR_WRITER_0_LOW, a + 0xc00);
    csrw_ss(BASE_PTR_WRITER_0_HIGH, 0);
    csrw_ss(S_STRIDE_WRITER_0_0, 8);
    csrw_ss(T_BOUND_WRITER_0_0, 0);
    csrw_ss(T_STRIDE_WRITER_0_0, 32);

#if CORE_LOADS
    // The start write and the core's two loads, in this order
    uint32_t other, bank0;
    asm volatile(
        "csrw " STR(STREAMER_START_CSR) ", %[one]\n\t"
        "lw %[other], 0(%[p_other])\n\t"
        "lw %[bank0], 0(%[p_bank0])"
        : [other] "=&r"(other), [bank0] "=&r"(bank0)
        : [one] "r"(1), [p_other] "r"(a + OTHER_BANK_WORD),
          [p_bank0] "r"(a + BANK0_WORD)
        : "memory");
#else
    csrw_ss(STREAMER_START_CSR, 1);
#endif
    uint32_t polls = 0;
    while (csrr_ss(STREAMER_BUSY_CSR)) polls++;
    uint32_t counter = csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR);

#if CORE_LOADS
    printf("core-tcdm %s: counter %u, polls %u, loaded %u %u\n", name, counter, polls,
           other, bank0);
#else
    printf("core-tcdm %s: counter %u, polls %u\n", name, counter, polls);
#endif
    return 0;
}

#endif
