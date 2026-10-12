// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stddef.h>

void *memset(void *s, int c, size_t n);

void *memcpy(void *dst0, const void *src0, size_t len0);

int strcmp(const char *s1, const char *s2);

int strncmp(const char *s1, const char *s2, size_t n);

extern char  *strchr(const char *s, int c);

size_t strcspn( const char * s1, const char * s2 );

size_t strspn( const char * s1, const char * s2 );

extern void  *memmove(void *d, const void *s, size_t n);
int memcmp(const void *m1, const void *m2, size_t n);

extern char  *strcpy(char *d, const char *s);
extern char *strcat(char *dest, const char *src);

size_t strlen(const char *str);
