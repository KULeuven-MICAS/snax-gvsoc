// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Flash-API round-trip test: erase a sector, program a known pattern, read it
// back, compare. Uses only the generic `pmsis/drivers/flash.h` interface; the
// only flash-specific step is the initial `pi_mram_device_init` binding.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <pmsis/drivers/flash.h>
#include <arch/gap/gap9/drivers/mram_implem.h>

#define TEST_ADDR   0x00001000    // start at sector 1 (leave sector 0 alone)
#define TEST_SIZE   256

static pi_mram_t mram;
static uint8_t   tx_buf[TEST_SIZE];
static uint8_t   rx_buf[TEST_SIZE];

int main(void)
{
    struct pi_mram_conf conf = {
        .size      = 0x400000,
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

    // Fill the pattern.
    for (int i = 0; i < TEST_SIZE; i++)
    {
        tx_buf[i] = (uint8_t)(i ^ 0xA5);
    }
    memset(rx_buf, 0, sizeof(rx_buf));

    printf("flash_rw: erase\n");
    pi_flash_erase(dev, TEST_ADDR, TEST_SIZE);

    printf("flash_rw: program\n");
    pi_flash_program(dev, TEST_ADDR, tx_buf, TEST_SIZE);

    printf("flash_rw: read\n");
    pi_flash_read(dev, TEST_ADDR, rx_buf, TEST_SIZE);

    pi_flash_close(dev);

    if (memcmp(tx_buf, rx_buf, TEST_SIZE) != 0)
    {
        printf("flash_rw MISMATCH\n");
        for (int i = 0; i < TEST_SIZE; i++)
        {
            if (tx_buf[i] != rx_buf[i])
            {
                printf("  [%d] wrote 0x%02x got 0x%02x\n",
                       i, tx_buf[i], rx_buf[i]);
                break;
            }
        }
        return -1;
    }

    printf("flash_rw OK\n");
    return 0;
}
