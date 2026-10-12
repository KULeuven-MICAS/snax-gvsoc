// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <pmsis/kernel/kernel.h>
#include PI_CHIP_INC(CONFIG_CHIP_FAMILY_NAME, kernel/properties.h)

#if defined(CHIP_HAS_ALIAS) && !defined(CONFIG_NO_ALIAS)

#include <kernel/thread_data.h>
#include <kernel/event_data.h>

#if 0
#define LP_START_0  ( 0x7C0 )
#define LP_END_0    ( 0x7C1 )
#define LP_COUNT_0  ( 0x7C2 )
#define LP_START_1  ( 0x7C4 )
#define LP_END_1    ( 0x7C5 )
#define LP_COUNT_1  ( 0x7C6 )
#endif

    .section .text_static

    .global __pi_irq_handler_stub
    .type   __pi_irq_handler_stub, @function
    // This is the normal common IRQ handler used by default for all interrupts.
    // This does not assume anything on previous state and save all the caller-saved registers.
__pi_irq_handler_stub:
    add  sp, sp, -160

    sw   ra, 0x00(sp)
    sw   gp, 0x04(sp)
    sw   tp, 0x08(sp)
    sw   t0, 0x0C(sp)
    sw   t1, 0x10(sp)
    sw   t2, 0x14(sp)
    sw   a0, 0x18(sp)
    sw   a1, 0x1C(sp)
    sw   a2, 0x20(sp)
    sw   a3, 0x24(sp)
    sw   a4, 0x28(sp)
    sw   a5, 0x2C(sp)
    sw   a6, 0x30(sp)
    sw   a7, 0x34(sp)
    sw   t3, 0x38(sp)
    sw   t4, 0x3C(sp)
    sw   t5, 0x40(sp)
    sw   t6, 0x4C(sp)

#if 0
    // TODO
    // This costs too much, need to find a way to optimize it
    csrr    t0, LP_START_0
    csrr    t1, LP_END_0
    csrr    t2, LP_COUNT_0
    sw      t0, 0x50(sp)
    sw      t1, 0x54(sp)
    sw      t2, 0x58(sp)
    csrr    t0, LP_START_1
    csrr    t1, LP_END_1
    csrr    t2, LP_COUNT_1
    sw      t0, 0x5C(sp)
    sw      t1, 0x60(sp)
    sw      t2, 0x64(sp)
#endif

    // Read IRQ number of mcause and execute IRQ handler from SW vector table
    csrr   t0, 0x342

    slli   t0, t0, 2
    p.lw   t1, %tiny(__pi_irq_handlers)(t0)
    p.lw   a0, %tiny(__pi_irq_handlers_arg)(t0)

    jalr   ra, t1

    // Once we are done with IRQ handler execution, we need to check a few things:
    // - check if another thread should be scheduled. This can happen when a new thread became ready
    // to check if it has higher priority or current thread can not run. If not nothing will happen.
    // - check if we should force the switch to a new thread. This happens when the thread slice is
    // is reached.
    // - execute any pending event callback as some might have been enqueued during IRQ handler execution
__pi_irq_handler_callbacks_check:
    // TODO
    // Not clear why we should switch to a different thread before handling event callbacks since
    // they are not associated to any thread.
    // To be checked when the thread test is integrated
    lb     t2, %tiny(__pi_thread_resched)(x0)
    lb     t3, %tiny(__pi_thread_force_resched)(x0)
    lw     a0, %tiny(__pi_evt_ready_first)(x0)
    bnez   t2, __pi_irq_resched_check
    bnez   t3, __pi_irq_resched_do
    beqz   a0, __pi_irq_restore

__pi_irq_handle_callbacks:
    lw     t5, PI_EVT_T_NEXT(a0)
    lw     t6, PI_EVT_T_CALLBACK(a0)
    sw     t5, %tiny(__pi_evt_ready_first)(x0)

    // After the callback execution, we need to check again callbacks and thread switch
    // ra still point there, no need to set it.
    jr     t6

