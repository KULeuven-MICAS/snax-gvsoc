// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once


#include <stddef.h>
#include <pmsis/kernel/kernel.h>
#include <pmsis/kernel/event.h>


// TODO
typedef struct pi_device_s
{
} pi_device_t;


typedef struct
{
    void (*open)(pi_device_t *device, pi_flash_evt_t *event);
    void (*close)(pi_device_t *device, pi_flash_evt_t *event);
    void (*read_2d)(pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length, pi_flash_evt_t *event);
    void (*program)(pi_device_t *device, size_t addr, const void *data, size_t size, pi_flash_evt_t *event);
    void (*erase_chip)(pi_device_t *device, pi_flash_evt_t *event);
    void (*erase_sector)(pi_device_t *device, size_t addr, pi_flash_evt_t *event);
    void (*erase)(pi_device_t *device, size_t addr, size_t size, pi_flash_evt_t *event);
    void (*get_info)(pi_device_t *device, size_t *sector_size, size_t *size);
} pi_flash_api_t;


typedef struct
{
    pi_flash_api_t api;
    pi_device_t instance;
} pi_flash_device_t;



ALWAYS_INLINE int pi_flash_open(pi_device_t *device)
{
    pi_flash_evt_t event;
    pi_flash_open_async(device, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
    return pi_evt_status_get(&event.header);
}



ALWAYS_INLINE void pi_flash_open_async(pi_device_t *device, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.open(&flash->instance, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_close(pi_device_t *device)
{
    pi_flash_evt_t event;
    pi_flash_close_async(device, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_close_async(pi_device_t *device, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.close(&flash->instance, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_read(pi_device_t *device, size_t addr, void *data, size_t size)
{
    pi_flash_evt_t event;
    pi_flash_read_async(device, addr, data, size, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_read_async(pi_device_t *device, size_t addr, void *data, size_t size, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.read_2d(&flash->instance, addr, data, size, size, size, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_read_safe_async(pi_device_t *device, size_t addr, void *data, size_t size, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    flash->api.read_2d(&flash->instance, addr, data, size, size, size, event);
}



ALWAYS_INLINE void pi_flash_read_2d(pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length)
{
    pi_flash_evt_t event;
    pi_flash_read_2d_async(device, addr, data, size, stride, length, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_read_2d_async(pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.read_2d(&flash->instance, addr, data, size, stride, length, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_read_2d_safe_async(pi_device_t *device, size_t addr, void *data, size_t size, size_t stride, size_t length, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    flash->api.read_2d(&flash->instance, addr, data, size, stride, length, event);
}



ALWAYS_INLINE void pi_flash_program(pi_device_t *device, size_t addr, const void *data, size_t size)
{
    pi_flash_evt_t event;
    pi_flash_program_async(device, addr, data, size, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}




ALWAYS_INLINE void pi_flash_program_safe(pi_device_t *device, size_t addr, const void *data, size_t size, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    flash->api.program(&flash->instance, addr, data, size, event);
}



ALWAYS_INLINE void pi_flash_program_async(pi_device_t *device, size_t addr, const void *data, size_t size, pi_flash_evt_t *event)
{
    int irq = pi_irq_lock();
    pi_flash_program_safe(device, addr, data, size, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_erase(pi_device_t *device, size_t addr, size_t size)
{
    pi_flash_evt_t event;
    pi_flash_erase_async(device, addr, size, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_erase_safe(pi_device_t *device, size_t addr, size_t size, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    flash->api.erase(&flash->instance, addr, size, event);
}

ALWAYS_INLINE void pi_flash_erase_async(pi_device_t *device, size_t addr, size_t size, pi_flash_evt_t *event)
{
    int irq = pi_irq_lock();
    pi_flash_erase_safe(device, addr, size, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_erase_chip(pi_device_t *device)
{
    pi_flash_evt_t event;
    pi_flash_erase_chip_async(device, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_erase_chip_async(pi_device_t *device, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.erase_chip(&flash->instance, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_erase_sector(pi_device_t *device, size_t addr)
{
    pi_flash_evt_t event;
    pi_flash_erase_sector_async(device, addr, (pi_flash_evt_t *)pi_evt_sig_init(&event.header));
    pi_evt_sig_wait(&event.header);
}



ALWAYS_INLINE void pi_flash_erase_sector_async(pi_device_t *device, size_t addr, pi_flash_evt_t *event)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    int irq = pi_irq_lock();
    flash->api.erase_sector(&flash->instance, addr, event);
    pi_irq_unlock(irq);
}



ALWAYS_INLINE void pi_flash_get_info(pi_device_t *device, size_t *sector_size, size_t *size)
{
    pi_flash_device_t *flash = (pi_flash_device_t *)device;
    flash->api.get_info(&flash->instance, sector_size, size);
}
