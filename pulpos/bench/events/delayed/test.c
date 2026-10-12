// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <pmsis/kernel/cycle.h>
#include <pmsis/kernel/event.h>
#include <pmsis/kernel/time.h>
#include <pmsis/kernel/irq.h>
#include <arch/gap/gap9/kernel/perf.h>

// The list-operation benchmarks below are O(list length) per iteration and the
// firing ones spend NB * delay of simulated time, both of which the RTL
// platform pays for heavily (about 7.5 s of VCS per simulated ms). It gets
// shorter lists and a single measured pass; the reported per-iteration figures
// are then of a 20-deep list, so they are not comparable with the other
// platforms' 100-deep ones.
#if defined(CONFIG_PLATFORM_RTL)
#define NB_ITER 20
#define NB_PASS 1
#else
#define NB_ITER 100
#define NB_PASS 3
#endif
#define DELAY_US 1000000

static pi_evt_t events[NB_ITER];

static void empty_callback(pi_evt_t *evt) {}

/*
 * Benchmark 0: single push cost
 * Measures the cost of pi_evt_notify_delayed() when the timer list is empty
 * (only one event scheduled at a time). This gives the best-case push cost
 * without any list traversal.
 */
static void bench_push_single()
{
    pi_evt_t event;

    printf("Benchmarking delayed event single push cost\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < NB_PASS; j++)
    {
        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < NB_ITER; i++)
        {
            pi_evt_notify_delayed(
                pi_evt_cb_init(&event, empty_callback), DELAY_US);
            pi_evt_timed_cancel(&event);
        }

        pi_perf_stop();
    }

    pi_cycle_stop();

    printf("    [push_single] Cycles per iteration: %f\n",
        (float)pi_cycle_get32() / NB_ITER);
    printf("    [push_single] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / NB_ITER);
    printf("    [push_single] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / NB_ITER);
    printf("\n");
}

/*
 * Benchmark 1: bulk push cost
 * Measures the cost of pi_evt_notify_delayed() when scheduling many events
 * into an already-populated timer list. Each successive push must traverse
 * further into the list, giving the amortized cost.
 */
static void bench_push()
{
    printf("Benchmarking delayed event push cost\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < NB_PASS; j++)
    {
        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < NB_ITER; i++)
        {
            pi_evt_notify_delayed(
                pi_evt_cb_init(&events[i], empty_callback), DELAY_US);
        }

        pi_perf_stop();

        for (int i = 0; i < NB_ITER; i++)
            pi_evt_timed_cancel(&events[i]);
    }

    pi_cycle_stop();

    printf("    [push] Cycles per iteration: %f\n",
        (float)pi_cycle_get32() / NB_ITER);
    printf("    [push] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / NB_ITER);
    printf("    [push] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / NB_ITER);
    printf("\n");
}

/*
 * Benchmark 1: cancel cost (in order)
 * Schedules all events, then measures the cost of cancelling them in the
 * same order they were pushed (first pushed = first cancelled).
 * This cancels from the head of the timer list.
 */
static void bench_cancel_ordered()
{
    printf("Benchmarking delayed event cancel cost (in order)\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < NB_PASS; j++)
    {
        // Schedule all events outside the measurement
        for (int i = 0; i < NB_ITER; i++)
        {
            pi_evt_notify_delayed(
                pi_evt_cb_init(&events[i], empty_callback), DELAY_US);
        }

        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < NB_ITER; i++)
            pi_evt_timed_cancel(&events[i]);

        pi_perf_stop();
    }

    pi_cycle_stop();

    printf("    [cancel_ordered] Cycles per iteration: %f\n",
        (float)pi_cycle_get32() / NB_ITER);
    printf("    [cancel_ordered] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / NB_ITER);
    printf("    [cancel_ordered] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / NB_ITER);
    printf("\n");
}

/*
 * Benchmark 2: cancel cost (reverse order)
 * Schedules all events, then measures the cost of cancelling them in
 * reverse order (last pushed = first cancelled).
 * This cancels from the tail of the timer list.
 */
static void bench_cancel_reverse()
{
    printf("Benchmarking delayed event cancel cost (reverse order)\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < NB_PASS; j++)
    {
        // Schedule all events outside the measurement
        for (int i = 0; i < NB_ITER; i++)
        {
            pi_evt_notify_delayed(
                pi_evt_cb_init(&events[i], empty_callback), DELAY_US);
        }

        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = NB_ITER - 1; i >= 0; i--)
            pi_evt_timed_cancel(&events[i]);

        pi_perf_stop();
    }

    pi_cycle_stop();

    printf("    [cancel_reverse] Cycles per iteration: %f\n",
        (float)pi_cycle_get32() / NB_ITER);
    printf("    [cancel_reverse] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / NB_ITER);
    printf("    [cancel_reverse] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / NB_ITER);
    printf("\n");
}

/*
 * Benchmark 3: fire + re-schedule cost
 * Measures the full cycle of a delayed event firing and being re-scheduled
 * from its own callback. This is the typical periodic timer pattern.
 * The callback re-enqueues the event with pi_evt_notify_delayed, so each
 * iteration includes: timer IRQ, callback dispatch, re-schedule.
 * The core sleeps between fires, so active_cycles isolates the overhead.
 */

#if defined(CONFIG_PLATFORM_RTL)
#define FIRE_NB_ITER 20
#else
#define FIRE_NB_ITER 200
#endif
#define FIRE_DELAY_US 10

static pi_evt_t fire_end_event;
static int fire_count;

static void fire_callback(pi_evt_t *evt)
{
    fire_count--;
    if (fire_count == 0)
        pi_evt_notify(&fire_end_event);
    else
        pi_evt_notify_delayed(pi_evt_cb_init(evt, fire_callback), FIRE_DELAY_US);
}

static void bench_fire()
{
    pi_evt_t event;

    printf("Benchmarking delayed event fire + re-schedule cost\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    int irq_state = pi_irq_lock();

    for (int j = 0; j < NB_PASS; j++)
    {
        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        fire_count = FIRE_NB_ITER;
        pi_evt_sig_init(&fire_end_event);
        pi_evt_notify_delayed(pi_evt_cb_init(&event, fire_callback), FIRE_DELAY_US);
        pi_evt_sig_wait(&fire_end_event);

        pi_perf_stop();
    }

    pi_cycle_stop();
    pi_irq_unlock(irq_state);

    printf("    [fire] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / FIRE_NB_ITER);
    printf("    [fire] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / FIRE_NB_ITER);
    printf("\n");
}

/*
 * Benchmark 4: signal wait on delayed event
 * Measures the cost of scheduling a delayed event with a signal notification
 * and waiting for it with pi_evt_sig_wait. This is the typical blocking delay
 * pattern (e.g. pi_time_wait_us style). Each iteration: init signal event,
 * schedule delayed notification, wait for signal.
 * Active cycles measure the CPU overhead; total cycles include the sleep.
 */

#if defined(CONFIG_PLATFORM_RTL)
#define WAIT_NB_ITER 20
#else
#define WAIT_NB_ITER 200
#endif
#define WAIT_DELAY_US 10

static void bench_signal_wait()
{
    pi_evt_t event;

    printf("Benchmarking delayed event signal wait cost\n");

    pi_perf_enable((1 << PI_PERF_ACTIVE_CYCLES) | (1 << PI_PERF_INSTR));
    pi_cycle_start();

    for (int j = 0; j < NB_PASS; j++)
    {
        pi_cycle_reset();
        pi_perf_reset();
        pi_perf_start();

        for (int i = 0; i < WAIT_NB_ITER; i++)
        {
            pi_evt_sig_init(&event);
            pi_evt_notify_delayed(&event, WAIT_DELAY_US);
            pi_evt_sig_wait(&event);
        }

        pi_perf_stop();
    }

    pi_cycle_stop();

    printf("    [signal_wait] Active cycles per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_ACTIVE_CYCLES) / WAIT_NB_ITER);
    printf("    [signal_wait] Instructions per iteration: %f\n",
        (float)pi_perf_read(PI_PERF_INSTR) / WAIT_NB_ITER);
    printf("\n");
}

int main()
{
    bench_push_single();
    bench_push();
    bench_cancel_ordered();
    bench_cancel_reverse();
    bench_fire();
    bench_signal_wait();

    return 0;
}
