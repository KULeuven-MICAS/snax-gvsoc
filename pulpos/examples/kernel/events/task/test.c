// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <stdint.h>
#include <pmsis/kernel/event.h>
#include <pmsis/kernel/time.h>

// The delayed-event period/count and the busy loops size the run; the RTL
// simulation gets shorter ones so that the test fits in its wall-clock budget.
// There, what costs is the CPU work the RTL has to simulate, mostly the busy
// loops (90% of the instructions with 2000 iterations and 1 ms delays, 8 min in
// CI); the delays shrink with them so that the tasks still overlap the delayed
// events.
#if defined(CONFIG_PLATFORM_RTL)
#define PERIOD0 100
#define NB_DELAYS 10
#define BUSY_LOOP_ITER 500
#else
#define PERIOD0 10000
#define NB_DELAYS 50
#define BUSY_LOOP_ITER 1000000
#endif

static int count0 = NB_DELAYS;
static pi_evt_t end_event;

static void delay_handler(pi_evt_t *event)
{
    count0--;
    if (count0 > 0)
    {
        pi_evt_notify_delayed(event, PERIOD0);
    }
    else
    {
        pi_evt_notify(&end_event);
    }
    printf("Delay 0 handler\n");
}

static void task0_handler(pi_evt_t *event)
{
    for (int i=0; i<10; i++)
    {
        printf("Task 0 executing\n");

        for (volatile int j=0; j<BUSY_LOOP_ITER; j++);
    }
}

static void task1_handler(pi_evt_t *event)
{
    for (int i=0; i<10; i++)
    {
        printf("Task 1 executing\n");

        for (volatile int j=0; j<BUSY_LOOP_ITER; j++);
    }
}

int main()
{
    pi_evt_t task0_event, task1_event, delayed_event;

    printf("Entered example\n");

    pi_evt_sig_init(&end_event);

    pi_evt_notify(pi_evt_task_init(&task0_event, task0_handler, NULL));

    pi_evt_notify(pi_evt_task_init(&task1_event, task1_handler, NULL));

    pi_evt_notify_delayed(pi_evt_cb_init(&delayed_event, delay_handler), PERIOD0);

    pi_evt_sig_wait(&end_event);

    return 0;
}