__pi_irq_restore:
#if 0
    lw      t2, 0x64(sp)
    lw      t1, 0x60(sp)
    lw      t0, 0x5C(sp)
    csrw    LP_COUNT_1, t2
    csrw    LP_END_1, t1
    csrw    LP_START_1, t0
    lw      t2, 0x58(sp)
    lw      t1, 0x54(sp)
    lw      t0, 0x50(sp)
    csrw    LP_COUNT_0, t2
    csrw    LP_END_0, t1
    csrw    LP_START_0, t0
#endif

    lw   ra, 0x00(sp)
    lw   gp, 0x04(sp)
    lw   tp, 0x08(sp)
    lw   t0, 0x0C(sp)
    lw   t1, 0x10(sp)
    lw   t2, 0x14(sp)
    lw   a0, 0x18(sp)
    lw   a1, 0x1C(sp)
    lw   a2, 0x20(sp)
    lw   a3, 0x24(sp)
    lw   a4, 0x28(sp)
    lw   a5, 0x2C(sp)
    lw   a6, 0x30(sp)
    lw   a7, 0x34(sp)
    lw   t3, 0x38(sp)
    lw   t4, 0x3C(sp)
    lw   t5, 0x40(sp)
    lw   t6, 0x4C(sp)

    add  sp, sp, 160

    mret

    // This gets called when we need to check if another thread should be scheduled
__pi_irq_resched_check:
    // Get sched info about ready threads and current thread
    lw    t3, %tiny(__pi_thread_ready)(x0)
    lw    t2, %tiny(__pi_thread_current)(x0)
    // Allow another reschedule check for next time
    sb    x0, %tiny(__pi_thread_resched)(x0)
    // Nothing to do if there is no ready thread
    beqz  t3, __pi_irq_resched_check_end
    // Otherwise compare with current thread
    lb    t4, PI_THREAD_T_READY(t2)
    lb    t6, PI_THREAD_T_PRIORITY(t2)
    // Do resched if current thread is not ready
    beqz  t4, __pi_irq_resched_do
    // Or is not higher priority thread.
    p.fl1 t5, t3
    bgt   t5, t6, __pi_irq_resched_do
__pi_irq_resched_check_end:
    jr    ra

    // This gets called to force a schedule to next thread
__pi_irq_resched_do:
    // Allow the force for tnext next
    sb   x0, %tiny(__pi_thread_force_resched)(x0)
    j    __pi_thread_switch_to_next

    .size   __pi_irq_handler_stub, . - __pi_irq_handler_stub




    .global __pi_irq_fast_handler_stub
    .type   __pi_irq_fast_handler_stub, @function
    // This is the fast IRQ handler which is used when the core is sleeping to limit the context
    // save/restore.
__pi_irq_fast_handler_stub:

    // Since core is sleeping and has save important data to callee-saved registers,
    // we can safely call IRQ handlers without saving anything.
    csrr   t0, 0x342
    slli   t0, t0, 2
    p.lw   t1, %tiny(__pi_irq_handlers)(t0)
    p.lw   a0, %tiny(__pi_irq_handlers_arg)(t0)

    jalr   ra, t1

    // Once we are done with IRQ handler execution, we need to check a few things:
    // - check if another thread should be scheduled. This can happen when a new thread became ready
    // to check if it has higher priority or current thread can not run. If not nothing will happen.
    // - check if we should force the switch to a new thread. This happens when the thread slice is
    // is reached.
    // - execute any pending event callback as some might have been enqueued during IRQ handler execution
__pi_irq_fast_handle_callbacks_check:
// TODO
// Not clear why we should switch to a different thread before handling event callbacks since
// they are not associated to any thread.
// To be checked when the thread test is integrated
    lb     t2, %tiny(__pi_thread_resched)(x0)
    lb     t3, %tiny(__pi_thread_force_resched)(x0)
    lw     a0, %tiny(__pi_evt_ready_first)(x0)
    bnez   t2, __pi_irq_resched_check
    bnez   t3, __pi_irq_resched_do
    beqz   a0, __pi_irq_fast_handler_stub_end

