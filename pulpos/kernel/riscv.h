// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>

#define CSR_MSTATUS 0x300
#define CSR_MSTATUS_MIE_BIT 3

#define CSR_MTVEC  0x305

#if defined(__RV32__)
typedef uint32_t uint_t;
#elif defined(__RV64__)
typedef uint64_t uint_t;
#else
#error "Unknown processor width, define either __RV32__ or __RV64__"
#endif
