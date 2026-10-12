// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Drive the L2 shared heap to exhaustion, then verify it recovers fully.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>
#include PI_CHIP_INC(CONFIG_CHIP_FAMILY_NAME, kernel/memory_map.h)


#define BLOCK_SIZE   (4 * 1024)
// Cap sized to the actual L2 shared region (+ margin) so exhaustion is reached
// on any L2 size, not just gap9's.
#define MAX_BLOCKS   (CHIP_L2_SHARED_SIZE / BLOCK_SIZE + 8)


static void *blocks[MAX_BLOCKS];


int main(void)
{
    int errors = 0;

    int n = 0;
    for (; n < MAX_BLOCKS; n++)
    {
        void *p = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE);
        if (!p)
            break;
        blocks[n] = p;
    }

    if (n == 0)
    {
        printf("alloc_exhaust FAIL: no allocations succeeded\n");
        return -1;
    }

    if (n == MAX_BLOCKS)
    {
        printf("alloc_exhaust FAIL: heap appears unbounded (got %d blocks)\n", n);
        return -1;
    }

    printf("alloc_exhaust: heap held %d blocks of %d B (%d KB)\n",
           n, BLOCK_SIZE, (n * BLOCK_SIZE) / 1024);

    // After exhaustion, further allocs must keep returning NULL.
    if (pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE) != NULL)
    {
        printf("alloc_exhaust FAIL: alloc succeeded after exhaustion\n");
        errors++;
    }

    // Free everything.
    for (int i = 0; i < n; i++)
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, blocks[i], BLOCK_SIZE);

    // The heap should coalesce back to its original capacity. Allocating the same total in one
    // shot proves it.
    size_t total = (size_t)n * BLOCK_SIZE;
    void *big = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, total);
    if (big == NULL)
    {
        printf("alloc_exhaust FAIL: heap did not coalesce back (%u B unavailable)\n",
               (unsigned)total);
        errors++;
    }
    else
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, big, total);
    }

    if (errors)
    {
        printf("alloc_exhaust FAILED: %d errors\n", errors);
        return -1;
    }

    printf("alloc_exhaust OK\n");
    return 0;
}
