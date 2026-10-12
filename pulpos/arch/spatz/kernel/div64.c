// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// 64-bit division and shift helpers, replacing the libgcc ones. The
// toolchain has no C-less multilib, so the libgcc objects contain compressed
// instructions which are not supported by the RTL core. These
// implementations get compiled with the target march instead.
//
// Only constant-amount 64-bit shifts are used here since variable-amount
// ones would be turned into calls to the very functions being implemented.

#include <stdint.h>

uint64_t __lshrdi3(uint64_t value, int shift)
{
    uint32_t hi = value >> 32;
    uint32_t lo = value;

    if (shift >= 32)
    {
        lo = hi >> (shift - 32);
        hi = 0;
    }
    else if (shift != 0)
    {
        lo = (lo >> shift) | (hi << (32 - shift));
        hi = hi >> shift;
    }

    return ((uint64_t)hi << 32) | lo;
}

uint64_t __ashldi3(uint64_t value, int shift)
{
    uint32_t hi = value >> 32;
    uint32_t lo = value;

    if (shift >= 32)
    {
        hi = lo << (shift - 32);
        lo = 0;
    }
    else if (shift != 0)
    {
        hi = (hi << shift) | (lo >> (32 - shift));
        lo = lo << shift;
    }

    return ((uint64_t)hi << 32) | lo;
}

int64_t __ashrdi3(int64_t value, int shift)
{
    int32_t hi = value >> 32;
    uint32_t lo = value;

    if (shift >= 32)
    {
        lo = hi >> (shift - 32);
        hi = hi >> 31;
    }
    else if (shift != 0)
    {
        lo = (lo >> shift) | ((uint32_t)hi << (32 - shift));
        hi = hi >> shift;
    }

    return ((int64_t)hi << 32) | lo;
}

static uint64_t __pi_udiv64(uint64_t num, uint64_t den, uint64_t *rem_out)
{
    uint64_t quot = 0;
    uint64_t rem = 0;

    if (den != 0)
    {
        for (int i = 0; i < 64; i++)
        {
            rem = (rem << 1) | (num >> 63);
            num = num << 1;
            quot = quot << 1;
            if (rem >= den)
            {
                rem -= den;
                quot |= 1;
            }
        }
    }

    if (rem_out)
    {
        *rem_out = rem;
    }

    return quot;
}

uint64_t __udivdi3(uint64_t num, uint64_t den)
{
    return __pi_udiv64(num, den, 0);
}

uint64_t __umoddi3(uint64_t num, uint64_t den)
{
    uint64_t rem;
    __pi_udiv64(num, den, &rem);
    return rem;
}

int64_t __divdi3(int64_t num, int64_t den)
{
    int neg = (num < 0) != (den < 0);
    uint64_t unum = num < 0 ? -(uint64_t)num : (uint64_t)num;
    uint64_t uden = den < 0 ? -(uint64_t)den : (uint64_t)den;
    uint64_t quot = __pi_udiv64(unum, uden, 0);
    return neg ? -(int64_t)quot : (int64_t)quot;
}

int64_t __moddi3(int64_t num, int64_t den)
{
    uint64_t unum = num < 0 ? -(uint64_t)num : (uint64_t)num;
    uint64_t uden = den < 0 ? -(uint64_t)den : (uint64_t)den;
    uint64_t rem;
    __pi_udiv64(unum, uden, &rem);
    return num < 0 ? -(int64_t)rem : (int64_t)rem;
}
