// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdint.h>

// HTIF host interface. The host locates the tohost/fromhost variables through
// their ELF symbols and uses them to communicate with the target: the target
// posts commands to tohost (bit 0 set: exit request, bit 0 clear: pointer to
// a syscall descriptor) and the host acknowledges through fromhost.
volatile uint64_t tohost __attribute__((aligned(64)));
volatile uint64_t fromhost __attribute__((aligned(64)));

// Syscall descriptor: syscall number followed by up to 7 arguments
static volatile uint64_t __pi_htif_syscall_args[8] __attribute__((aligned(64)));

static void __pi_htif_send(uint32_t value)
{
    // Wait until the host has consumed the previous command. Only the low
    // 32 bits of tohost are ever written to a non-zero value, so that the
    // host can not see the two-word store half-written.
    while (tohost != 0)
    {
    }

    tohost = value;
}

static void __pi_htif_wait_ack()
{
    while (fromhost == 0)
    {
    }

    fromhost = 0;
}

void __pi_htif_write(int fd, uint8_t *buffer, int len)
{
    __pi_htif_syscall_args[0] = 64; // riscv SYS_write
    __pi_htif_syscall_args[1] = fd;
    __pi_htif_syscall_args[2] = (uint32_t)buffer;
    __pi_htif_syscall_args[3] = len;

    __asm__ volatile ("" : : : "memory");

    __pi_htif_send((uint32_t)__pi_htif_syscall_args);
    __pi_htif_wait_ack();
}

void __pi_htif_exit(int status)
{
    __pi_htif_send((status << 1) | 1);

    while (1)
    {
        __asm__ volatile ("wfi");
    }
}
