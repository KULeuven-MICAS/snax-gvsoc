// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#ifndef LANGUAGE_ASSEMBLY

#include <kernel/event_data.h>
#include <kernel/riscv.h>
#include <pmsis/kernel/memory.h>

#define PI_THREAD_MAX_PRIORITIES 3

typedef struct pi_thread_queue_s
{
    struct pi_thread_s *first;
    struct pi_thread_s *last;
} pi_thread_queue_t;

typedef struct pi_thread_s
{
    // Registers to be saved/retored during a context switch.
    struct {
        uint_t ra;
        uint_t s0;
        uint_t s1;
        uint_t s2;
        uint_t s3;
        uint_t s4;
        uint_t s5;
        uint_t s6;
        uint_t s7;
        uint_t s8;
        uint_t s9;
        uint_t s10;
        uint_t s11;
        uint_t sp;
        uint_t mstatus;
        uint_t mepc;
    } regs;
    // Next pointer for chaining thread
    struct pi_thread_s *next;
    // First work item notified on this thread
    pi_evt_t *first_task;
    // Last work item notified on this thread
    pi_evt_t *last_task;
    // Thread status which should be reported to any thread joining this one
    int status;
    // Event to be notified when thread has exited
    pi_evt_t *event;
    // True if thread is finished
    char finished;
    // Thread priority
    char priority;
    // True if thread is ready to be executed
    char ready;
    // False if threading is waiting for something (e.g. mutex or signal event).
    // This does not prevent him from beeing ready so that it can execute work-items.
    char not_waiting;
#if defined(CONFIG_STACK_CHECK)
    // Stack bounds declared to the simulator stack checker at each context
    // switch to this thread
    uint_t stack_base;
    uint_t stack_size;
#endif
} pi_thread_t;

extern PI_MEMORY_TINY pi_thread_t *__pi_thread_current;
extern PI_MEMORY_TINY int __pi_thread_current_running;
extern PI_MEMORY_TINY uint_t __pi_thread_ready;
extern PI_MEMORY_TINY pi_thread_t __pi_thread_main;

#endif

// Offsets for assembly code
#define PI_THREAD_T_REGS_RA          ( 0*4)
#define PI_THREAD_T_REGS_S0          ( 1*4)
#define PI_THREAD_T_REGS_S1          ( 2*4)
#define PI_THREAD_T_REGS_S2          ( 3*4)
#define PI_THREAD_T_REGS_S3          ( 4*4)
#define PI_THREAD_T_REGS_S4          ( 5*4)
#define PI_THREAD_T_REGS_S5          ( 6*4)
#define PI_THREAD_T_REGS_S6          ( 7*4)
#define PI_THREAD_T_REGS_S7          ( 8*4)
#define PI_THREAD_T_REGS_S8          ( 9*4)
#define PI_THREAD_T_REGS_S9          (10*4)
#define PI_THREAD_T_REGS_S10         (11*4)
#define PI_THREAD_T_REGS_S11         (12*4)
#define PI_THREAD_T_REGS_SP          (13*4)
#define PI_THREAD_T_REGS_MSTATUS     (14*4)
#define PI_THREAD_T_REGS_MEPC        (15*4)
#define PI_THREAD_T_NEXT             (16*4)
#define PI_THREAD_T_FIRST_TASK       (17*4)
#define PI_THREAD_T_LAST_TASK        (18*4)
#define PI_THREAD_T_STATUS           (19*4)
#define PI_THREAD_T_EVENT            (20*4)
#define PI_THREAD_T_FINISHED         (21*4 + 0)
#define PI_THREAD_T_PRIORITY         (21*4 + 1)
#define PI_THREAD_T_READY            (21*4 + 2)
#define PI_THREAD_T_NOT_WAITING      (21*4 + 3)
