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
 * @addtogroup time_apis
 * @{
 */

/**
 * @brief Notify the termination of an event after a delay.
 *
 * This behaves exactly as pi_evt_notify(), except that the event notification is triggered
 * after a delay.
 *
 * @param event Pointer to the event.
 * @param delay Delay in micro-seconds after which the event is notified.
 *
 * @note The given delay is taken as a minimum. It is guaranteed that the event is notified
 * at least after the given delay, but this may be more due to rounding and processor activity.
 */
ALWAYS_INLINE void pi_evt_notify_delayed(pi_evt_t *event, uint32_t delay);



/**
 * @brief Notify the termination of an event after a delay from a safe caller.
 *
 * This behaves exactly as pi_evt_notify_delayed() but gives a hint to the callee that it is being
 * called from a safe caller, i.e. with interrupts disabled.
 * The callee can then use it to skip interrupt disabling/restoring for performance reasons.
 * This is particularly interesting to call this variant from interrupt handlers which are
 * frequently called.
 *
 * @param event Pointer to the event.
 * @param delay Delay in micro-seconds after which the event is notified.
 */
void pi_evt_notify_delayed_unsafe(pi_evt_t *event, uint32_t delay);

/**
 * @brief Cancel a timed event.
 *
 * This function removes a timed event from any queue where it has been enqueued so that
 * the event can be safely reused for something else.
 *
 * In case it has been notified as a delayed event, if the delay has not elapsed, the event is removed
 * from the waiting queue of timed events. If the delay has elapsed, if the event is a work-item,
 * and it has not been executed yet, it is removed from the work-item queue.
 * For all other cases, nothing is done.
 *
 * @param event Pointer to the event.
 */
ALWAYS_INLINE void pi_evt_timed_cancel(pi_evt_t *event);



/**
 * @brief Cancel a timed event from a safe caller.
 *
 * This behaves exactly as pi_evt_timed_cancel() but gives a hint to the callee that it is being
 * called from a safe caller, i.e. with interrupts disabled.
 * The callee can then use it to skip interrupt disabling/restoring for performance reasons.
 * This is particularly interesting to call this variant from interrupt handlers which are
 * frequently called.
 *
 * @param event Pointer to the event.
 */
void pi_evt_timed_cancel_unsafe(pi_evt_t *event);

/**
 * @brief Get current time in microseconds.
 *
 * This function returns the current time in microseconds since the runtime has started.
 *
 * @return Current time in microseconds.
 */
uint64_t pi_time_get_us();

/**
 * @brief Wait for a specified time in microseconds.
 *
 * This function blocks the calling task for the specified amount of time.
 *
 * @param time Time to wait in microseconds.
 */
void pi_time_wait_us(int time);

/**
 * @}
 */

enum pi_time_source;

void __pi_time_source_set(enum pi_time_source source, int frequency);
void __pi_time_slice_set(int slice);

#if defined(CONFIG_TIME_INC)
#include CONFIG_TIME_INC
#endif

#include <kernel/time_implem.h>
