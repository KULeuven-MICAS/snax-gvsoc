// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>
#include <kernel/riscv.h>

#define PI_LIBC_PUTC_BUFFER_SIZE 128

#ifdef CONFIG_SPATZ_HTIF

// HTIF-based host interaction, used on platforms where semihosting is not
// available, like RTL simulations, where the binary is loaded through the
// RISC-V frontend server (fesvr)

void __pi_htif_write(int fd, uint8_t *buffer, int len);
void __pi_htif_exit(int status);

static inline void __pi_init_platform_exit(int status)
{
    __pi_htif_exit(status);
    while(1);
}

static inline void __pi_libc_write(int fd, uint8_t *buffer, int len)
{
    __pi_htif_write(fd, buffer, len);
}

#else

#include <kernel/semihost.h>

static inline void __pi_init_platform_exit(int status)
{
    __pi_libc_semihost_exit(status == 0 ? SEMIHOST_EXIT_SUCCESS : SEMIHOST_EXIT_ERROR);
    while(1);
}

static inline void __pi_libc_write(int fd, uint8_t *buffer, int len)
{
    __pi_libc_semihost_write(fd, buffer, len);
}

#endif


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
