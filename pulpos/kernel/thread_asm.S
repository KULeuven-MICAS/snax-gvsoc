// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <pmsis/kernel/kernel.h>
#include "thread_data.h"


    .section .text
    .global __pi_thread_start
    .type   __pi_thread_start, @function
__pi_thread_start:
    // Arguments:
    //     s0: thread entry function
    //     s1: thread entry function argument
    //     s2: return function which should be called when thread returns
    mv 	  a0, s1
    mv    ra, s2
    // This stub is used to start thread entry point with interrupts disabled.
    // This may not be needed anymore since context switch is now restoring mstatus.
    // TODO to be checked when threading test has been ported
    csrrsi  x0,mstatus,8
    jr    s0
    .size   __pi_thread_start, . - __pi_thread_start


	.global __pi_thread_switch
    .type   __pi_thread_switch, @function
__pi_thread_switch:
    // Arguments:
    //     a0: current thread
    //     a1: next thread

    sw    ra,  0*4(a0)
    sw    s0,  1*4(a0)
    sw    s1,  2*4(a0)
    sw    s2,  3*4(a0)
    sw    s3,  4*4(a0)
    sw    s4,  5*4(a0)
    sw    s5,  6*4(a0)
    sw    s6,  7*4(a0)
    sw    s7,  8*4(a0)
    sw    s8,  9*4(a0)
    sw    s9, 10*4(a0)
    sw    s10,11*4(a0)
    sw    s11,12*4(a0)
    sw    sp, 13*4(a0)
    csrr  a2, 0x300
    csrr  a3, 0x341
    sw    a2, 14*4(a0)
    sw    a3, 15*4(a0)

    lw    ra,  0*4(a1)
    lw    s0,  1*4(a1)
    lw    s1,  2*4(a1)
    lw    s2,  3*4(a1)
    lw    s3,  4*4(a1)
    lw    s4,  5*4(a1)
    lw    s5,  6*4(a1)
    lw    s6,  7*4(a1)
    lw    s7,  8*4(a1)
    lw    s8,  9*4(a1)
    lw    s9, 10*4(a1)
    lw    s10,11*4(a1)
    lw    s11,12*4(a1)
    lw    sp, 13*4(a1)
    lw    a2, 14*4(a1)
    lw    a3, 15*4(a1)
    csrw  0x300, a2
    csrw  0x341, a3

    ret

    .size   __pi_thread_switch, . - __pi_thread_switch
