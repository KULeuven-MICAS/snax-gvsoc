// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Streaming flash test using callback events.
//
// Programs and reads back a 32 KB payload split into 1 KB chunks. Each
// chunk is issued via `pi_flash_program_async` / `pi_flash_read_async`,
// and the per-chunk completion is delivered through a callback event
// (`pi_evt_cb_init`) — the callback chains the next chunk and only
// signals the main thread once the whole stream has drained.
//
// Exercises both directions (program then read) and verifies the
// round-trip end-to-end. The callback path is the interesting one:
// notifications come from the soc-event ISR context, and the test
// re-arms the same `pi_flash_evt_t` chunk-by-chunk.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>

// memcmp is defined in libc-minimal but not declared in pulpos string.h.
extern int memcmp(const void *s1, const void *s2, size_t n);
#include <pmsis/kernel/event.h>
#include <pmsis/drivers/flash.h>
#include <arch/gap/gap9/drivers/mram_implem.h>

#define BASE_ADDR  0x00004000
#define CHUNK_SIZE 256
#define NB_CHUNKS  32
#define TOTAL_SIZE (CHUNK_SIZE * NB_CHUNKS)

static pi_mram_t mram;
static uint8_t   tx_buf[TOTAL_SIZE];
static uint8_t   rx_buf[TOTAL_SIZE];

// State shared between main and the chunk-completion callback.
static struct {
    pi_device_t   *dev;
    pi_flash_evt_t chunk_evt;     // re-armed on each chunk
    pi_evt_t       done;          // signal raised when the whole stream completes
    int            chunks_left;
    size_t         offset;
    bool           is_write;
} stream;

static void chunk_done(pi_evt_t *e);

// Issue the next chunk in the current direction. Both `program_async`
// and `read_async` use the same callback event; the callback re-arms
// it before re-entering this helper.
static inline void issue_chunk(void)
{
    if (stream.is_write)
    {
        pi_flash_program_async(stream.dev,
                               BASE_ADDR + stream.offset,
                               tx_buf + stream.offset,
                               CHUNK_SIZE,
                               &stream.chunk_evt);
    }
    else
    {
        pi_flash_read_async(stream.dev,
                            BASE_ADDR + stream.offset,
                            rx_buf + stream.offset,
                            CHUNK_SIZE,
                            &stream.chunk_evt);
    }
}

// Fired (potentially from soc-event ISR context) once each chunk
// completes. Chains the next chunk or signals the main thread.
static void chunk_done(pi_evt_t *e)
{
    stream.chunks_left--;
    if (stream.chunks_left == 0)
    {
        pi_evt_notify(&stream.done);
        return;
    }
    stream.offset += CHUNK_SIZE;
    pi_evt_cb_init(&stream.chunk_evt.header, chunk_done);
    issue_chunk();
}

// Run a full streaming pass in one direction, blocking until the last
// chunk's callback signals completion.
static void stream_run(pi_device_t *dev, bool is_write)
{
    stream.dev         = dev;
    stream.chunks_left = NB_CHUNKS;
    stream.offset      = 0;
    stream.is_write    = is_write;

    pi_evt_sig_init(&stream.done);
    pi_evt_cb_init(&stream.chunk_evt.header, chunk_done);

    issue_chunk();

    pi_evt_sig_wait(&stream.done);
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

    // Distinct, deterministic pattern.
    for (int i = 0; i < TOTAL_SIZE; i++)
    {
        tx_buf[i] = (uint8_t)((i * 31u) ^ (i >> 8));
    }
    memset(rx_buf, 0, TOTAL_SIZE);

    printf("flash_stream: erase %d KB\n", TOTAL_SIZE / 1024);
    pi_flash_erase(dev, BASE_ADDR, TOTAL_SIZE);

    printf("flash_stream: program %d chunks of %d B (cb)\n",
           NB_CHUNKS, CHUNK_SIZE);
    stream_run(dev, /*is_write=*/true);

    printf("flash_stream: read %d chunks of %d B (cb)\n",
           NB_CHUNKS, CHUNK_SIZE);
    stream_run(dev, /*is_write=*/false);

    pi_flash_close(dev);

    if (memcmp(tx_buf, rx_buf, TOTAL_SIZE) != 0)
    {
        printf("flash_stream MISMATCH\n");
        for (int i = 0; i < TOTAL_SIZE; i++)
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

    printf("flash_stream OK\n");
    return 0;
}
