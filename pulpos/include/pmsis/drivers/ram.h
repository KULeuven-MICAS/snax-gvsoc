// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)
//
// Generic external-RAM driver API, mirroring the flash API
// (<pmsis/drivers/flash.h>). It provides the device-independent entry points
// (open / close / alloc / free) which dispatch to a concrete RAM driver through
// a function-pointer vtable embedded as the first member of the device object.
//
// NOTE: copy / read / write entry points are intentionally NOT provided yet.
// The external RAM is, for now, only meant to be reached directly (e.g. by the
// cluster mchan using the RAM's memory-mapped address); allocation hands out
// those addresses. Transfer helpers can be added later alongside a DMA backend.

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <pmsis/kernel/kernel.h>


/** @brief RAM driver method table.
 *
 * A concrete RAM device object embeds this as its first member so the generic
 * ``pi_ram_*`` entry points can recover it from the ``pi_device_t`` handle.
 */
typedef struct pi_ram_api_s
{
    int  (*open) (pi_device_t *device);
    void (*close)(pi_device_t *device);
    int  (*alloc)(pi_device_t *device, uint32_t *addr, uint32_t size);
    int  (*free) (pi_device_t *device, uint32_t addr, uint32_t size);
} pi_ram_api_t;


/** @brief Base RAM configuration.
 *
 * Concrete device configurations (e.g. ``struct pi_apsram_conf``) start with
 * the device-specific fields; this base type only exists for API parity with
 * the other drivers.
 */
struct pi_ram_conf
{
    pi_ram_api_t *api;
};


/** @brief Open a RAM device.
 *
 * Must be called before the device is used. For a directly-addressable RAM this
 * only sets up the host-side allocator; it does not touch the RAM itself.
 *
 * @param device  Device handle (a concrete RAM device whose first member is a
 *                ``pi_ram_api_t``).
 * @return 0 on success, -1 on error.
 */
ALWAYS_INLINE int pi_ram_open(pi_device_t *device)
{
    return ((pi_ram_api_t *)device)->open(device);
}


/** @brief Close an opened RAM device and release its host-side resources. */
ALWAYS_INLINE void pi_ram_close(pi_device_t *device)
{
    ((pi_ram_api_t *)device)->close(device);
}


/** @brief Allocate a chunk of RAM.
 *
 * @param device  The RAM device.
 * @param addr    Filled with the allocated RAM address on success.
 * @param size    Number of bytes to allocate.
 * @return 0 on success, -1 if the allocation failed.
 */
ALWAYS_INLINE int pi_ram_alloc(pi_device_t *device, uint32_t *addr, uint32_t size)
{
    return ((pi_ram_api_t *)device)->alloc(device, addr, size);
}


/** @brief Free a chunk previously returned by ``pi_ram_alloc``.
 *
 * As with the other PulpOS allocators, the size must be passed back explicitly.
 *
 * @param device  The RAM device.
 * @param addr    The RAM address to free.
 * @param size    The size that was allocated.
 * @return 0 on success, -1 on error.
 */
ALWAYS_INLINE int pi_ram_free(pi_device_t *device, uint32_t addr, uint32_t size)
{
    return ((pi_ram_api_t *)device)->free(device, addr, size);
}


#ifdef __cplusplus
}
#endif
