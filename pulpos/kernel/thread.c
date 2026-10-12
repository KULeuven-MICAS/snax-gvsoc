// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <string.h>
#include <pmsis/kernel/thread.h>
#include <kernel/hal.h>
#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__) || defined(CONFIG_STACK_CHECK)
#include <gvsoc.h>
#endif
#endif

#if defined(CONFIG_STACK_CHECK)
// Main stack bounds from the linker script
extern unsigned char stack_start[];
extern unsigned char stack[];
#endif

// Queues of ready thread, one per priority.
PI_MEMORY_TINY pi_thread_queue_t __pi_thread_ready_queues[PI_THREAD_MAX_PRIORITIES];
// Mask giving the queues containing at least one ready thread. One bit per queue.
PI_MEMORY_TINY uint_t __pi_thread_ready;
// Current thread which has been the last to execute. It can either be currently running or
// blocked if no other thread can be scheduled
PI_MEMORY_TINY pi_thread_t *__pi_thread_current;
// Tell if the current thread is running or not, as it could be the current but not running if
// no other thread can be scheduled
PI_MEMORY_TINY int __pi_thread_current_running;
// Set to 1 when we should check if a higher priority thread should be scheduled when leaving
// interrupt handler
PI_MEMORY_TINY char __pi_thread_resched;
// Set to 1 when we should force the scheduler to schedule a new thread when leaving the
// interrupt handler. This is used to end the current thread slice
PI_MEMORY_TINY char __pi_thread_force_resched;
// Thread storage for main thread
PI_MEMORY_TINY pi_thread_t __pi_thread_main;

#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
// Store the VCD trace used to send to the profiler information about thread lifecycle
PI_MEMORY_TINY int __pi_thread_vcd_lifecycle;
// Store the VCD trace used to tell the profiler the current thread
PI_MEMORY_TINY int __pi_thread_vcd_current;
#endif
#endif

// Send the thread name to the profiler
static int __pi_thread_name_set(pi_thread_t *thread, const char *name)
{
#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
    int irq = pi_irq_lock();
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, 2);
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, (uint32_t)thread);

    if (name)
    {
        while(1)
        {
            gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, (uint32_t)*name);
            if (*name == 0)
            {
                break;
            }
            name++;
        }
    }
    else
    {
        gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, 0);
    }
#endif
#endif
}

// Enqueue a thread to the tail of a thread queue.
static inline void __attribute__((always_inline)) __pi_thread_enqueue(pi_thread_queue_t *queue,
        pi_thread_t *thread)
{
    if (queue->first == NULL)
    {
        queue->first = thread;
    }
    else
    {
        queue->last->next = thread;
    }

    thread->next = NULL;
    queue->last = thread;
}

// Initialize a thread state after creation so that it is ready to be scheduled
static void __pi_thread_state_init(pi_thread_t *thread)
{
    thread->finished = 0;
    thread->priority = 0;
    thread->first_task = NULL;
    thread->ready = 0;
    thread->not_waiting = 1;
}

void pi_thread_yield()
{
    int irq = pi_irq_lock();
    if (__pi_thread_ready)
    {
        __pi_thread_switch_to_next();
    }
    pi_irq_unlock(irq);
}

void pi_thread_exit()
{
    pi_irq_lock();
    pi_thread_t *thread = __pi_thread_current;
    thread->finished = 1;
    thread->ready = 0;
    if (thread->event)
    {
        pi_evt_notify_unsafe(thread->event);
    }

#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, 3);
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, (uint32_t)thread);
#endif
#endif

    __pi_thread_deschedule();
}

// Init the thread saved context so that it can start executing after first context switch to it
static void __pi_thread_init(pi_thread_t *thread, void (*entry)(void *), void *arg,
    int priority, void *stack, unsigned int stack_size, pi_evt_t *event)
{
    thread->regs.sp = (long)stack + stack_size;
    thread->regs.ra = (long)__pi_thread_start;
    thread->regs.s0 = (long)entry;
    thread->regs.s1 = (long)arg;
    thread->regs.s2 = (long)pi_thread_exit;
    thread->priority = priority;
    thread->event = event;
    thread->status = 0;
#if defined(CONFIG_STACK_CHECK)
    thread->stack_base = (uint_t)stack;
    thread->stack_size = stack_size;
#endif
}

// Init thread queue
static void __pi_thread_queue_init(pi_thread_queue_t *queue)
{
    queue->first = NULL;
}