__pi_irq_fast_handle_callbacks:
    lw     t5, PI_EVT_T_NEXT(a0)
    lw     t6, PI_EVT_T_CALLBACK(a0)
    sw     t5, %tiny(__pi_evt_ready_first)(x0)

    // After the callback execution, we need to check again callbacks and thread switch
    // ra still point there, no need to set it.
    jr     t6

__pi_irq_fast_handler_stub_end:
    mret

    .size   __pi_irq_fast_handler_stub, . - __pi_irq_fast_handler_stub



    .global __pi_exception_handler_stub
    .type   __pi_exception_handler_stub, @function
__pi_exception_handler_stub:
    add  sp, sp, -160

    sw   ra, 0x00(sp)
    sw   gp, 0x04(sp)
    sw   tp, 0x08(sp)
    sw   t0, 0x0C(sp)
    sw   t1, 0x10(sp)
    sw   t2, 0x14(sp)
    sw   a0, 0x18(sp)
    sw   a1, 0x1C(sp)
    sw   a2, 0x20(sp)
    sw   a3, 0x24(sp)
    sw   a4, 0x28(sp)
    sw   a5, 0x2C(sp)
    sw   a6, 0x30(sp)
    sw   a7, 0x34(sp)
    sw   t3, 0x38(sp)
    sw   t4, 0x3C(sp)
    sw   t5, 0x40(sp)
    sw   t6, 0x4C(sp)

#if 0
    csrr    t0, LP_START_0
    csrr    t1, LP_END_0
    csrr    t2, LP_COUNT_0
    sw      t0, 0x50(sp)
    sw      t1, 0x54(sp)
    sw      t2, 0x58(sp)
    csrr    t0, LP_START_1
    csrr    t1, LP_END_1
    csrr    t2, LP_COUNT_1
    sw      t0, 0x5C(sp)
    sw      t1, 0x60(sp)
    sw      t2, 0x64(sp)
#endif

    la     t1, pi_irq_handle_exception

    jalr   ra, t1

__pi_exception_restore:
#if 0
    lw      t2, 0x64(sp)
    lw      t1, 0x60(sp)
    lw      t0, 0x5C(sp)
    csrw    LP_COUNT_1, t2
    csrw    LP_END_1, t1
    csrw    LP_START_1, t0

    lw      t2, 0x58(sp)
    lw      t1, 0x54(sp)
    lw      t0, 0x50(sp)
    csrw    LP_COUNT_0, t2
    csrw    LP_END_0, t1
    csrw    LP_START_0, t0
#endif

    lw   ra, 0x00(sp)
    lw   gp, 0x04(sp)
    lw   tp, 0x08(sp)
    lw   t0, 0x0C(sp)
    lw   t1, 0x10(sp)
    lw   t2, 0x14(sp)
    lw   a0, 0x18(sp)
    lw   a1, 0x1C(sp)
    lw   a2, 0x20(sp)
    lw   a3, 0x24(sp)
    lw   a4, 0x28(sp)
    lw   a5, 0x2C(sp)
    lw   a6, 0x30(sp)
    lw   a7, 0x34(sp)
    lw   t3, 0x38(sp)
    lw   t4, 0x3C(sp)
    lw   t5, 0x40(sp)
    lw   t6, 0x4C(sp)

    add  sp, sp, 160

    mret

    .size   __pi_irq_fast_handler_stub, . - __pi_irq_fast_handler_stub


    // This is the normal vector table which makes all vector call a common IRQ handler which will
    // do complete context save/restore
.section .vectors, "ax"
.option norvc;

    j __pi_exception_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub
    j __pi_irq_handler_stub



    // This is the optimized vector table which makes all vector call a common IRQ handler which
    // will assume the core was sleeping and will not do any context save/restore
.section .fast_vectors, "ax"
.option norvc;

    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub
    j __pi_irq_fast_handler_stub

#endif
