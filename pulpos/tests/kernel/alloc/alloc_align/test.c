// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Sweep pi_mem_alloc_align across power-of-two alignments. Each iteration allocates and frees;
// after the sweep, a heap-sized allocation must still succeed (no leaks / no surviving
// fragmentation).
//
// Allocations stay in the L2 shared heap but are bounded so we don't touch beyond ~64 KB. gvsoc's
// shared model has gaps in regions 3/7/11 that fault on access, so we keep well clear.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>


static const size_t alignments[] = { 16, 32, 64, 128, 256, 512, 1024, 2048 };
#define NB_ALIGNMENTS  (sizeof(alignments) / sizeof(alignments[0]))

#define ITER_PER_ALIGN  4
#define PAYLOAD_SIZE    256

// A 64 KB single-shot allocation lands well inside region 0 of the shared bank.
#define WITNESS_SIZE    (64 * 1024)


int main(void)
{
    int errors = 0;

    // Witness allocation before the sweep.
    void *witness = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, WITNESS_SIZE);
    if (!witness)
    {
        printf("alloc_align FAIL: shared heap too small for %d B witness\n", WITNESS_SIZE);
        return -1;
    }
    pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, witness, WITNESS_SIZE);

    // Sweep every alignment, ITER_PER_ALIGN times each.
    for (size_t a = 0; a < NB_ALIGNMENTS; a++)
    {
        size_t align = alignments[a];

        for (int it = 0; it < ITER_PER_ALIGN; it++)
        {
            void *p = pi_mem_alloc_align(PI_MEM_ALLOCATOR_L2_SHARED, PAYLOAD_SIZE, align);
            if (!p)
            {
                printf("alloc_align FAIL: align=%u iter=%d returned NULL\n",
                       (unsigned)align, it);
                errors++;
                continue;
            }
            if (((uintptr_t)p & (align - 1)) != 0)
            {
                printf("alloc_align FAIL: align=%u, ptr=%p not aligned\n",
                       (unsigned)align, p);
                errors++;
            }
            pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, p, PAYLOAD_SIZE);
        }
    }

    // Witness allocation after the sweep — proves the heap coalesced back.
    witness = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, WITNESS_SIZE);
    if (!witness)
    {
        printf("alloc_align FAIL: heap did not coalesce after sweep\n");
        errors++;
    }
    else
    {
        pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, witness, WITNESS_SIZE);
    }

    if (errors)
    {
        printf("alloc_align FAILED: %d errors\n", errors);
        return -1;
    }

    printf("alloc_align OK\n");
    return 0;
}
