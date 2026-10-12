// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Minimal flash-API smoke test. The flow (open -> get_info -> close) uses
// only the generic `pmsis/drivers/flash.h` API and should work against any
// concrete flash driver. Only the initial device binding is flash-specific
// (here: MRAM).

#include <stdio.h>
#include <stddef.h>
#include <pmsis/drivers/flash.h>
#include <arch/gap/gap9/drivers/mram_implem.h>

static pi_mram_t mram;

int main(void)
{
    struct pi_mram_conf conf = {
        .size      = 0x400000,   // 4 MB
        .itf       = 0,
        .frequency = 25000000,
    };

    pi_mram_device_init(&mram, &conf);

    pi_device_t *dev = (pi_device_t *)&mram;

    if (pi_flash_open(dev))
    {
        printf("pi_flash_open failed\n");
        return -1;
    }

    size_t sector_size = 0, total_size = 0;
    pi_flash_get_info(dev, &sector_size, &total_size);
    printf("flash size=%u sector=%u\n",
           (unsigned)total_size, (unsigned)sector_size);

    pi_flash_close(dev);

    printf("flash_smoke OK\n");
    return 0;
}
