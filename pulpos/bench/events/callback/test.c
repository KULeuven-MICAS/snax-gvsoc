// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <pmsis/kernel/cycle.h>
#include <pmsis/kernel/event.h>
#include <pmsis/kernel/irq.h>
#include <arch/gap/gap9/kernel/perf.h>

/*
 * Benchmark 0
 * This estimates the cost of an interrupt handler notifying an event callback while the core
 * is active, which leads to full interrupt save/restore.
 * For that the test iterates and triggers a SW interrupt at aech iteration, which immediately
 * executes the IRQ handler while core is still executing instructions.
 */

#define BENCH_0_NB_ITER 100

static void bench_0_irq_handler(void *arg) {
    pi_evt_t *evt = (pi_evt_t *)arg;
    pi_evt_notify_unsafe(evt);
}

static void bench_0_evt_callback(pi_evt_t *evt) {
}

static void bench_0_cb_while_active() {
    pi_evt_t event;

    printf("Benchmarking event callback while core is active\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));

    pi_cycle_start();
    pi_perf_start();

    // Register our callback on IRQ 1 as IRQ 0 is for exceptions
    pi_irq_handler_set(1, bench_0_irq_handler, (void *)&event);
    pi_irq_enable(1);

    for (int j=0; j<3; j++) {
        pi_cycle_reset();
        pi_perf_reset();

        for (int i=0; i<BENCH_0_NB_ITER; i++) {
            // Register the callback at each iteration to also benchmark the cost of initializing
            // the callback
            pi_evt_cb_init(&event, bench_0_evt_callback);
            pi_irq_set(1);
        }
    }

    pi_perf_stop();
    pi_cycle_stop();

    printf("    [active] Cycles per interrupt: %f\n", (float)pi_cycle_get32() / BENCH_0_NB_ITER);
    printf("    [active] Active cycles per interrupt: %f\n", (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / BENCH_0_NB_ITER);
    printf("    [active] Instructions per interrupt: %f\n", (float)pi_perf_read(PI_PERF_INSTR) / BENCH_0_NB_ITER);
    printf("\n");
}

/*
 * Benchmark 1
 * This estimates the cost of an interrupt handler notifying an event callback while the core
 * is sleeping, which leads to reduced interrupt save/restore.
 * For that the test locks interrupts and wait for an end event, which means the IRQ handler is
 * delayed until the point where the core switched to fast IRQ handling and sleeps.
 */

#define BENCH_1_NB_ITER 200

static int bench_1_iter;
static pi_evt_t bench_1_end_event;

static void bench_1_irq_handler(void *arg) {
    pi_evt_t *evt = (pi_evt_t *)arg;
    pi_evt_notify_unsafe(evt);
}

static void bench_1_evt_callback(pi_evt_t *evt) {
    bench_1_iter--;
    if (bench_1_iter == 0) {
        pi_evt_notify(&bench_1_end_event);
    } else {
        pi_evt_cb_init(evt, bench_1_evt_callback);
        pi_irq_set(1);
    }
}

static void bench_1_cb_while_idle() {
    pi_evt_t event;

    printf("Benchmarking event callback while core is sleeping\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));

    pi_cycle_start();
    pi_perf_start();

    pi_irq_handler_set(1, bench_1_irq_handler, (void *)&event);
    pi_irq_enable(1);
    int irq_state = pi_irq_lock();

    for (int j=0; j<3; j++) {
        pi_cycle_reset();
        pi_perf_reset();

        // Fully initialize our iteration here since the interrupt will iterates alone
        bench_1_iter = BENCH_1_NB_ITER;
        pi_evt_sig_init(&bench_1_end_event);
        pi_evt_cb_init(&event, bench_1_evt_callback);
        pi_irq_set(1);
        pi_evt_sig_wait(&bench_1_end_event);
    }

    pi_perf_stop();
    pi_cycle_stop();
    pi_irq_unlock(irq_state);

    printf("    [idle] Cycles per interrupt: %f\n", (float)pi_cycle_get32() / BENCH_1_NB_ITER);
    printf("    [idle] Active cycles per interrupt: %f\n", (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / BENCH_1_NB_ITER);
    printf("    [idle] Instructions per interrupt: %f\n", (float)pi_perf_read(PI_PERF_INSTR) / BENCH_1_NB_ITER);
    printf("\n");
}


int main()
{
    bench_0_cb_while_active();
    bench_1_cb_while_idle ();

    return 0;
}
