// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Checks each core's observability CSR, 0x7C5 (snax_cluster's CsrObsRegister,
// snitch.sv): it reads 0 after reset, then holds what each kind of CSR
// instruction writes, all 32 bits. Every core checks its own register and
// returns its errors; the runtime adds them up.

#include "snrt.h"

#define OBS 0x7c5

static int err;

static void check(const char *what, uint32_t got, uint32_t expected) {
    if (got != expected) {
        printf("obs-csr core %u, %s: read 0x%x, expected 0x%x\n",
               snrt_cluster_core_idx(), what, got, expected);
        err++;
    }
}

int main() {
    check("reset", read_csr(0x7c5), 0);

    write_csr(0x7c5, 0xA5A5005Au);
    check("csrw", read_csr(0x7c5), 0xA5A5005Au);

    check("csrrw old", swap_csr(0x7c5, 0x12345678u), 0xA5A5005Au);
    check("csrrw", read_csr(0x7c5), 0x12345678u);

    check("csrrs old", set_csr(0x7c5, 0x80000001u), 0x12345678u);
    check("csrrs", read_csr(0x7c5), 0x92345679u);

    check("csrrc old", clear_csr(0x7c5, 0x02340000u), 0x92345679u);
    check("csrrc", read_csr(0x7c5), 0x90005679u);

    write_csr(0x7c5, 7);  // csrwi
    check("csrwi", read_csr(0x7c5), 7);

    write_csr(0x7c5, 0);
    check("back to 0", read_csr(0x7c5), 0);
    return err;
}
