// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Verify the allocator's coalescing behavior under a checkerboard fragmentation pattern.
//
// We first probe the L2 shared heap to find exactly N — the maximum number of BLOCK_SIZE blocks
// that fit. Then we re-allocate all N (heap is fully consumed apart from a sub-block residual).
// Freeing the even-indexed blocks leaves a checkerboard: every free slot is exactly BLOCK_SIZE
// wide, with allocated odd-indexed neighbours on either side. A request for `2 * BLOCK_SIZE` must
// fail because no two free slots are adjacent. After freeing the odd-indexed ones, full
// coalescing must let a request for `N * BLOCK_SIZE` succeed.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>
#include PI_CHIP_INC(CONFIG_CHIP_FAMILY_NAME, kernel/memory_map.h)


// Block size the heap is carved into. The frees walk the free list, so the run
// is quadratic in the number of blocks: with 4 KB blocks the el1 L2 shared heap
// holds 988 of them, which the RTL platform spends minutes simulating. Bigger
// blocks there give the same checkerboard with ~60 of them; nothing in the test
// depends on the block size.
#if defined(CONFIG_PLATFORM_RTL)
#define BLOCK_SIZE  (64 * 1024)
#else
#define BLOCK_SIZE  (4 * 1024)
#endif
// Cap sized to the actual L2 shared region (+ margin) so the probe finds the
// true N on any L2 size, not just gap9's.
#define MAX_BLOCKS  (CHIP_L2_SHARED_SIZE / BLOCK_SIZE + 8)


static void *blocks[MAX_BLOCKS];


int main(void)
{
    int errors = 0;

    // Phase 1: probe the heap capacity.
    int N = 0;
    for (; N < MAX_BLOCKS; N++)
    {
        void *p = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE);
        if (!p) break;
        blocks[N] = p;
    }
    if (N < 4 || N == MAX_BLOCKS)
    {
        printf("alloc_fragment FAIL: probe returned suspicious N=%d\n", N);
        return -1;
    }
    for (int i = 0; i < N; i++)
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, blocks[i], BLOCK_SIZE);

    // Phase 2: re-allocate exactly N blocks to fully consume the heap.
    for (int i = 0; i < N; i++)
    {
        blocks[i] = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE);
        if (!blocks[i])
        {
            printf("alloc_fragment FAIL: phase 2 alloc %d failed (expected to fit)\n", i);
            return -1;
        }
    }
    // One more must fail.
    if (pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE) != NULL)
    {
        printf("alloc_fragment FAIL: phase 2 over-allocation succeeded\n");
        errors++;
    }

    // Phase 3: free even-indexed → checkerboard.
    for (int i = 0; i < N; i += 2)
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, blocks[i], BLOCK_SIZE);
        blocks[i] = NULL;
    }

    // A 2-block request must fail (no two adjacent free slots).
    void *two = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, 2 * BLOCK_SIZE);
    if (two != NULL)
    {
        printf("alloc_fragment FAIL: 2-block alloc succeeded with checkerboard heap\n");
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, two, 2 * BLOCK_SIZE);
        errors++;
    }

    // But a 1-block request must succeed (any single hole works).
    void *one = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, BLOCK_SIZE);
    if (one == NULL)
    {
        printf("alloc_fragment FAIL: cannot reuse a freed slot\n");
        errors++;
    }
    else
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, one, BLOCK_SIZE);
    }

    // Phase 4: free odd-indexed → row fully empty, expect full coalesce.
    for (int i = 1; i < N; i += 2)
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, blocks[i], BLOCK_SIZE);
        blocks[i] = NULL;
    }

    size_t total = (size_t)N * BLOCK_SIZE;
    void *big = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, total);
    if (big == NULL)
    {
        printf("alloc_fragment FAIL: heap did not coalesce after frees (%u B)\n",
               (unsigned)total);
        errors++;
    }
    else
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, big, total);
    }

    if (errors)
    {
        printf("alloc_fragment FAILED: %d errors\n", errors);
        return -1;
    }

    printf("alloc_fragment OK (N=%d)\n", N);
    return 0;
}
