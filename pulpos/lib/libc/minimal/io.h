// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdio.h>

// Dump a character to stdout in a safe multi-core way
int __pi_libc_fputc_safe(int c, FILE *stream);

// Unsafe printf. Needs to be protected against multi-core race conditions by the caller
int __pi_libc_prf(int (*func)(int,FILE *), void *dest, const char *format, va_list vargs);

// printf to stdout in a safe multi-core way
int __pi_libc_prf_safe(int (*func)(int,FILE *), void *dest, const char *format, va_list vargs);