void __pi_thread_sched_init()
{
    for (int i=0; i<PI_THREAD_MAX_PRIORITIES; i++)
    {
        __pi_thread_queue_init(&__pi_thread_ready_queues[i]);
    }

#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
    __pi_thread_vcd_lifecycle = gv_vcd_open_trace("thread_lifecycle");
    __pi_thread_vcd_current = gv_vcd_open_trace("thread_current");

    // Set main thread tid
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, 4);
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, (uint32_t)&__pi_thread_main);
#endif
#endif

    // Initialize the main thread so that it is handled like any other thread
    __pi_thread_current = &__pi_thread_main;
    __pi_thread_state_init(&__pi_thread_main);
#if defined(CONFIG_STACK_CHECK)
    __pi_thread_main.stack_base = (uint_t)stack_start;
    __pi_thread_main.stack_size = (uint_t)(stack - stack_start);
#endif
    __pi_thread_main.ready = 1;
    __pi_thread_main.priority = 0;
    __pi_thread_current_running = 1;
    __pi_thread_resched = 0;
    __pi_thread_force_resched = 0;
}

int pi_thread_create(pi_thread_t *thread, const char *name, void (*entry)(void *), void *arg, int priority,
    void *stack, unsigned int stack_size, pi_evt_t *event)
{
    int irq = pi_irq_lock();
    __pi_thread_state_init(thread);
    __pi_thread_init(thread, entry, arg, priority, stack, stack_size, event);
    __pi_thread_enqueue_ready(thread);

#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, 1);
    gv_vcd_dump_trace(__pi_thread_vcd_lifecycle, (uint32_t)thread);
    __pi_thread_name_set(thread, name);
#endif
#endif

    pi_irq_unlock(irq);

    return 0;
}

// Dequeue and get highest priority ready thread
static pi_thread_t *__pi_thread_dequeue_ready()
{
    int priority = __pi_thread_get_highest_prio();
    // Get and dequeue from queue
    pi_thread_t *thread = __pi_thread_dequeue_first(&__pi_thread_ready_queues[priority]);
    // And update the mask so that the scheduler do not try to schedule from this queue if it is
    // empty
    if (__pi_thread_ready_queues[priority].first == NULL)
    {
        __pi_thread_ready = __BITCLR_R(__pi_thread_ready, 1, priority);
    }
    return thread;
}

void __pi_thread_enqueue_ready(pi_thread_t *thread)
{
    int priority = thread->priority;
    thread->ready = 1;
    // Enqueue to the right priority
    __pi_thread_enqueue(&__pi_thread_ready_queues[priority], thread);
    // Update the priority mask so that the scheduler knows a thread is ready there
    __pi_thread_ready = __BITSET_R(__pi_thread_ready, 1, priority);
}

void __pi_thread_switch_to_next()
{
    pi_thread_t *current = __pi_thread_current;
    __pi_thread_current = __pi_thread_dequeue_ready();

    // Only switch if next thread is different
    if (__pi_thread_current != current)
    {
        // Current thread may still be ready, in which case it needs to be in the ready queue
        if (current->ready)
        {
            __pi_thread_enqueue_ready(current);
        }

        // If the current thread is currently blocked in the sleep loop, we have to make sure
        // it will go out of the loop the next time it is scheduled.
        // For that we modified the curent mepc since it will be saved by __pi_thread_switch
        if (!__pi_thread_current_running)
        {
            asm volatile ("csrw %0, %1" :  : "I" (0x341), "r" (__pi_thread_sleep_wakeup) );
        }

        __pi_thread_current_running = 1;

        // We might have entered irq handler from fast mode. Since we're breaking
        // control flow, we need to switch back to normal mode.
        asm volatile ("csrw %0, %1" :  : "I" (CSR_MTVEC), "r" (__pi_linker_irq_vector_base()) );

#if defined(__PLATFORM_GVSOC__)
#if defined(__GVSOC_GUI__)
        gv_vcd_dump_trace(__pi_thread_vcd_current, (uint32_t)__pi_thread_current);
#endif
#endif

#if defined(CONFIG_STACK_CHECK)
        // Declare the next thread's stack before switching; the simulator arms
        // the checks once SP lands inside it (the sp restore in
        // __pi_thread_switch)
        gv_stack_set((void *)__pi_thread_current->stack_base,
            __pi_thread_current->stack_size);
#endif

        // Now do the actual switch
        __pi_thread_switch(current, __pi_thread_current);
    }
}

void __pi_thread_deschedule()
{
    if (!__pi_thread_ready)
    {
        __pi_thread_sleep();
    }
    else
    {
        __pi_thread_switch_to_next();
    }
}

void __pi_thread_slice_check()
{
    // Check if a ready thread is higher priority than current thread.
    if (__pi_thread_ready)
    {
        if (!__pi_thread_current || __pi_thread_current->priority <= __pi_thread_get_highest_prio())
        {
            __pi_thread_force_resched = 1;
        }
    }
}
