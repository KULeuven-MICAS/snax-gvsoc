// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>
#include <pmsis/kernel/kernel.h>
#include <pmsis/kernel/event.h>

/**
 * @addtogroup thread_apis
 * @{
 */

/**
 * @brief Thread handle type.
 *
 * Opaque structure representing a thread object.
 */
typedef struct pi_thread_s pi_thread_t;

/**
 * @brief Create and start a new thread.
 *
 * Creates a new thread with the specified properties and starts it.
 *
 * @param thread Pointer to the thread structure to initialize.
 * @param name Name of the thread (for debugging purposes).
 * @param entry Entry point function for the thread.
 * @param arg Argument to pass to the entry function.
 * @param priority Priority level of the thread (higher values = higher priority).
 * @param stack Pointer to the stack memory for the thread.
 * @param stack_size Size of the stack in bytes.
 * @param event Optional event to signal when the thread completes (can be NULL).
 *
 * @return 0 on success, negative error code on failure.
 */
int pi_thread_create(pi_thread_t *thread, const char *name, void (*entry)(void *), void *arg,
    int priority, void *stack, unsigned int stack_size, pi_evt_t *event);

/**
 * @brief Set the status of the current thread.
 *
 * Sets the status value for the currently executing thread.
 *
 * @param status The status value to set.
 */
ALWAYS_INLINE void pi_thread_status_set(int status);

/**
 * @brief Get the status of a thread.
 *
 * Retrieves the current status of the specified thread.
 *
 * @param thread Pointer to the thread structure.
 *
 * @return Current status of the thread.
 */
ALWAYS_INLINE int pi_thread_status_get(pi_thread_t *thread);

/**
 * @brief Yield the current thread.
 *
 * Voluntarily gives up the CPU to the next ready thread of the same or higher
 * priority. If no other thread is ready, the current thread continues.
 */
void pi_thread_yield();

/**
 * @brief Exit the current thread.
 *
 * Terminates the currently executing thread and performs cleanup.
 * This function does not return.
 */
void pi_thread_exit();

/**
 * @}
 */

#include <kernel/thread_data.h>
#include <kernel/thread_implem.h>
