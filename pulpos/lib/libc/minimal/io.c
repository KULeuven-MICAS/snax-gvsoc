// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <kernel/init.h>
#include "io.h"






void __pi_libc_init()
{
}



int __pi_libc_start()
{
    return 0;
}



void __pi_libc_stop()
{
}






int puts(const char *s)
{
    char c;
    do
    {
        c = *s;
        if (c == 0)
        {
            __pi_libc_fputc_safe('\n', NULL);
            break;
        }
        __pi_libc_fputc_safe(c, NULL);
        s++;
    } while(1);

    return 0;
}



int fputc(int c, FILE *stream)
{
    __pi_libc_fputc_safe(c, NULL);

    return 0;
}



int putchar(int c)
{
    return fputc(c, stdout);
}



int __pi_libc_prf(int (*func)(int,FILE *), void *dest, const char *format, va_list vargs)
{
    return __pi_libc_prf_safe(func, dest, format, vargs);
}



void exit(int status)
{
    // Stop the OS
    __pi_init_stop(status);
}



void abort()
{
    exit(-1);
}
