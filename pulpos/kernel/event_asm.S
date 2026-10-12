// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <pmsis/kernel/kernel.h>

#include "thread_data.h"
#include "event_data.h"

    .global __pi_thread_sleep
    .type   __pi_thread_sleep, @function
__pi_thread_sleep:
    // Since the loop will use some saved register, we need to save them before calling it
    add     sp, sp, -16
    sw      s0, 0(sp)
    sw      s1, 8(sp)
    sw      ra, 4(sp)
    lw      s1, %tiny(__pi_thread_current)(x0)
    j       __pi_thread_sleep_start

    .size   __pi_thread_sleep, . - __pi_thread_sleep




    .global __pi_evt_sig_wait
    .type   __pi_evt_sig_wait, @function
__pi_evt_sig_wait:
    // Arguments:
    //     a0: event
    //     a1: current thread


    // Store some saved registers on the stack since we will use them to store information
    // while calling callbacks
    add     sp, sp, -16
    sw      s0, 0(sp)
    mv      s0, a0
    sw      s1, 8(sp)
    mv      s1, a1
    sw      ra, 4(sp)

    sb      x0, PI_THREAD_T_NOT_WAITING(s1)
    // Mark this thread as waiting on this event, this will be used to wakup the thread when
    // event is notified
    sw      s1, PI_EVT_T_WAITING_THREAD(s0)

    // Execute work-items
__pi_thread_handle_work_items:
    // Execute first all pending event callbacks
    lw      a0, %tiny(__pi_evt_ready_first)(x0)
    beqz    a0, __pi_thread_handle_work_items_no_callbacks

    la     ra, __pi_thread_handle_work_items
    lw     t5, PI_EVT_T_NEXT(a0)
    lw     t6, PI_EVT_T_CALLBACK(a0)
    sw     t5, %tiny(__pi_evt_ready_first)(x0)

    jr     t6

__pi_thread_handle_work_items_no_callbacks:
    // Then tasks. If there is any this will come back to callback handling in case new ones have
    // been added
    lw      t3, PI_THREAD_T_FIRST_TASK(s1)
    bnez    t3, __pi_evt_sig_wait_handle_tasks

    // Check if we should exit because event is now done
    // Here we are sure to leave with no work-item pending as we checked them before
    lb      t3, PI_THREAD_T_NOT_WAITING(s1)
    bnez    t3, __pi_evt_sig_wait_end

    // Make sure we won't be scheduled again since we don't have any work-item anymore
    // No need to update __pi_thread_ready since we were not in the queue as we are the current
    // thread
    sb      x0, PI_THREAD_T_READY(s1)

    // If there is any thready ready, switch to it instead of going to sleep
    lw      t3, %tiny(__pi_thread_ready)(x0)
    bnez    t3, __pi_evt_sig_wait_switch_thread




    // Now go to sleep
__pi_thread_sleep_start:
    // Mark the current thread as not running anymore
    sw      x0, %tiny(__pi_thread_current_running)(x0)

    // Switch to fast handlers
    la      t3, __pi_fast_irq_vector_base
    ori     t3, t3, 1
    csrw    mtvec, t3

    // And enable interrupts to let IRQ handlers execute while we are sleeping
    csrsi   mstatus,8

    // Enter the sleep loop
    // We loop forever since the interrupt handlers will make us leave by modifying the MEPC
    // to jump out of this loop.
__pi_thread_sleep_loop:
    // Do several wfi to avoid paying the cost of the jump at every interrupt
    wfi
    wfi
    wfi
    j     __pi_thread_sleep_loop




    .size   __pi_evt_sig_wait, . - __pi_evt_sig_wait

    .global __pi_thread_sleep_wakeup
    .type   __pi_thread_sleep_wakeup, @function
    // This can be called by returning from mret after forcing the mepc to it, to exit the wfi
    // loop
__pi_thread_sleep_wakeup:
    // We got waken-up by forcing a jump out of the sleep loop
    csrci   mstatus,8

    // Switch back to normal interrupt vectors
    la      t3, __pi_irq_vector_base
    ori     t3, t3, 1
    csrw    mtvec, t3

    // And execute the whole loop to check work-items and see if we can exit the event wait
    j       __pi_thread_handle_work_items

    .size   __pi_thread_sleep_wakeup, . - __pi_thread_sleep_wakeup




    .global __pi_evt_sig_wait_end
    .type   __pi_evt_sig_wait_end, @function
    // This gets called when we were waiting for a signal event and it got notified
__pi_evt_sig_wait_end:
    // Restore the information we saved when we entered and leave
    lw      s0, 0(sp)
    lw      s1, 8(sp)
    lw      ra, 4(sp)
    add     sp, sp, 16
    ret




    // This gets called when there are tasks to handle before going to sleep
__pi_evt_sig_wait_handle_tasks:
    // Pop them one by one
    lw      t6, PI_EVT_T_NEXT(t3)
    lw      t4, PI_EVT_T_CALLBACK(t3)
    mv      a0, t3
    sw      t6, PI_THREAD_T_FIRST_TASK(s1)
    sw      x0, PI_EVT_T_THREAD(t3)

    // And execute them with interrupts enabled since they should be limited by thread slice
    csrsi   mstatus,8

    jalr    ra, t4

    csrci   mstatus,8

    // Go back to whole loop in case event callbacks were enqueued during task execution.
    // We will get back to this function in case there are still some pending tasks
    j       __pi_thread_handle_work_items



    // This can be called from event wait routine to schedule another thread
__pi_evt_sig_wait_switch_thread:
    // We can safely call this C function since we come from a C call and we saved
    // preserved registers
    jal    ra, __pi_thread_switch_to_next
    // When we get back here, exec again the whole loop which will check work-items, and possibly
    // unblock the thread if the event is done
    j      __pi_thread_handle_work_items

    .size   __pi_evt_sig_wait_end, . - __pi_evt_sig_wait_end
