// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdarg.h>
#include <stddef.h>

typedef int FILE;

#define stdin  ((FILE *) 1)
#define stdout ((FILE *) 2)
#define stderr ((FILE *) 3)

int puts(const char *s);

int printf(const char *format, ...);

int putchar(int c);

int puts(const char *s);

int sprintf(char *str, const char *fmt, ...) ;

int fputc(int c, FILE *stream);

int vprintf(const char *format, va_list ap);

int snprintf(char *s, size_t len, const char *format, ...);
