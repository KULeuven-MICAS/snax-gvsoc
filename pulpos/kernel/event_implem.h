// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <string.h>
#include <pmsis/kernel/irq.h>
#include <kernel/thread_data.h>

// This is a kind of stub used to force the core to exits its sleep loop. This is force
// in the MEPC csr during an interrupt handler to make it jump there, check work-items
// and event wait status.
void __pi_thread_sleep_wakeup();
// Block the execution until the event is signaled. This may execute events associated
// to the current thread, and may also schedule another thread
void __pi_evt_sig_wait(pi_evt_t *event, pi_thread_t *current_thread);
// Callback associated to signal events, which is in charge of handling signal events wakeup
void __pi_evt_handle_signal(pi_evt_t *arg);
// Event callback associated to task events, to make it push the task when the callback is execute.
void __pi_evt_push_task(pi_evt_t *event);
// Init scheduler, should be called during runtime init
void __pi_evt_sched_init();

ALWAYS_INLINE void pi_evt_sig_wait(pi_evt_t *event)
{
    int irq = pi_irq_lock();
    pi_evt_sig_wait_unsafe(event);
    pi_irq_unlock(irq);
}

ALWAYS_INLINE void pi_evt_sig_wait_unsafe(pi_evt_t *event)
{
    if (event->callback)
    {
        __pi_evt_sig_wait(event, __pi_thread_current);
    }
}

ALWAYS_INLINE void __attribute__((always_inline)) pi_evt_notify_unsafe(pi_evt_t *event)
{
    event->next = __pi_evt_ready_first;
    __pi_evt_ready_first = event;
}

ALWAYS_INLINE void __attribute__((always_inline)) pi_evt_notify(pi_evt_t *event)
{
    int irq = pi_irq_lock();
    pi_evt_notify_unsafe(event);
    pi_irq_unlock(irq);
}

ALWAYS_INLINE pi_evt_t *pi_evt_sig_init(pi_evt_t *event)
{
    pi_evt_cb_init(event, __pi_evt_handle_signal);
    event->waiting_thread = NULL;
    return event;
}

ALWAYS_INLINE pi_evt_t *pi_evt_cb_init(pi_evt_t *event, void (*callback)(pi_evt_t*))
{
    event->callback = callback;
    return event;
}

ALWAYS_INLINE pi_evt_t *pi_evt_task_init(pi_evt_t *event, void (*callback)(pi_evt_t*), pi_thread_t *thread)
{
    pi_evt_cb_init(event, __pi_evt_push_task);
    event->thread = thread ? thread : &__pi_thread_main;
    event->waiting_thread = (pi_thread_t *)callback;
    return event;
}

ALWAYS_INLINE int pi_evt_status_get(pi_evt_t *event)
{
    return event->status;
}

ALWAYS_INLINE int pi_evt_status_set(pi_evt_t *event, int status)
{
    event->status = status;
    return 0;
}
