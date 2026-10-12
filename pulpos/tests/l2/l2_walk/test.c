// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Linear walk over all available L2 memory: probes both the L2 priv heap (~60 KB after BSS) and
// the L2 shared heap (~1.5 MB), then sweeps each with NB_ITER iterations of linearly increasing
// access counts. Iteration k writes/reads `k * step` consecutive 32-bit words, where `step` is
// sized so the last iteration covers the full buffer. The shared sweep crosses every region; the
// priv sweep straddles the priv0/priv1 bank boundary as long as the heap is bigger than 32 KB.
//
// Each word is written as `(iter << 24) | index` so the readback distinguishes stale reads
// (wrong upper byte) from address aliasing (wrong index).

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>


#define NB_ITER 8

// Largest buffers probed; the RTL simulation walks much smaller ones so that
// the test fits in its wall-clock budget.
#if defined(CONFIG_PLATFORM_RTL)
#define SHARED_START (8 * 1024)
#define SHARED_MIN   (4 * 1024)
#define PRIV_START   (4 * 1024)
#else
#define SHARED_START (2 * 1024 * 1024)
#define SHARED_MIN   (64 * 1024)
#define PRIV_START   (64 * 1024)
#endif


static size_t probe_max_alloc(enum pi_mem_allocator alloc, size_t start, size_t shrink_step,
                              size_t min_size, void **out_buf)
{
    size_t s = start;
    void *p = NULL;
    while (s >= min_size)
    {
        p = pi_mem_alloc(alloc, s);
        if (p) break;
        s -= shrink_step;
    }
    *out_buf = p;
    return p ? s : 0;
}


static int walk_buffer(const char *name, volatile uint32_t *p, int max_words)
{
    int errors = 0;
    uint64_t total_accesses = 0;
    int step_words = (max_words + NB_ITER - 1) / NB_ITER;

    printf("%s: words=%d step=%d\n", name, max_words, step_words);

    for (int k = 1; k <= NB_ITER; k++)
    {
        int n_words = k * step_words;
        if (n_words > max_words) n_words = max_words;

        for (int i = 0; i < n_words; i++)
            p[i] = ((uint32_t)k << 24) | (uint32_t)i;

        for (int i = 0; i < n_words; i++)
        {
            uint32_t got = p[i];
            uint32_t expect = ((uint32_t)k << 24) | (uint32_t)i;
            if (got != expect)
            {
                if (errors < 5)
                {
                    printf("%s MISMATCH: iter=%d idx=%d got=0x%08x expected=0x%08x\n",
                           name, k, i, got, expect);
                }
                errors++;
            }
        }

        total_accesses += 2 * (uint64_t)n_words;
    }

    printf("%s: total accesses %u (writes+reads)\n", name, (unsigned)total_accesses);
    return errors;
}


int main(void)
{
    int errors = 0;

    // L2 SHARED — probe largest contiguous block, sweep it.
    void *shared_buf = NULL;
    size_t shared_size = probe_max_alloc(PI_MEM_ALLOCATOR_L2_SHARED,
                                         /*start=*/SHARED_START,
                                         /*shrink_step=*/4 * 1024,
                                         /*min_size=*/SHARED_MIN,
                                         &shared_buf);
    if (!shared_buf)
    {
        printf("l2_walk FAIL: could not allocate any L2 shared buffer\n");
        return -1;
    }
    printf("l2_walk: shared buf=%p size=%u\n", shared_buf, (unsigned)shared_size);
    errors += walk_buffer("shared", (volatile uint32_t *)shared_buf, shared_size / 4);
    pi_mem_free(PI_MEM_ALLOCATOR_L2_SHARED, shared_buf, shared_size);

    // L2 PRIV — same probe + sweep on the default heap.
    void *priv_buf = NULL;
    size_t priv_size = probe_max_alloc(PI_MEM_ALLOCATOR_DEFAULT,
                                       /*start=*/PRIV_START,
                                       /*shrink_step=*/4 * 1024,
                                       /*min_size=*/4 * 1024,
                                       &priv_buf);
    if (!priv_buf)
    {
        printf("l2_walk FAIL: could not allocate any L2 priv buffer\n");
        return -1;
    }
    printf("l2_walk: priv buf=%p size=%u\n", priv_buf, (unsigned)priv_size);
    errors += walk_buffer("priv", (volatile uint32_t *)priv_buf, priv_size / 4);
    pi_free(priv_buf, priv_size);

    if (errors)
    {
        printf("l2_walk FAILED (%d mismatches)\n", errors);
        return -1;
    }

    printf("l2_walk OK\n");
    return 0;
}
