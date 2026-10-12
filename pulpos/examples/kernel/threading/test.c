// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdio.h>
#include <stdint.h>
#include <pmsis/kernel/thread.h>

#define STACK_SIZE 2048

// The busy loop sizes the run; the RTL simulation gets a much shorter one so
// that the test fits in its wall-clock budget.
#if defined(CONFIG_PLATFORM_RTL)
#define BUSY_LOOP_ITER 2000
#else
#define BUSY_LOOP_ITER 1000000
#endif

static uint8_t stack0[STACK_SIZE];
static uint8_t stack1[STACK_SIZE];

static void thread0_entry(void *arg)
{
    for (int i=0; i<10; i++)
    {
        printf("Thread 0 executing\n");

        for (volatile int j=0; j<BUSY_LOOP_ITER; j++);
    }
}

static void thread1_entry(void *arg)
{
    for (int i=0; i<10; i++)
    {
        printf("Thread 1 executing\n");

        for (volatile int j=0; j<BUSY_LOOP_ITER; j++);
    }
}

int main()
{
    pi_thread_t thread0, thread1;
    pi_evt_t event0, event1;

    printf("Entered example, creating threads\n");

    if (pi_thread_create(&thread0, "thread0", thread0_entry, NULL, 0, stack0,
            STACK_SIZE, pi_evt_sig_init(&event0))) return -1;

    if (pi_thread_create(&thread1, "thread1", thread1_entry, NULL, 0, stack1,
            STACK_SIZE, pi_evt_sig_init(&event1))) return -1;

    pi_evt_sig_wait(&event0);
    pi_evt_sig_wait(&event1);

    if (pi_thread_status_get(&thread0)) return -1;
    if (pi_thread_status_get(&thread1)) return -1;

    return 0;
}
