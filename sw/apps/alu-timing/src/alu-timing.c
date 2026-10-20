// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// ALU timing program: the same ELF runs on snax_cluster's RTL and on
// SNAX-GVSoC. Five cases, one after the other, on snax-alu's three streamers
// and the ALU, set up through snax-alu's library. Each prints its errors, the
// streamer's counter (977), the ALU's (982) and the gap between the two
// start writes as the core sees it (mcycle before start_alu minus mcycle
// before start_streamer).
//
// That gap is the core's timing, so each case has one counter that does not
// depend on it, the one to compare:
//   alu_first       977  the ALU waits for the streamer
//   stream_first    982  the ALU starts on full readers
//   out_one_bank    982  as stream_first, every word of O on one bank: the
//                        writer gets one grant a cycle, four a beat, its
//                        queue fills and the ALU stalls on its output
//   len1            both the counter stays 1 with length 1
//   restart_idle    977  a second start before any firing, O = A - B
// Every case consumes all its beats and every run ends, so nothing carries
// over to the next case. Returns the error count.

#include "snrt.h"

#include "snax-alu-lib.h"
#include "streamer_csr_addr_map.h"

// One beat: 4 lanes of 64 bit
#define BEAT 32
#define BEATS 25
#define WORDS (4 * BEATS)
// Bytes per bank word and banks: the bank of an address is (addr / 8) % 32
#define BANK_WIDTH 8
#define NB_BANKS 32
// Cycles stream_first waits for the readers to fill (8 beats, about 10)
#define FILL_WAIT 100

enum order { ALU_FIRST, STREAM_FIRST, RESTART };

typedef struct {
    const char *name;
    enum order order;
    uint32_t beats;       // the streamers' temporal bound and the ALU's length
    uint32_t mode;        // the ALU's mode (the second start's for RESTART)
    uint32_t o_offset;    // O's offset from A
    uint32_t o_sstride;   // O's spatial stride (lane to lane)
    uint32_t o_tstride;   // O's temporal stride (beat to beat)
} alu_case_t;

// O after A and B as in snax-alu, or, for out_one_bank, lane i of beat t at
// 1024 * t + 256 * i: every word on the same bank (25 KiB from A + 2 KiB)
static const alu_case_t cases[] = {
    {"alu_first", ALU_FIRST, BEATS, 0, 1600, 8, BEAT},
    {"stream_first", STREAM_FIRST, BEATS, 0, 1600, 8, BEAT},
    {"out_one_bank", STREAM_FIRST, BEATS, 0, 2048, NB_BANKS * BANK_WIDTH,
     4 * NB_BANKS * BANK_WIDTH},
    {"len1", ALU_FIRST, 1, 0, 1600, 8, BEAT},
    {"restart_idle", RESTART, BEATS, 1, 1600, 8, BEAT},
};
#define NB_CASES (sizeof(cases) / sizeof(cases[0]))

// The ALU's op on one lane (snax_alu_pe.sv)
static uint64_t alu_op(uint32_t mode, uint64_t a, uint64_t b) {
    switch (mode) {
        case 1:
            return a - b;
        case 2:
            return a * b;
        case 3:
            return a ^ b;
        default:
            return a + b;
    }
}

// The 64-bit generator of snax-stream
static uint64_t next_word(uint64_t *x) {
    *x = *x * 6364136223846793005ull + 1442695040888963407ull;
    return *x;
}

static inline uintptr_t align_up(uintptr_t x, uintptr_t a) {
    return (x + a - 1) & ~(a - 1);
}

int main() {
    if (!snrt_is_compute_core()) return 0;

    // A on bank 0, B 800 B after it (bank 4), as snax-alu places them
    uint64_t *a = (uint64_t *)align_up((uintptr_t)snrt_l1_next(), NB_BANKS * BANK_WIDTH);
    uint64_t *b = a + WORDS;
    uint64_t x = 1;
    for (uint32_t i = 0; i < WORDS; i++) {
        a[i] = next_word(&x);
        b[i] = next_word(&x);
    }

    uint32_t errors = 0;
    for (uint32_t c = 0; c < NB_CASES; c++) {
        const alu_case_t *k = &cases[c];
        uint64_t *o = (uint64_t *)((uintptr_t)a + k->o_offset);
        uint32_t words = 4 * k->beats;
        // The span O's lanes cover, cleared
        uint32_t o_span = ((k->beats - 1) * k->o_tstride + 3 * k->o_sstride) / 8 + 1;
        for (uint32_t i = 0; i < o_span; i++) o[i] = 0;
        // The core's stores are done before the streamer reads the banks
        asm volatile("fence" ::: "memory");

        configure_streamer_a((uint32_t)a, 0, 8, k->beats, BEAT);
        configure_streamer_b((uint32_t)b, 0, 8, k->beats, BEAT);
        configure_streamer_o((uint32_t)o, 0, k->o_sstride, k->beats, k->o_tstride);

        uint32_t t_alu, t_stream;
        if (k->order == STREAM_FIRST) {
            configure_alu(k->mode, k->beats);
            t_stream = snrt_mcycle();
            start_streamer();
            while (snrt_mcycle() - t_stream < FILL_WAIT) {
            }
            t_alu = snrt_mcycle();
            start_alu();
        } else {
            if (k->order == RESTART) {
                // A first start that would run for 100 beats, then a second
                // one before any firing: the second's mode and length hold
                configure_alu(0, 100);
                start_alu();
            }
            configure_alu(k->mode, k->beats);
            t_alu = snrt_mcycle();
            start_alu();
            t_stream = snrt_mcycle();
            start_streamer();
        }
        while (read_busy_alu()) {
        }
        while (read_busy_streamer()) {
        }

        uint32_t err = 0;
        for (uint32_t i = 0; i < words; i++) {
            // Element i is lane i % 4 of beat i / 4
            uint32_t at = ((i / 4) * k->o_tstride + (i % 4) * k->o_sstride) / 8;
            if (o[at] != alu_op(k->mode, a[i], b[i])) err++;
        }
        errors += err;
        printf("alu-timing %s: errors %u, streamer counter %u, alu counter %u, start gap %d\n",
               k->name, err, csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR),
               csrr_ss(ALU_RO_PERF_COUNT), (int32_t)(t_alu - t_stream));
    }
    return errors;
}
