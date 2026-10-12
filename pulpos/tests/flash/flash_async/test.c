// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Async flash-API round-trip test: same erase/program/read cycle as flash_rw,
// but each operation uses its `_async` variant with a caller-provided
// `pi_flash_evt_t` + `pi_evt_sig_wait()` to exercise the event-completion
// path end-to-end.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <pmsis/kernel/event.h>
#include <pmsis/drivers/flash.h>
#include <arch/gap/gap9/drivers/mram_implem.h>

#define TEST_ADDR   0x00002000    // sector 2
#define TEST_SIZE   256

static pi_mram_t mram;
static uint8_t   tx_buf[TEST_SIZE];
static uint8_t   rx_buf[TEST_SIZE];

// Helper: wait-for-signal on a flash event. The caller has already initialized
// the event's pi_evt_t header as a signal via pi_evt_sig_init().
static inline void wait(pi_flash_evt_t *evt)
{
    pi_evt_sig_wait(&evt->header);
}

int main(void)
{
    struct pi_mram_conf conf = {
        .size      = 0x400000,
        .itf       = 0,
        .frequency = 25000000,
    };
    pi_mram_device_init(&mram, &conf);

    pi_device_t   *dev = (pi_device_t *)&mram;
    pi_flash_evt_t evt;

    // --- open ---
    pi_evt_sig_init(&evt.header);
    pi_flash_open_async(dev, &evt);
    wait(&evt);
    if (pi_evt_status_get(&evt.header))
    {
        printf("flash_open_async failed\n");
        return -1;
    }

    // Pattern (different from the sync test so the sector starts dirty if
    // flash_rw ran first).
    for (int i = 0; i < TEST_SIZE; i++)
    {
        tx_buf[i] = (uint8_t)(i + 0x5A);
    }
    memset(rx_buf, 0, sizeof(rx_buf));

    // --- erase ---
    printf("flash_async: erase\n");
    pi_evt_sig_init(&evt.header);
    pi_flash_erase_async(dev, TEST_ADDR, TEST_SIZE, &evt);
    wait(&evt);

    // --- program ---
    printf("flash_async: program\n");
    pi_evt_sig_init(&evt.header);
    pi_flash_program_async(dev, TEST_ADDR, tx_buf, TEST_SIZE, &evt);
    wait(&evt);

    // --- read ---
    printf("flash_async: read\n");
    pi_evt_sig_init(&evt.header);
    pi_flash_read_async(dev, TEST_ADDR, rx_buf, TEST_SIZE, &evt);
    wait(&evt);

    // --- close ---
    pi_evt_sig_init(&evt.header);
    pi_flash_close_async(dev, &evt);
    wait(&evt);

    if (memcmp(tx_buf, rx_buf, TEST_SIZE) != 0)
    {
        printf("flash_async MISMATCH\n");
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

    printf("flash_async OK\n");
    return 0;
}
