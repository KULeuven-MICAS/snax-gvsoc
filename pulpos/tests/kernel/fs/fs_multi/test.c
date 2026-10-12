// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Open three files concurrently (no close between opens), interleave reads, and verify each
// file's read cursor is independent. Exercises the per-file state allocation in the readfs
// driver and confirms operations on different files do not collide on the shared FS instance.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/bsp/bsp.h>      // PI_BSP_VFS (the board's /mram VFS)


static const char *expected[3] = {
    "AAAAAAAAAAAAAAAA\n",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n",
    "cccccccc\n",
};
static const char *paths[3] = {
    "/mram/readfs/alpha.txt",
    "/mram/readfs/beta.txt",
    "/mram/readfs/gamma.txt",
};


int main(void)
{
    int errors = 0;

    pi_fs_file_t files[3];
    for (int i = 0; i < 3; i++)
    {
        if (pi_fs_open(PI_BSP_VFS, &files[i], paths[i], PI_FS_O_READ) != 0)
        {
            printf("fs_multi FAIL: open[%d]\n", i);
            return -1;
        }
    }

    // Round-robin: read 4 bytes from each file in turn until they all hit EOF.
    char accum[3][64] = { { 0 } };
    size_t pos[3] = { 0, 0, 0 };
    int    done   = 0;
    while (done != 7)
    {
        for (int i = 0; i < 3; i++)
        {
            if (done & (1 << i)) continue;
            char    chunk[5];
            ssize_t n = pi_fs_read(&files[i], chunk, 4);
            if (n < 0)
            {
                printf("fs_multi FAIL: read[%d] returned %d\n", i, (int)n);
                errors++;
                done |= (1 << i);
                continue;
            }
            if (n == 0)
            {
                done |= (1 << i);
                continue;
            }
            if (pos[i] + (size_t)n >= sizeof(accum[0]))
            {
                printf("fs_multi FAIL: file %d would overflow accumulator\n", i);
                errors++;
                done |= (1 << i);
                continue;
            }
            memcpy(&accum[i][pos[i]], chunk, (size_t)n);
            pos[i] += (size_t)n;
            accum[i][pos[i]] = '\0';
        }
    }

    for (int i = 0; i < 3; i++)
    {
        size_t expected_len = strlen(expected[i]);
        if (pos[i] != expected_len)
        {
            printf("fs_multi FAIL: file %d total %u bytes, expected %u\n",
                   i, (unsigned)pos[i], (unsigned)expected_len);
            errors++;
            continue;
        }
        if (strcmp(accum[i], expected[i]) != 0)
        {
            printf("fs_multi FAIL: file %d content mismatch\n  got:      %s\n  expected: %s",
                   i, accum[i], expected[i]);
            errors++;
        }
    }

    for (int i = 0; i < 3; i++)
    {
        if (pi_fs_close(PI_BSP_VFS, &files[i]) != 0)
        {
            printf("fs_multi FAIL: close[%d]\n", i);
            errors++;
        }
    }

    pi_fs_flush(PI_BSP_VFS);

    if (errors)
    {
        printf("fs_multi FAILED (%d errors)\n", errors);
        return -1;
    }
    printf("fs_multi OK\n");
    return 0;
}
