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
 * Benchmark: preemptive context switch cost
 *
 * Main (priority 0) and a second thread (same priority 0) are round-robined
 * by the preemption timer. The second thread only executes WFI in a tight
 * loop, contributing zero active-cycle overhead. Main executes WFI, wakes on
 * the preemption switch, decrements a counter and goes back to WFI. When the
 * counter reaches zero main falls through and prints the results.
 *
 * Because both threads spend all their time sleeping, the only active cycles
 * are the context-switch overhead: timer IRQ entry, scheduler pick, context
 * save/restore, and main's short counter check between WFIs.
 */

// Each iteration costs two 1 ms slices of simulated time, and the RTL platform
// pays about 7.5 s of VCS per simulated ms, so it gets two round-trips in a
// single pass instead of three passes of three.
#if defined(CONFIG_PLATFORM_RTL)
#define NB_ITER 2
#define NB_PASS 1
#else
#define NB_ITER 200
#define NB_PASS 3
#endif

static volatile int running;

static char stack[2048];

static void thread_entry(void *arg)
{
    while (running)
    {
        asm volatile ("wfi");
    }

    pi_thread_exit(0);
}

int main()
{
    pi_thread_t thread;
    pi_evt_t event;

    printf("Benchmarking preemptive context switch cost\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));

    for (int j = 0; j < NB_PASS; j++)
    {
        running = 1;

        pi_thread_create(&thread, "t", thread_entry, NULL, 0,
                         stack, sizeof(stack), pi_evt_sig_init(&event));

        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < NB_ITER; i++)
        {
            asm volatile ("wfi");
        }

        pi_perf_stop();

        // Tell the other thread to exit and wait for it.
        running = 0;
        pi_evt_sig_wait(&event);
    }

    // Each main WFI iteration is a round-trip: main->thread then thread->main,
    // so there are 2 context switches per iteration.
    printf("    [preempt] Active cycles per switch: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / (NB_ITER * 2));
    printf("    [preempt] Instructions per switch: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / (NB_ITER * 2));
    printf("\n");

    return 0;
}
