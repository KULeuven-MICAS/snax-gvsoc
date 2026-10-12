// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <kernel/riscv.h>
#include <stdint.h>

#define PI_LIBC_PUTC_BUFFER_SIZE 128

// MMIO base shared by GVSoC (gvsoc/pulp/pulp/ri5ky/ri5ky_mmio.cpp) and the
// Verilator testbench (hw/ri5ky_gwt/gv_tb/mmio.sv). Same layout as the
// acu_core_v2 testbench so the same hello binary runs on both.
#define RI5KY_TB_MMIO_PUTCHAR (*(volatile uint32_t *)0x10000000)
#define RI5KY_TB_MMIO_EXIT    (*(volatile uint32_t *)0x10000004)

static inline void __pi_init_platform_exit(int status)
{
    RI5KY_TB_MMIO_EXIT = (uint32_t)status;
    while(1);
}

static inline void __pi_libc_write(int fd, uint8_t *buffer, int len)
{
    (void)fd;
    for (int i = 0; i < len; i++)
    {
        RI5KY_TB_MMIO_PUTCHAR = buffer[i];
    }
}


extern unsigned char __pi_irq_vector_base;

static inline uint_t __pi_linker_irq_vector_base()
{
    return (long)&__pi_irq_vector_base;
}


extern unsigned char __pi_fast_irq_vector_base;

static inline uint_t __pi_linker_fast_irq_vector_base()
{
    return (long)&__pi_fast_irq_vector_base;
}
