// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>
#include <pmsis/kernel/kernel.h>


/**
 * @addtogroup cycle_apis
 * @{
 */

/**
 * @brief Start the cycle counter.
 *
 * This function starts the hardware cycle counter. Once started, the counter increments
 * every clock cycle and can be read using pi_cycle_get32() or pi_cycle_get64().
 */
ALWAYS_INLINE void pi_cycle_start();

/**
 * @brief Get the current cycle count as a 64-bit value.
 *
 * This function returns the current value of the cycle counter as a 64-bit integer,
 * avoiding overflow issues that may occur with the 32-bit variant on long-running measurements.
 * This returns the same as pi_cycle_get64 on targets which only have 32bits counter.
 *
 * @return Current cycle count as a 64-bit value.
 */
ALWAYS_INLINE uint64_t pi_cycle_get64();

/**
 * @brief Get the current cycle count as a 32-bit value.
 *
 * This function returns the current value of the cycle counter as a 32-bit integer.
 * For long-running measurements where overflow may occur, use pi_cycle_get64() instead.
 *
 * @return Current cycle count as a 32-bit value.
 */
ALWAYS_INLINE uint32_t pi_cycle_get32();

/**
 * @brief Stop the cycle counter.
 *
 * This function stops the hardware cycle counter. The counter value is preserved
 * and can still be read after stopping.
 */
ALWAYS_INLINE void pi_cycle_stop();

/**
 * @brief Reset the cycle counter.
 *
 * This function resets the cycle counter value to zero.
 */
ALWAYS_INLINE void pi_cycle_reset();
/**
 * @}
 */

#if defined(CONFIG_CYCLE_INC)
#include CONFIG_CYCLE_INC
#endif
