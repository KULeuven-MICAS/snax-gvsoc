// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#ifndef LANGUAGE_ASSEMBLY

#include <stdint.h>
#include <pmsis/kernel/memory.h>
#include <kernel/riscv.h>

typedef struct pi_thread_s pi_thread_t;
typedef struct pi_evt_s pi_evt_t;

typedef struct pi_evt_s
{
    // Callback function called when callback event gets notified or work-item event gets execute.
    void (*callback)(pi_evt_t*);

    // Used for chaining events in various queues
    pi_evt_t *next;

    // List of threads waiting for the completion of the event in case it is a polling event.
    pi_thread_t *waiting_thread;

    // Thread this event belongs to. This is not NULL only when the event is a work-item and has
    // not been executed yet. In this case, it is set to NULL just before the work-item starts
    // execution.
    pi_thread_t *thread;

    // Return value of the asynchromous operation associate to the event.
    int status;

    // Extra timestamp. This is used to store the time where the event must be notified.
    uint_t time;
}
pi_evt_t;

// First event callback ready to be executed. This is processed by IRQ handlers to execute
// pending event callbacks
extern PI_MEMORY_TINY pi_evt_t *__pi_evt_ready_first;

#endif

// Offsets for assembly code
#define PI_EVT_T_CALLBACK       (0*4)
#define PI_EVT_T_NEXT           (1*4)
#define PI_EVT_T_WAITING_THREAD (2*4)
#define PI_EVT_T_THREAD         (3*4)
