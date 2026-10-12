// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>
#include <pmsis/kernel/kernel.h>

// The cycle CSR is always counting on this target, the start/stop/reset
// operations are empty and measurements must be done by difference between
// two reads.

ALWAYS_INLINE void pi_cycle_start() {
}

ALWAYS_INLINE void pi_cycle_stop() {
}

ALWAYS_INLINE void pi_cycle_reset() {
}

ALWAYS_INLINE uint32_t pi_cycle_get32() {
    uint32_t val;
    // Read mcycle. The user-mode cycle CSR is not implemented on the RTL core.
    __asm__ volatile("csrr %0, 0xB00" : "=r"(val));
    return val;
}

ALWAYS_INLINE uint64_t pi_cycle_get64() {
    return (uint64_t)pi_cycle_get32();
}
