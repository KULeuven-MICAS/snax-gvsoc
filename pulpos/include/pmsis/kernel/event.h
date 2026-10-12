// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stdint.h>
#include <pmsis/kernel/kernel.h>

typedef struct pi_thread_s pi_thread_t;

/**
 * @addtogroup event_apis
 * @{
 */

/**
 * @brief Type for events.
 *
 * Events can be used as signal events, callback events, or task events.
 */
typedef struct pi_evt_s pi_evt_t;

/**
 * @brief Initialize an event as a signal event.
 *
 * Signal events allow the caller to initiate an asynchronous operation, continue with other tasks,
 * and then explicitly wait for the event when the result is needed. The wait call blocks the
 * caller until the asynchronous operation signals completion.
 *
 * Once an event is initialized with this function, it becomes a signal event.
 * The signal event can then be passed to any asynchronous function so that the caller is notified
 * of the function's completion.
 * The caller can call pi_evt_sig_wait() to block until the function completes.
 *
 * @param event Pointer to the event.
 *
 * @note The event must not be used anywhere when it is initialized.
 * The same event can be reused, but only after it has been notified. For tasks, they must also
 * have started execution before they can be reused.
 *
 * @return Pointer to the event.
 *
 */
ALWAYS_INLINE pi_evt_t *pi_evt_sig_init(pi_evt_t *event);

/**
 * @brief Initialize an event as a callback event.
 *
 * Callback events provide immediate notification through a function pointer supplied during event
 * initialization. When the asynchronous operation completes, it invokes the callback function
 * directly, potentially from within an interrupt context. This form enables the fastest possible
 * response to completion but requires the callback to be interrupt-safe and to execute quickly.
 *
 * Once an event is initialized with this function, it becomes a callback event.
 * The callback event can then be passed to any asynchronous function so that the caller is notified
 * of the function's completion by a call to the specified callback.
 *
 * @param event Pointer to the event.
 * @param callback Function that will be called when the event is notified.
 *
 * @note Using this kind of notification is particularly useful when the event is notified by an interrupt
 * handler, so that the function is called directly by the interrupt handler.
 *
 * @return Pointer to the event.
 *
 */
ALWAYS_INLINE pi_evt_t *pi_evt_cb_init(pi_evt_t *event, void (*callback)(pi_evt_t*));

/**
 * @brief Initialize an event as a task event.
 *
 * Tasks provide deferred notification through a work queue system. Instead of executing the
 * notification callback immediately (potentially from interrupt context), the callback is scheduled
 * on a dedicated work queue thread. This approach combines the benefits of asynchronous notification
 * with the safety of executing callbacks in thread context rather than interrupt context, making it
 * suitable for callbacks that require more processing time or need to call blocking functions.
 *
 * @param event Pointer to the event.
 * @param callback Function that will be called when the event is scheduled on the work queue.
 * @param thread Pointer to the thread on whose work queue the task will be scheduled.
 *
 * @return Pointer to the event.
 *
 */
ALWAYS_INLINE pi_evt_t *pi_evt_task_init(pi_evt_t *event, void (*callback)(pi_evt_t*), pi_thread_t *thread);

/**
 * @brief Notify the completion of an event.
 *
 * This function triggers the notification of the event that was provided when the event was
 * initialized.
 *
 * In the case of a signal event, it flags it as completed and unblocks any thread waiting on it. If
 * any thread then tries to wait for it by calling pi_evt_sig_wait(), it will immediately
 * return.
 *
 * In the case of a callback event, the callback is called immediately from the caller's context, even
 * if it is from an interrupt handler.
 *
 * In the case of a task event, it is pushed to its work queue and will be executed later
 * when it is scheduled.
 *
 * @param event Pointer to the event.
 *
 * @note Although this function is mostly used by drivers to notify the end of driver operations,
 * it can also be used by user code to synchronize different pieces of code.
 */
ALWAYS_INLINE void pi_evt_notify(pi_evt_t *event);

/**
 * @brief Notify the completion of an event without internal locking.
 *
 * This behaves exactly as pi_evt_notify() but does not perform any internal locking.
 * This function must be called from a context where interrupts are already disabled or from
 * an interrupt handler to ensure thread safety.
 * This variant provides better performance by skipping the lock/unlock operations.
 *
 * @param event Pointer to the event.
 *
 * @warning This function must only be called from a safe context (e.g., with interrupts disabled
 * or from an interrupt handler). Calling it from an unsafe context may lead to race conditions.
 */
ALWAYS_INLINE void pi_evt_notify_unsafe(pi_evt_t *event);

/**
 * @brief Wait for the completion of a signal event.
 *
 * This function blocks the caller until the given signal event is notified.
 * If it has already been notified, this function returns immediately.
 *
 * While the caller is blocked waiting for the event, it will execute any task that has been
 * enqueued in its thread's work queue.
 *
 * @param event Pointer to the event.
 */
ALWAYS_INLINE void pi_evt_sig_wait(pi_evt_t *event);

/**
 * @brief Wait for the completion of a signal event without internal locking.
 *
 * This behaves exactly as pi_evt_sig_wait() but does not perform any internal locking.
 * This function must be called from a context where interrupts are already disabled or from
 * an interrupt handler to ensure thread safety.
 * This variant provides better performance by skipping the lock/unlock operations.
 *
 * @param event Pointer to the event.
 *
 * @warning This function must only be called from a safe context (e.g., with interrupts disabled
 * or from an interrupt handler). Calling it from an unsafe context may lead to race conditions.
 */
ALWAYS_INLINE void pi_evt_sig_wait_unsafe(pi_evt_t *event);

/**
 * \brief Get event status.
 *
 * This function returns the status of the asynchronous operation associated with the event.
 *
 * @param event Pointer to the event.
 *
 * \return        Value corresponding to event status.
 */
ALWAYS_INLINE int pi_evt_status_get(pi_evt_t *event);

/**
 * \brief Set event status.
 *
 * This function sets the status of the asynchronous operation associated with the event.
 *
 * @param event Pointer to the event.
 * @param status Event status.
 *
 * \return        Value corresponding to event status.
 */
ALWAYS_INLINE int pi_evt_status_set(pi_evt_t *event, int status);

/**
 * @}
 */

 #include <kernel/event_data.h>
 #include <kernel/event_implem.h>
