// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <pmsis/kernel/cycle.h>
#include <pmsis/kernel/event.h>
#include <pmsis/kernel/thread.h>
#include <pmsis/kernel/irq.h>
#include <arch/gap/gap9/kernel/perf.h>

/*
 * Benchmark: cooperative context switch cost via pi_thread_yield
 *
 * Two threads at the same priority each call pi_thread_yield() in a loop.
 * Each yield switches to the other thread. We count NB_ITER yields per thread,
 * giving NB_ITER total context switches.
 */

#define NB_ITER 200

static volatile int done;
static char stack_b[2048];

static void thread_b_entry(void *arg)
{
    while (!done)
    {
        pi_thread_yield();
    }

    pi_thread_exit(0);
}

int main()
{
    pi_thread_t thread_b;
    pi_evt_t thread_b_done;

    printf("Benchmarking cooperative context switch cost (yield)\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < 3; j++)
    {
        done = 0;

        // Create thread B at same priority as main (0)
        pi_thread_create(&thread_b, "b", thread_b_entry, NULL, 0,
                         stack_b, sizeof(stack_b), pi_evt_sig_init(&thread_b_done));

        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < NB_ITER; i++)
        {
            pi_thread_yield();
        }

        pi_perf_stop();

        // Signal thread B to exit and wait for it
        done = 1;
        pi_thread_yield();
        pi_evt_sig_wait(&thread_b_done);
    }

    pi_cycle_stop();

    // Each main yield switches to B (1 switch), then B yields back to main
    // (1 switch), so there are 2 context switches per loop iteration.
    printf("    [switch] Cycles per switch: %f\n",
        (float)pi_cycle_get32() / (NB_ITER * 2));
    printf("    [switch] Active cycles per switch: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / (NB_ITER * 2));
    printf("    [switch] Instructions per switch: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / (NB_ITER * 2));
    printf("\n");

    return 0;
}
