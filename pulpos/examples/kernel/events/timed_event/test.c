// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <stdint.h>
#include <pmsis/kernel/event.h>
#include <pmsis/kernel/time.h>

// The two periods size the run, and on the RTL platform the simulated idle
// time is what costs (about 7.5 s of VCS per simulated ms), so they are scaled
// down by ten there. The counts and the 5:1 ratio are kept, so the second
// handler still fires between the first one's.
#if defined(CONFIG_PLATFORM_RTL)
#define PERIOD0 100
#define PERIOD1 500
#else
#define PERIOD0 1000
#define PERIOD1 5000
#endif

static int count0 = 20;
static int count1 = 4;
static pi_evt_t end_event;

static void delay0_handler(pi_evt_t *event)
{
    count0--;
    if (count0 > 0)
    {
        pi_evt_notify_delayed(event, PERIOD0);
    }
    else if (count1 == 0)
    {
        pi_evt_notify(&end_event);
    }
    printf("Delay 0 handler\n");
}

static void delay1_handler(pi_evt_t *event)
{
    count1--;
    if (count1 > 0)
    {
        pi_evt_notify_delayed(event, PERIOD1);
    }
    else if (count0 == 0)
    {
        pi_evt_notify(&end_event);
    }
    printf("Delay 1 handler\n");
}

int main()
{
    pi_evt_t event0, event1;

    printf("Entered example\n");

    pi_evt_sig_init(&end_event);

    pi_evt_notify_delayed(pi_evt_cb_init(&event0, delay0_handler), PERIOD0);
    pi_evt_notify_delayed(pi_evt_cb_init(&event1, delay1_handler), PERIOD1);

    pi_evt_sig_wait(&end_event);

    return 0;
}
