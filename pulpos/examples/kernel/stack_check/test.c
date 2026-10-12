// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Stack-checker test: runs threads whose stacks are declared to the simulator
// (CONFIG_STACK_CHECK), with nested calls consuming a good part of each stack,
// and checks everything completes without the checker raising a false
// positive. Built with -DOVERFLOW_TEST, one thread recurses past its stack
// instead, which must be trapped by the simulator (used manually, not part of
// the testset).

#include <stdio.h>
#include <stdint.h>
#include <pmsis/kernel/thread.h>

#define STACK_SIZE 2048

static uint8_t stack0[STACK_SIZE];
static uint8_t stack1[STACK_SIZE];

// Consume stack with a recursive descent carrying a live frame each level.
// The frame is read back after the recursive call so the compiler cannot
// turn the recursion into a loop (tail-call optimization).
static int __attribute__((noinline)) consume_stack(int depth, int acc)
{
    volatile uint8_t frame[64];
    frame[0] = depth;
    if (depth == 0)
    {
        return acc + frame[0];
    }
    int result = consume_stack(depth - 1, acc + frame[0]);
    return result + frame[0];
}

static void thread_entry(void *arg)
{
    int id = (int)(long)arg;

    for (int i = 0; i < 5; i++)
    {
        // ~10 levels * ~100 bytes stays well within the 2KB stack
        int result = consume_stack(10, 0);
        printf("Thread %d iter %d result %d\n", id, i, result);
        pi_thread_yield();
    }

#ifdef OVERFLOW_TEST
    if (id == 1)
    {
        // Recurse way past the 2KB stack, the simulator must trap it
        consume_stack(1000, 0);
    }
#endif
}

int main()
{
    pi_thread_t thread0, thread1;
    pi_evt_t event0, event1;

    pi_thread_create(&thread0, "t0", thread_entry, (void *)0, 0,
        stack0, sizeof(stack0), pi_evt_sig_init(&event0));
    pi_thread_create(&thread1, "t1", thread_entry, (void *)1, 0,
        stack1, sizeof(stack1), pi_evt_sig_init(&event1));

    pi_evt_sig_wait(&event0);
    pi_evt_sig_wait(&event1);

    printf("TEST PASSED\n");

    return 0;
}
