// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)
//          Eric Flamand

// Free-list memory allocator. Caller must pass the size at free, so allocated blocks carry no
// metadata. Free list is singly-linked, sorted by address; coalesces with both neighbours on free.

#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/alloc.h>


pi_alloc_t __pi_mem_alloc_instances[PI_MEM_NB_ALLOCATORS];


// Min chunk = 8 B: enough to hold the free-block header and to keep all allocations 8-aligned.
#define MIN_CHUNK_SIZE 8

#define ALIGN_UP(addr, size)   (((addr) + (size) - 1) & ~((size) - 1))
#define ALIGN_DOWN(addr, size) ((addr) & ~((size) - 1))


void __pi_mem_alloc_init(pi_alloc_t *a, void *_chunk, size_t size, int memcheck_mem_id)
{
    pi_alloc_chunk_t *chunk = (pi_alloc_chunk_t *)ALIGN_UP((uintptr_t)_chunk, MIN_CHUNK_SIZE);
    a->first_free = chunk;
#if defined(CONFIG_MEMCHECK) && defined(__PLATFORM_GVSOC__)
    a->memcheck_mem_id = memcheck_mem_id;
#else
    (void)memcheck_mem_id;
#endif
    size = size - ((uintptr_t)chunk - (uintptr_t)_chunk);
    if (size > 0)
    {
        chunk->size = ALIGN_DOWN(size, MIN_CHUNK_SIZE);
        chunk->next = NULL;
    }
}


void *__pi_mem_alloc(pi_alloc_t *a, size_t size)
{
    pi_alloc_chunk_t *pt = a->first_free, *prev = NULL;

    size = ALIGN_UP(size, MIN_CHUNK_SIZE);

    while (pt && (pt->size < (int)size))
    {
        prev = pt;
        pt = pt->next;
    }

    if (!pt)
    {
        return NULL;
    }

    if (pt->size == (int)size)
    {
        if (prev)
            prev->next = pt->next;
        else
            a->first_free = pt->next;
        return (void *)pt;
    }

    // Split: hand back the head of the block, push the remainder back into the list.
    void *result = (void *)pt;
    pi_alloc_chunk_t *new_pt = (pi_alloc_chunk_t *)((char *)pt + size);
    new_pt->size = pt->size - size;
    new_pt->next = pt->next;

    if (prev)
        prev->next = new_pt;
    else
        a->first_free = new_pt;

    return result;
}


void *__pi_mem_alloc_align(pi_alloc_t *a, size_t size, size_t align)
{
    if (align < sizeof(pi_alloc_chunk_t))
        return __pi_mem_alloc(a, size);

    // Allocate enough slack to free a header before and a tail after the aligned region.
    size_t size_align = size + align + sizeof(pi_alloc_chunk_t) * 2;
    uintptr_t result = (uintptr_t)__pi_mem_alloc(a, size_align);
    if (!result)
        return NULL;

    uintptr_t result_align = (result + align - 1) & -(uintptr_t)align;
    uintptr_t headersize = result_align - result;

    if (headersize != 0)
    {
        // Need at least one chunk header worth of space before the aligned address to free it.
        if (headersize < sizeof(pi_alloc_chunk_t))
        {
            result_align += align;
            headersize = result_align - result;
        }
        __pi_mem_free(a, (void *)result, headersize);
    }

    __pi_mem_free(a, (void *)(result_align + size), size_align - headersize - size);

    return (void *)result_align;
}


void __pi_mem_free(pi_alloc_t *a, void *_chunk, size_t size)
{
    size = ALIGN_UP(size, MIN_CHUNK_SIZE);

    pi_alloc_chunk_t *chunk = (pi_alloc_chunk_t *)_chunk;
    pi_alloc_chunk_t *next = a->first_free, *prev = NULL;

    while (next && next < chunk)
    {
        prev = next;
        next = next->next;
    }

    // Coalesce with next.
    if (((char *)chunk + size) == (char *)next)
    {
        chunk->size = size + next->size;
        chunk->next = next->next;
    }
    else
    {
        chunk->size = size;
        chunk->next = next;
    }

    // Coalesce with prev.
    if (prev)
    {
        if (((char *)prev + prev->size) == (char *)chunk)
        {
            prev->size += chunk->size;
            prev->next = chunk->next;
        }
        else
        {
            prev->next = chunk;
        }
    }
    else
    {
        a->first_free = chunk;
    }
}
