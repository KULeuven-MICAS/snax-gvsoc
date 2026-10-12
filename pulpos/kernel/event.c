// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <pmsis/kernel/event.h>
#include <kernel/thread_implem.h>

PI_MEMORY_TINY pi_evt_t *__pi_evt_ready_first;

// This gets called when a polling event gets notified to flag it and unblock any waiting thread.
void __pi_evt_handle_signal(pi_evt_t *event)
{
    pi_thread_t *thread = (pi_thread_t *)event->waiting_thread;

    // Flag the event as notified so that any thread waiting for it from now will just return
    // immediately.
    event->callback = NULL;

    // Then unblobk waiting thread
    if (thread)
    {
        __pi_thread_unblock_waiting(thread);
    }
}

void __pi_evt_push_task(pi_evt_t *event)
{
    // We get called by the event callback attached to task events, when the event was notified.
    // Now push the task to the associated thread task queue

    pi_thread_t *thread = event->thread;

    if (thread->first_task)
    {
        thread->last_task->next = event;
    }
    else
    {
        thread->first_task = event;
    }
    thread->last_task = event;
    event->next = NULL;
    event->callback = (void (*)(pi_evt_t*))event->waiting_thread;

    // The thread may need to become ready in case it is waiting for something
    __pi_thread_enqueue_ready_check(thread);
}


void __pi_evt_sched_init()
{
    __pi_evt_ready_first = NULL;
}
