// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <kernel/riscv.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum semihosting_operation_numbers {
    /*
    * ARM/openocd semihosting operations.
    * extracted from openocd semihosting_commong.h file
    */
    SEMIHOSTING_ENTER_SVC = 0x17, /* DEPRECATED */

    SEMIHOSTING_SYS_CLOCK = 0x10,
    SEMIHOSTING_SYS_ELAPSED = 0x30,

    SEMIHOSTING_SYS_ERRNO = 0x13,

    SEMIHOSTING_SYS_EXIT = 0x18,
    SEMIHOSTING_SYS_EXIT_EXTENDED = 0x20,
    // stat
    SEMIHOSTING_SYS_FLEN = 0x0C,
    SEMIHOSTING_SYS_GET_CMDLINE = 0x15,
    SEMIHOSTING_SYS_HEAPINFO = 0x16,
    SEMIHOSTING_SYS_ISERROR = 0x08,
    SEMIHOSTING_SYS_ISTTY = 0x09,

    // File operations
    SEMIHOSTING_SYS_OPEN = 0x01,
    SEMIHOSTING_SYS_CLOSE = 0x02,
    SEMIHOSTING_SYS_READ = 0x06,
    SEMIHOSTING_SYS_READC = 0x07,
    SEMIHOSTING_SYS_REMOVE = 0x0E,
    SEMIHOSTING_SYS_RENAME = 0x0F,
    SEMIHOSTING_SYS_SEEK = 0x0A,
    SEMIHOSTING_SYS_WRITE = 0x05,
    SEMIHOSTING_SYS_WRITEC = 0x03,
    // roughly a printf (print a string terminated by '\0')
    SEMIHOSTING_SYS_WRITE0 = 0x04,

    SEMIHOSTING_SYS_SYSTEM = 0x12,
    SEMIHOSTING_SYS_TICKFREQ = 0x31,
    SEMIHOSTING_SYS_TIME = 0x11,
    SEMIHOSTING_SYS_TMPNAM = 0x0D,
};

#define SEMIHOST_EXIT_SUCCESS 0x20026
#define SEMIHOST_EXIT_ERROR   0x20023

/* riscv semihosting standard:
 * IN: a0 holds syscall number
 * IN: a1 holds pointer to arg struct
 * OUT: a0 holds return value (if exists)
 */
static inline long __pi_libc_semihost(long n, long _a1)
{
    register long a0 asm("a0") = n;
    register long a1 asm("a1") = _a1;

    // riscv magic values for semihosting
    asm volatile(".option norvc;\t\n"
                "slli    zero,zero,0x1f\t\n"
                "ebreak\t\n"
                "srai    zero,zero,0x7\t\n"
                ".option rvc;\t\n"
                : "+r"(a0)
                : "r"(a1));

    return a0;
}

static inline void __pi_libc_semihost_write0(const char *print_string)
{
    __pi_libc_semihost(SEMIHOSTING_SYS_WRITE0, (long)print_string);
}

static inline int __pi_libc_semihost_open(const char *name, int mode)
{
    uint_t len = strlen(name);
    uint_t args[3] = {(uint_t)(long)name, (uint_t)mode, len};
    __asm__ __volatile__("" : : : "memory");
    return __pi_libc_semihost(SEMIHOSTING_SYS_OPEN, (long)args);
}

static inline int __pi_libc_semihost_close(int fd)
{
    return __pi_libc_semihost(SEMIHOSTING_SYS_CLOSE, (long)fd);
}

static inline int __pi_libc_semihost_read(int fd, uint8_t *buffer, int len)
{
    uint_t args[3] = {(uint_t)(long)fd, (uint_t)(long)buffer, (uint_t)(long)len};
    __asm__ __volatile__("" : : : "memory");
    return __pi_libc_semihost(SEMIHOSTING_SYS_READ, (long)args);
}

static inline int __pi_libc_semihost_write(int fd, uint8_t *buffer, int len)
{
    uint_t args[3] = {(uint_t)(long)fd, (uint_t)(long)buffer, (uint_t)(long)len};
    __asm__ __volatile__("" : : : "memory");
    return __pi_libc_semihost(SEMIHOSTING_SYS_WRITE, (long)args);
}

static inline int __pi_libc_semihost_seek(int fd, uint_t pos)
{
    uint_t args[2] = {(uint_t)(long)fd, pos};
    __asm__ __volatile__("" : : : "memory");
    return __pi_libc_semihost(SEMIHOSTING_SYS_SEEK, (long)args);
}

static inline int __pi_libc_semihost_flen(int fd)
{
    return __pi_libc_semihost(SEMIHOSTING_SYS_FLEN, (long)fd);
}

static inline int __pi_libc_semihost_exit(int code)
{
    return __pi_libc_semihost(SEMIHOSTING_SYS_EXIT, (long)code);
}
