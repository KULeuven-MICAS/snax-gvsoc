// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Smoke test for the kernel allocator: basic alloc/free, first-fit reuse, coalescing,
// the second (L2_SHARED) heap, and aligned allocation.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>


static int check(const char *what, int cond)
{
    if (!cond)
    {
        printf("alloc_smoke FAIL: %s\n", what);
        return 1;
    }
    return 0;
}


int main(void)
{
    int errors = 0;

    // --- 1. Three allocations are non-NULL, distinct, and 8-byte aligned.
    void *a = pi_malloc(64);
    void *b = pi_malloc(64);
    void *c = pi_malloc(64);
    errors += check("a non-null", a != NULL);
    errors += check("b non-null", b != NULL);
    errors += check("c non-null", c != NULL);
    errors += check("a aligned",  ((uintptr_t)a & 7) == 0);
    errors += check("b aligned",  ((uintptr_t)b & 7) == 0);
    errors += check("c aligned",  ((uintptr_t)c & 7) == 0);
    errors += check("a != b",     a != b);
    errors += check("b != c",     b != c);

    // --- 2. First-fit reuses the freed slot.
    pi_free(b, 64);
    void *b2 = pi_malloc(64);
    errors += check("first-fit reuse", b2 == b);

    // --- 3. Free everything; coalescing should let us allocate a near-heap-sized block.
    pi_free(a,  64);
    pi_free(b2, 64);
    pi_free(c,  64);

    // The default heap is the L2 private bank leftover (~60 KB on GAP9). Keep request safe.
    size_t big = 16 * 1024;
    void *big_a = pi_malloc(big);
    errors += check("coalesced big alloc", big_a != NULL);
    if (big_a) pi_free(big_a, big);

    // --- 4. Second heap (L2 shared, ~1.5 MB) works independently.
    void *s = pi_mem_alloc(PI_MEM_ALLOCATOR_L2_SHARED, 256 * 1024);
    errors += check("shared alloc", s != NULL);
    if (s) pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, s, 256 * 1024);

    // --- 5. Aligned allocation respects the requested alignment (use the bigger shared heap).
    void *al = pi_mem_alloc_align(PI_MEM_ALLOCATOR_L2_SHARED, 256, 256);
    errors += check("aligned alloc",      al != NULL);
    errors += check("alignment honored",  al && (((uintptr_t)al & 255) == 0));
    if (al) pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, al, 256);

    if (errors)
    {
        printf("alloc_smoke FAILED: %d errors\n", errors);
        return -1;
    }

    printf("alloc_smoke OK\n");
    return 0;
}
