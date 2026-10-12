// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#ifdef __cplusplus
extern "C" {
#endif


#include <stddef.h>
#include <stdint.h>
#include <pmsis/kernel/kernel.h>
#include <pmsis/kernel/event.h>


/**
 * @addtogroup flash_apis
 * @{
 */

/** @brief Flash-API event.
 *
 * Used by all asynchronous flash operations. Wraps a `pi_evt_t` header plus a
 * driver-private scratch area (`priv[]`) that each concrete flash driver casts
 * as it sees fit (pending op args, status, queue links, ...).
 */
#ifndef PI_FLASH_EVT_PRIV_WORDS
#define PI_FLASH_EVT_PRIV_WORDS 6
#endif

typedef struct pi_flash_evt_s {
    pi_evt_t header;
    uint32_t priv[PI_FLASH_EVT_PRIV_WORDS];
} pi_flash_evt_t;



/** @brief Open a flash device.
 *
 * This function must be called before the flash device can be used.
 * It will do all the needed configuration to make it usable and initialize
 * the handle used to refer to this opened device when calling other functions.
 * The configuration associated to the device must specify the exact model of
 * flash which must be opened.
 *
 * @param device    A pointer to the device structure of the device to open.
 *   This structure is allocated by the called and must be kept alive until the
 *   device is closed.
 *
 * @return          0 if the operation is successfull, -1 if there was an error.
 */
ALWAYS_INLINE int pi_flash_open(pi_device_t *device);



/** @brief Close an opened flash device.
 *
 * This function can be called to close an opened flash device once it is
 * not needed anymore, in order to free all allocated resources. Once this
 * function is called, the device is not accessible anymore and must be opened
 * again before being used.
 *
 * @param device    The device structure of the device to close.
 */
ALWAYS_INLINE void pi_flash_close(pi_device_t *device);



/** @brief Enqueue a read copy to the flash (from flash to processor).
 *
 * The copy will make a transfer between the flash and one of the processor
 * memory areas.
 * The caller is blocked until the transfer is finished.
 * Depending on the chip, there may be some restrictions on the memory which
 * can be used. Check the chip-specific documentation for more details.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr  The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy
 */
ALWAYS_INLINE void pi_flash_read(
    pi_device_t *device, size_t addr, void *data, size_t size
);



/** @brief Enqueue a 2D read copy (rectangle area) to the flash (from flash to processor).
 *
 * The copy will make a transfer between the flash and one of the processor
 * memory areas.
 * The caller is blocked until the transfer is finished.
 * Depending on the chip, there may be some restrictions on the memory which
 * can be used. Check the chip-specific documentation for more details.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy.
 * @param stride      2D stride, which is the number of bytes which are added
 *   to the beginning of the current line to switch to the next one.
 * @param length      2D length, which is the number of transferred bytes after
 *   which the driver will switch to the next line.
 */
ALWAYS_INLINE void pi_flash_read_2d(
    pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length
);



/** @brief Enqueue a write copy to the flash (from processor to flash).
 *
 * The copy will make a write transfer from one of the processor memory areas
 * to the flash.
 * The locations in the flash being written should have first been erased.
 * The caller is blocked until the transfer is finished.
 * Depending on the chip, there may be some restrictions on the memory which
 * can be used. Check the chip-specific documentation for more details.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr    The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy
 */
ALWAYS_INLINE void pi_flash_program(
    pi_device_t *device, size_t addr, const void *data, size_t size
);



/** @brief Erase the whole flash.
 *
 * This will erase the entire flash. The duration of this operation may be long
 * and may be retrieved from the datasheet.
 * The caller is blocked until the operation is finished.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 */
ALWAYS_INLINE void pi_flash_erase_chip(pi_device_t *device);



/** @brief Erase a sector.
 *
 * This will erase one sector. The duration of this operation may be long
 * and may be retrieved from the datasheet.
 * The caller is blocked until the operation is finished.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 * @param addr  The address of the sector to be erased.
 */
ALWAYS_INLINE void pi_flash_erase_sector(pi_device_t *device, size_t addr);



/** @brief Erase an area in the flash.
 *
 * This will erase the specified area. The duration of this operation may be
 * long and may be retrieved from the datasheet. If the flash only supports
 * sector erasing, all the sectors partially or entirely covered by this aread
 * will be erased.
 * The caller is blocked until the operation is finished.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 * @param addr  The address of the area to be erased.
 * @param size  The size of the area to be erased.
 */
ALWAYS_INLINE void pi_flash_erase(pi_device_t *device, size_t addr, size_t size);



/** @brief Get information about the flash.
 *
 * This function can return the sector size and the size of the flash.
 *
 * @param device       The device descriptor of the flash chip on which to do
 *   the operation.
 * @param sector_size  Pointer to variable where the sector size must be set. It is set only if it
 * is not NULL.
 * @param size         Pointer to variable where the size must be set. It is set only if it
 * is not NULL.
 */
ALWAYS_INLINE void pi_flash_get_info(pi_device_t *device, size_t *sector_size, size_t *size);



/** @brief Open a flash device asynchronously.
 *
 * This function is equivalent to pi_flash_open() but done asynchronously.
 *
 * @param device    A pointer to the device structure of the device to open.
 *   This structure is allocated by the called and must be kept alive until the
 *   device is closed.
 * @param event     The event used to notify the end of transfer.
 *
 * @return          0 if the operation is successfull, -1 if there was an error.
 */
ALWAYS_INLINE void pi_flash_open_async(pi_device_t *device, pi_flash_evt_t *event);



/** @brief Close an opened flash device asynchronously.
 *
 * This function is equivalent to pi_flash_close() but done asynchronously.
 *
 * @param device    The device structure of the device to close.
 * @param event     The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_close_async(pi_device_t *device, pi_flash_evt_t *event);



/** @brief Enqueue a read copy to the flash (from flash to processor) asynchronously.
 *
 * This function is equivalent to pi_flash_read() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_read_async(
    pi_device_t *device, size_t addr, void *data, size_t size, pi_flash_evt_t *event
);



/** @brief Enqueue a read copy to the flash (from flash to processor) asynchronously from a safe
 * caller.
 *
 * This behaves exactly as pi_flash_read_async() but gives a hint to the callee that it is being
 * called from a safe caller, i.e. with interrupts disabled.
 * The callee can then use it to skip interrupt disabling/restoring for performance reasons.
 * This is particularly interesting to call this variant from interrupt handlers which are
 * frequently called.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_read_safe_async(
    pi_device_t *device, size_t addr, void *data, size_t size, pi_flash_evt_t *event
);



/** @brief Enqueue a 2D read copy (rectangle area) to the flash (from flash to processor)
 * asynchronously.
 *
 * This function is equivalent to pi_flash_read_2d() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy.
 * @param stride      2D stride, which is the number of bytes which are added
 *   to the beginning of the current line to switch to the next one.
 * @param length      2D length, which is the number of transferred bytes after
 *   which the driver will switch to the next line.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_read_2d_async(
    pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length,
    pi_flash_evt_t *event
);



/** @brief Enqueue a 2D read copy (rectangle area) to the flash (from flash to processor)
 * asynchronously from a safe caller.
 *
 * This behaves exactly as pi_flash_read_2d_async() but gives a hint to the callee that it is being
 * called from a safe caller, i.e. with interrupts disabled.
 * The callee can then use it to skip interrupt disabling/restoring for performance reasons.
 * This is particularly interesting to call this variant from interrupt handlers which are
 * frequently called.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy.
 * @param stride      2D stride, which is the number of bytes which are added
 *   to the beginning of the current line to switch to the next one.
 * @param length      2D length, which is the number of transferred bytes after
 *   which the driver will switch to the next line.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_read_2d_safe_async(
    pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length,
    pi_flash_evt_t *event
);



/** @brief Enqueue a write copy to the flash (from processor to flash) asynchronously.
 *
 * This function is equivalent to pi_flash_program() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the copy.
 * @param addr        The address of the copy in the flash.
 * @param data        The address of the copy in the processor.
 * @param size        The size in bytes of the copy.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_program_async(
    pi_device_t *device, size_t addr, const void *data, size_t size, pi_flash_evt_t *event);



/** @brief Erase the whole flash asynchronously.
 *
 * This function is equivalent to pi_flash_erase_chip() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_erase_chip_async(pi_device_t *device, pi_flash_evt_t *event);



/** @brief Erase a sector asynchronously.
 *
 * This function is equivalent to pi_flash_erase_sector() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 * @param addr        The address of the sector to be erased.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_erase_sector_async(
    pi_device_t *device, size_t addr, pi_flash_evt_t *event
);



/** @brief Erase an area in the flash asynchronously.
 *
 * This function is equivalent to pi_flash_erase() but done asynchronously.
 *
 * @param device      The device descriptor of the flash chip on which to do
 *   the operation.
 * @param addr  The address of the area to be erased.
 * @param size  The size of the area to be erased.
 * @param event       The event used to notify the end of transfer.
 */
ALWAYS_INLINE void pi_flash_erase_async(
    pi_device_t *device, size_t addr, size_t size, pi_flash_evt_t *event
);

/**
 * @}
 */

#include <drivers/flash/flash_implem.h>


#ifdef __cplusplus
}
#endif
