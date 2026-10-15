// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// snax-alu's three streamers and the ALU in its four modes (SG4): readers A
// and B and the writer O set up as snax-alu sets them, through snax-alu's
// library, one run per mode (add, sub, mul, xor). A and B are full 64-bit
// words, so sub underflows and mul keeps the low 64 bits of its product, as
// snax_alu_pe.sv does. Each run checks O against the core's own result and
// prints the streamer's counter (977) and the ALU's (982). The same ELF runs
// on snax_cluster's RTL and on SNAX-GVSoC. Returns the error count.

#include "snrt.h"

#include "snax-alu-lib.h"
#include "streamer_csr_addr_map.h"

// Beats per stream, 4 words of 64 bit each, as snax-alu's LOOP_ITER
#define BEATS 25
#define WORDS (4 * BEATS)

static const char *mode_names[] = {"add", "sub", "mul", "xor"};
#define NB_MODES 4

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

// A 64-bit linear congruential generator (Knuth's MMIX constants): fixed
// data with every bit in use
static uint64_t next_word(uint64_t *x) {
    *x = *x * 6364136223846793005ull + 1442695040888963407ull;
    return *x;
}

int main() {
    if (!snrt_is_compute_core()) return 0;

    // As snax-alu: A, B and O one after the other from the start of L1
    uint64_t *a = (uint64_t *)snrt_l1_next();
    uint64_t *b = a + WORDS;
    uint64_t *o = b + WORDS;
    uint64_t x = 1;
    for (uint32_t i = 0; i < WORDS; i++) {
        a[i] = next_word(&x);
        b[i] = next_word(&x);
    }

    uint32_t errors = 0;
    for (uint32_t mode = 0; mode < NB_MODES; mode++) {
        for (uint32_t i = 0; i < WORDS; i++) o[i] = 0;
        // The core's stores are done before the streamer reads the banks
        asm volatile("fence" ::: "memory");

        configure_streamer_a((uint32_t)a, 0, 8, BEATS, 32);
        configure_streamer_b((uint32_t)b, 0, 8, BEATS, 32);
        configure_streamer_o((uint32_t)o, 0, 8, BEATS, 32);
        configure_alu(mode, BEATS);
        start_streamer();
        start_alu();
        while (read_busy_alu()) {
        }
        while (read_busy_streamer()) {
        }

        uint32_t err = 0;
        for (uint32_t i = 0; i < WORDS; i++) {
            if (o[i] != alu_op(mode, a[i], b[i])) err++;
        }
        errors += err;
        printf("snax-stream %s: errors %u, streamer counter %u, alu counter %u\n",
               mode_names[mode], err, csrr_ss(STREAMER_PERFORMANCE_COUNTER_CSR),
               csrr_ss(ALU_RO_PERF_COUNT));
    }
    return errors;
}
