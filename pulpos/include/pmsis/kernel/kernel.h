// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once


#ifndef LANGUAGE_ASSEMBLY
typedef struct pi_device_s pi_device_t;
#endif

#define ALWAYS_INLINE static inline __attribute__((always_inline))

// This macro can be used to include a chip-dependent file for the current chip
#define  PI_CHIP_INC(chip_name,file) __PI_OS_CHIP_INC(arch/chip_name/file)
#define  __PI_OS_CHIP_INC(x) #x

#ifndef likely
#define likely(x) __builtin_expect(x, 1)
#endif

#ifndef unlikely
#define unlikely(x) __builtin_expect(x, 0)
#endif
