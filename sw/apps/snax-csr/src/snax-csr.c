// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Checks the compute core's SNAX CSRs on snax_hjson with forge/vecadd/'s
// cluster file (the streamer and the shell): every read-write CSR reads
// back what was written, through each kind of CSR instruction, the forms that
// must not write (csrrc with x0, csrrsi / csrrci with 0) leave a read-only CSR
// alone, and the read-only CSRs read 0, as nothing is started. Returns the
// number of errors.
//
// The CSR number is part of a CSR instruction, so each check is written out
// once per CSR with the X-macros below. encoding.h's CSR macros take the
// number as written, so a name from the headers reaches them through one more
// macro, which expands it.

#include "snrt.h"

#include "acc_csr.h"
#include "streamer_csr_addr_map.h"

// The read-write CSRs of the streamer and the shell, without the two start
// CSRs (STREAMER_START_CSR, ACC_RW_START): every pattern has bit 0 set, which
// would start the block.
#define RW_CSRS(X)                                                            \
    X(BASE_PTR_READER_0_LOW) X(BASE_PTR_READER_0_HIGH) X(S_STRIDE_READER_0_0) \
    X(T_BOUND_READER_0_0) X(T_STRIDE_READER_0_0)                              \
    X(BASE_PTR_READER_1_LOW) X(BASE_PTR_READER_1_HIGH) X(S_STRIDE_READER_1_0) \
    X(T_BOUND_READER_1_0) X(T_STRIDE_READER_1_0)                              \
    X(BASE_PTR_WRITER_0_LOW) X(BASE_PTR_WRITER_0_HIGH) X(S_STRIDE_WRITER_0_0) \
    X(T_BOUND_WRITER_0_0) X(T_STRIDE_WRITER_0_0) X(ACC_RW_JOBS)
#define RO_CSRS(X)                                                \
    X(STREAMER_BUSY_CSR) X(STREAMER_PERFORMANCE_COUNTER_CSR)      \
    X(ACC_RO_STATUS) X(ACC_RO_COUNTER)
// Part 3's CSRs: a read-write one, and the group's read-only COUNTER
#define ONE_RW BASE_PTR_READER_0_LOW
#define ONE_RO ACC_RO_COUNTER

#define STR(x) #x
#define WRITE(csr, v) write_csr(csr, v)
#define READ(csr) read_csr(csr)
#define SET(csr, v) set_csr(csr, v)
#define CLEAR(csr, v) clear_csr(csr, v)

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
    asm volatile(insn " %0, " STR(csr) ", " #imm : "=r"(__v)); __v; })
#define CSRRC_X0(csr) ({ uint32_t __v; \
    asm volatile("csrrc %0, " STR(csr) ", x0" : "=r"(__v)); __v; })

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
    WRITE(ONE_RW, 0);
    check("csrrs old", ONE_RW, SET(ONE_RW, 0xF0F0), 0);
    check("csrrs new", ONE_RW, READ(ONE_RW), 0xF0F0);
    check("csrrc old", ONE_RW, CLEAR(ONE_RW, 0x00F0), 0xF0F0);
    check("csrrc new", ONE_RW, READ(ONE_RW), 0xF000);
    WRITE(ONE_RW, 5);
    check("csrrwi", ONE_RW, READ(ONE_RW), 5);
    check("csrrwi old", ONE_RW, CSR_IMM("csrrwi", ONE_RW, 7), 5);
    check("csrrwi new", ONE_RW, READ(ONE_RW), 7);
    check("csrrsi old", ONE_RW, CSR_IMM("csrrsi", ONE_RW, 8), 7);
    check("csrrsi new", ONE_RW, READ(ONE_RW), 15);
    check("csrrci old", ONE_RW, CSR_IMM("csrrci", ONE_RW, 3), 15);
    check("csrrci new", ONE_RW, READ(ONE_RW), 12);
    //    csrrc with x0 and csrrsi / csrrci with 0 only read. On the shell's
    //    read-only counter (0, nothing ran): a write there stops the run.
    check("csrrc x0", ONE_RO, CSRRC_X0(ONE_RO), 0);
    check("csrrsi 0", ONE_RO, CSR_IMM("csrrsi", ONE_RO, 0), 0);
    check("csrrci 0", ONE_RO, CSR_IMM("csrrci", ONE_RO, 0), 0);
    printf("set/clear/imm: %d errors\n", err);

    RO_CSRS(READ_ZERO)
    printf("read-only: %d errors\n", err);

    return err;
}
