// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// 2D-transfer flash test.
//
// Programs a 16x16 = 256-byte buffer into flash with a deterministic
// pattern, then reads it back using `pi_flash_read_2d` with a stride
// that picks out a sub-rectangle. Validates the sub-rectangle contents
// against what we expect from the source layout. Exercises both the
// sync and the async 2D-read paths (the async variant uses a
// callback-style event to notify completion).
//
// Note: the flash API only exposes 2D *read* (program is always
// linear), so the "two directions" here are sync vs. async 2D read.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <pmsis/kernel/event.h>
#include <pmsis/drivers/flash.h>
#include <arch/gap/gap9/drivers/mram_implem.h>

extern int memcmp(const void *s1, const void *s2, size_t n);

#define BASE_ADDR  0x00006000

// Source layout: ROWS x COLS bytes laid out linearly. Programmed once
// up front; both 2D reads pick sub-rectangles out of it.
#define ROWS       16
#define COLS       16
#define SRC_SIZE   (ROWS * COLS)

// Sub-rectangle dimensions.
#define SUB_ROWS   8
#define SUB_COLS   4
#define SUB_SIZE   (SUB_ROWS * SUB_COLS)

static pi_mram_t mram;
static uint8_t   src_buf[SRC_SIZE];
static uint8_t   ref_buf[SUB_SIZE];   // expected sub-rect bytes
static uint8_t   rx_buf[SUB_SIZE];

// Build the linear pattern + the reference sub-rect for the given
// (row, col) origin.
static void build_pattern(int row0, int col0)
{
    for (int i = 0; i < SRC_SIZE; i++)
    {
        src_buf[i] = (uint8_t)((i * 7u) ^ 0xA5);
    }
    for (int r = 0; r < SUB_ROWS; r++)
    {
        memcpy(&ref_buf[r * SUB_COLS],
               &src_buf[(row0 + r) * COLS + col0],
               SUB_COLS);
    }
}

static int verify_sub(const char *label)
{
    if (memcmp(ref_buf, rx_buf, SUB_SIZE) != 0)
    {
        printf("flash_2d %s MISMATCH\n", label);
        for (int i = 0; i < SUB_SIZE; i++)
        {
            if (ref_buf[i] != rx_buf[i])
            {
                printf("  [%d] expected 0x%02x got 0x%02x\n",
                       i, ref_buf[i], rx_buf[i]);
                break;
            }
        }
        return -1;
    }
    return 0;
}

// Callback fired when the async 2D read completes.
static pi_evt_t async_done;
static void on_async_done(pi_evt_t *e)
{
    pi_evt_notify(&async_done);
}

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
        printf("flash_open failed\n");
        return -1;
    }

    // --- Plant the source matrix ---
    pi_flash_erase(dev, BASE_ADDR, SRC_SIZE);
    for (int i = 0; i < SRC_SIZE; i++) src_buf[i] = (uint8_t)((i * 7u) ^ 0xA5);
    pi_flash_program(dev, BASE_ADDR, src_buf, SRC_SIZE);

    // --- Sync 2D read: rows 4..11, cols 2..5 ---
    {
        const int row0 = 4, col0 = 2;
        build_pattern(row0, col0);
        memset(rx_buf, 0, sizeof(rx_buf));

        printf("flash_2d: sync read %dx%d sub-rect at (%d,%d)\n",
               SUB_ROWS, SUB_COLS, row0, col0);
        pi_flash_read_2d(dev,
                         BASE_ADDR + row0 * COLS + col0,
                         rx_buf,
                         /*size=*/   SUB_SIZE,
                         /*stride=*/ COLS,
                         /*length=*/ SUB_COLS);

        if (verify_sub("sync")) return -1;
    }

    // --- Async 2D read with callback completion: rows 6..13, cols 8..11 ---
    {
        const int row0 = 6, col0 = 8;
        build_pattern(row0, col0);
        memset(rx_buf, 0, sizeof(rx_buf));

        printf("flash_2d: async read %dx%d sub-rect at (%d,%d)\n",
               SUB_ROWS, SUB_COLS, row0, col0);

        pi_flash_evt_t evt;
        pi_evt_sig_init(&async_done);
        pi_evt_cb_init(&evt.header, on_async_done);

        pi_flash_read_2d_async(dev,
                               BASE_ADDR + row0 * COLS + col0,
                               rx_buf,
                               /*size=*/   SUB_SIZE,
                               /*stride=*/ COLS,
                               /*length=*/ SUB_COLS,
                               &evt);

        pi_evt_sig_wait(&async_done);

        if (verify_sub("async")) return -1;
    }

    pi_flash_close(dev);

    printf("flash_2d OK\n");
    return 0;
}
