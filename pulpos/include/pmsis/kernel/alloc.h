// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <stddef.h>


enum pi_mem_allocator;


/**
 * @addtogroup mem_alloc_apis
 * @{
 */


/**
 * @brief Allocate memory.
 *
 * The allocated memory is 8-bytes aligned. The caller has to provide back the size of the
 * allocated chunk when freeing it.
 *
 * @param allocator      The allocator where to allocate memory.
 * @param size           Size in bytes of the memory to be allocated.
 *
 * @return The allocated chunk or NULL if there was not enough memory available.
 */
static inline void *pi_mem_alloc(enum pi_mem_allocator allocator, size_t size);

/**
 * @brief Free memory.
 *
 * @param allocator      The allocator where to free memory.
 * @param data           Chunk to be freed.
 * @param size           Size in bytes of the memory to be freed.
 */
static inline void pi_mem_free(enum pi_mem_allocator allocator, void *data, size_t size);

/**
 * @brief Allocate aligned memory.
 *
 * @param allocator      The allocator where to allocate memory.
 * @param size           Size in bytes of the memory to be allocated.
 * @param align          Alignment in bytes (must be a power of two).
 *
 * @return The allocated chunk or NULL if there was not enough memory available.
 */
static inline void *pi_mem_alloc_align(enum pi_mem_allocator allocator, size_t size, size_t align);

/**
 * @brief Allocate memory from the default allocator.
 */
static inline void *pi_malloc(size_t size);

/**
 * @brief Free memory previously allocated with pi_malloc().
 */
static inline void pi_free(void *chunk, size_t size);

/**
 * @}
 */


#include <pmsis/kernel/kernel.h>

#if defined(CONFIG_ALLOC_INC)
#include CONFIG_ALLOC_INC
#endif

#include <kernel/alloc.h>
