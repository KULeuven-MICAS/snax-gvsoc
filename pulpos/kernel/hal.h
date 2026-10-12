// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// This file can be included to have access to chip-dependent code implementing the HAL

#pragma once

#include <stdint.h>

// Write a buffer to a file descriptor
static inline void __pi_libc_write(int fd, uint8_t *buffer, int len);

// Make the platform exit with the specified status
static inline void __attribute__((noreturn)) __pi_init_platform_exit(int status);

// Initialize all the soc
void __pi_init_soc();

// Now include the chip-specific header
#include <pmsis/kernel/kernel.h>
#include PI_CHIP_INC(CONFIG_CHIP_FAMILY_NAME, kernel/hal.h)
