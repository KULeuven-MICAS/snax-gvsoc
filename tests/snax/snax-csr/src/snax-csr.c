// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Checks the compute core's SNAX CSRs on the snax_alu target's stub: every
// read-write CSR reads back what was written, through each kind of CSR
// instruction, and the read-only CSRs read 0. Returns the number of errors.
//
// The CSR number is part of a CSR instruction, so each check is written out
// once per CSR with the X-macros below.

#include "snrt.h"

// The stub's CSRs, as snax/snax_alu.py lists them
#define RW_CSRS(X)                                                    \
    X(960) X(961) X(962) X(963) X(964) X(965) X(966) X(967) X(968)    \
    X(969) X(970) X(971) X(972) X(973) X(974) X(975) X(978) X(979)    \
    X(980)
#define RO_CSRS(X) X(976) X(977) X(981) X(982)

// A value that differs per CSR and has bits set in both halves
#define PATTERN(csr) (0x5A000000u | ((uint32_t)(csr) << 12) | (csr))

static int err;

static void check(const char *what, int csr, uint32_t got, uint32_t expected) {
    if (got != expected) {
        printf("%s, CSR %d: read 0x%x, expected 0x%x\n", what, csr, got,
               expected);
        err++;
    }
}

// 1. csrw (csrrw with rd = x0) to all, then csrr (csrrs with rs1 = x0) of
//    all: one CSR's write landing on another shows up here.
#define WRITE_PATTERN(csr) write_csr(csr, PATTERN(csr));
#define READ_PATTERN(csr) check("csrw/csrr", csr, read_csr(csr), PATTERN(csr));

// 2. csrrw with rd != x0: returns the old value, then holds the new one
#define SWAP_INVERSE(csr) \
    check("csrrw old", csr, swap_csr(csr, ~PATTERN(csr)), PATTERN(csr));
#define READ_INVERSE(csr) check("csrrw new", csr, read_csr(csr), ~PATTERN(csr));

// 4. The read-only CSRs read 0 (busy and performance counters)
#define READ_ZERO(csr) check("read-only", csr, read_csr(csr), 0);

int main() {
    if (!snrt_is_compute_core()) return 0;

    RW_CSRS(WRITE_PATTERN)
    RW_CSRS(READ_PATTERN)
    printf("csrw/csrr: %d errors\n", err);

    RW_CSRS(SWAP_INVERSE)
    RW_CSRS(READ_INVERSE)
    printf("csrrw: %d errors\n", err);

    // 3. csrrs and csrrc set and clear bits (read, then write), csrrwi
    //    writes a 5-bit immediate. On one CSR is enough: the path does not
    //    depend on the number.
    write_csr(960, 0);
    check("csrrs old", 960, set_csr(960, 0xF0F0), 0);
    check("csrrs new", 960, read_csr(960), 0xF0F0);
    check("csrrc old", 960, clear_csr(960, 0x00F0), 0xF0F0);
    check("csrrc new", 960, read_csr(960), 0xF000);
    write_csr(960, 5);
    check("csrrwi", 960, read_csr(960), 5);
    printf("csrrs/csrrc/csrrwi: %d errors\n", err);

    RO_CSRS(READ_ZERO)
    printf("read-only: %d errors\n", err);

    return err;
}
