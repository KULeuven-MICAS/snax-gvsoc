// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <string.h>
#include <pmsis/kernel/builtins.h>

// Initialize the thread scheduler. Must be called by the global os init
void __pi_thread_sched_init();
// Make the cpu sleep. Should be called when no thread is ready to be scheduled.
// This will still handle interrupt handlers and will leave only when
// a thread is ready to be scheduled.
void __pi_thread_sleep();
// This can be called to unblock the specified waiting thread, which may become ready
static inline __attribute__((always_inline)) void __pi_thread_unblock_waiting(pi_thread_t *thread);
// Enqueue the thread to the ready queue of its priority
void __pi_thread_enqueue_ready(pi_thread_t *thread);
// Check if the a new thread must be scheduled. If so, it will only flag a reschedule, which will
// happen later when leaving the interrupt handler
void __pi_thread_slice_check();
// Deschedule current thread for example, after an exit. This may go to sleep if no thread can be
// scheduled.
void __pi_thread_deschedule();
// Do a context switch
void __pi_thread_switch();
// Force a context switch to the next ready thread
void __pi_thread_switch_to_next();
// Thread start stub used to unlock interrupts before executing thread entry point
void __pi_thread_start();

extern PI_MEMORY_TINY char __pi_thread_resched;

// Check if the a new thread must be scheduled. If so, it will only flag a reschedule, which will
// happen later when leaving the interrupt handler.
// Only have effect if preemption is enabled
static inline __attribute__((always_inline)) void pi_thread_slice_check()
{
#if defined(CONFIG_THREAD_PREEMPTION)
    __pi_thread_slice_check();
#endif
}

// Return highest priority thread
static inline int __pi_thread_get_highest_prio()
{
    return __FL1(__pi_thread_ready);
}

static inline __attribute__((always_inline)) void __pi_thread_current_unblock(pi_thread_t *thread)
{
    // In case there is no thread executing, it means we are just in the wfi loop waiting
    // the next thread.
    // The wfi loop is just looping without checking anything. Since we arrived here from an
    // interrupt handler, we just need to modify the saved PC (MEPC) and return.
    __pi_thread_current_running = 1;
        asm volatile ("csrw %0, %1" :  : "I" (0x341), "r" (__pi_thread_sleep_wakeup) );
}

static inline __attribute__((always_inline)) void __pi_thread_enqueue_ready_check(pi_thread_t *thread)
{
    if (!thread->ready)
    {
        if (__pi_thread_current == thread)
        {
            // Case where this thread was the last to execute but was blocked and no other thread could
            // execute, which means we are currently stuck in the sleep loop.
            // Mark the thread as running again and unblock the thread
            thread->ready = 1;
            __pi_thread_current_unblock(thread);
        }
        else
        {
            // Otherwise, just enqueue it to ready and flag the scheduler so that we check if this
            // thread should be scheduled when leaving the interrupt handler because it has higher
            // priority than current thread.
            __pi_thread_enqueue_ready(thread);
            __pi_thread_resched = 1;
        }
    }
}

// Unblock a waiting thread
static inline __attribute__((always_inline)) void __pi_thread_unblock_waiting(pi_thread_t *thread)
{
    // The thread is not waiting anymore
    thread->not_waiting = 1;
    // Now check if it is ready as something else can prevent it from being enqueued
    __pi_thread_enqueue_ready_check(thread);
}

// Dequeue first thread from queue
static inline pi_thread_t *__pi_thread_dequeue_first(pi_thread_queue_t *queue)
{
    pi_thread_t *result = queue->first;
    queue->first = result->next;
    return result;
}

ALWAYS_INLINE void pi_thread_status_set(int status)
{
    __pi_thread_current->status = status;
}

ALWAYS_INLINE int pi_thread_status_get(pi_thread_t *thread)
{
    return thread->status;
}

// Get current thread
static inline pi_thread_t *pi_thread_get_current()
{
    return __pi_thread_current;
}
