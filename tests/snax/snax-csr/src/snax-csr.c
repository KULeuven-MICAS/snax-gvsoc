// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Checks the compute core's SNAX CSRs on the snax_alu target (the streamer
// model and the test datapath in the ALU's place): every read-write CSR reads
// back what was written, through each kind of CSR instruction, the forms that
// must not write (csrrc with x0, csrrsi / csrrci with 0) leave a read-only CSR
// alone, and the read-only CSRs read 0, as nothing is started. Returns the
// number of errors.
//
// The CSR number is part of a CSR instruction, so each check is written out
// once per CSR with the X-macros below.

#include "snrt.h"

// The read-write CSRs of snax/snax_alu_acc.py, without the two start CSRs
// (975, 980): every pattern has bit 0 set, which would start the block.
#define RW_CSRS(X)                                                    \
    X(960) X(961) X(962) X(963) X(964) X(965) X(966) X(967) X(968)    \
    X(969) X(970) X(971) X(972) X(973) X(974) X(978) X(979)
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

// 3. The immediate forms with rd != x0, and csrrc with x0, in inline asm:
//    the encoding.h macros take the immediate or x0 as an operand.
#define CSR_IMM(insn, csr, imm) ({ uint32_t __v; \
    asm volatile(insn " %0, " #csr ", " #imm : "=r"(__v)); __v; })
#define CSRRC_X0(csr) ({ uint32_t __v; \
    asm volatile("csrrc %0, " #csr ", x0" : "=r"(__v)); __v; })

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
    //    writes a 5-bit immediate, and the immediate forms with rd != x0
    //    return the old value. On one CSR is enough: the path does not
    //    depend on the number.
    write_csr(960, 0);
    check("csrrs old", 960, set_csr(960, 0xF0F0), 0);
    check("csrrs new", 960, read_csr(960), 0xF0F0);
    check("csrrc old", 960, clear_csr(960, 0x00F0), 0xF0F0);
    check("csrrc new", 960, read_csr(960), 0xF000);
    write_csr(960, 5);
    check("csrrwi", 960, read_csr(960), 5);
    check("csrrwi old", 960, CSR_IMM("csrrwi", 960, 7), 5);
    check("csrrwi new", 960, read_csr(960), 7);
    check("csrrsi old", 960, CSR_IMM("csrrsi", 960, 8), 7);
    check("csrrsi new", 960, read_csr(960), 15);
    check("csrrci old", 960, CSR_IMM("csrrci", 960, 3), 15);
    check("csrrci new", 960, read_csr(960), 12);
    //    csrrc with x0 and csrrsi / csrrci with 0 only read. On the ALU's
    //    read-only counter 982 (0, nothing ran): a write there stops the run.
    check("csrrc x0", 982, CSRRC_X0(982), 0);
    check("csrrsi 0", 982, CSR_IMM("csrrsi", 982, 0), 0);
    check("csrrci 0", 982, CSR_IMM("csrrci", 982, 0), 0);
    printf("set/clear/imm: %d errors\n", err);

    RO_CSRS(READ_ZERO)
    printf("read-only: %d errors\n", err);

    return err;
}
