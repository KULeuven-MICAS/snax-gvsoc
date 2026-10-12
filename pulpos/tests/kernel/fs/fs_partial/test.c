// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Read a single readfs file in unequal chunks, span EOF, then read past the end. Verifies the
// reassembled content matches and that the FS reports 0 bytes once the cursor is at EOF.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/bsp/bsp.h>      // PI_BSP_VFS (the board's /mram VFS)


static const char *expected =
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt "
    "ut labore et dolore magna aliqua.\n";


int main(void)
{
    int errors = 0;

    pi_fs_file_t file;
    if (pi_fs_open(PI_BSP_VFS, &file, "/mram/readfs/lorem.txt", PI_FS_O_READ) != 0)
    {
        printf("fs_partial FAIL: open\n");
        return -1;
    }

    size_t expected_len = strlen(expected);
    char   buf[256];
    size_t pos = 0;
    static const size_t chunks[] = { 1, 5, 17, 33, 64, 256 };

    for (size_t i = 0; i < sizeof(chunks) / sizeof(chunks[0]); i++)
    {
        size_t want = chunks[i];
        ssize_t got = pi_fs_read(&file, &buf[pos], want);
        if (got < 0)
        {
            printf("fs_partial FAIL: read[%u] returned %d\n", (unsigned)i, (int)got);
            errors++;
            break;
        }
        if (pos + (size_t)got > expected_len)
        {
            printf("fs_partial FAIL: read[%u] overshot — pos=%u got=%d expected_len=%u\n",
                   (unsigned)i, (unsigned)pos, (int)got, (unsigned)expected_len);
            errors++;
            break;
        }
        // Each call should return min(want, remaining). Past the last useful chunk this
        // hits EOF and we expect 0.
        size_t remaining = expected_len - pos;
        size_t expect    = (want < remaining) ? want : remaining;
        if ((size_t)got != expect)
        {
            printf("fs_partial FAIL: read[%u] returned %d, expected %u (remaining=%u)\n",
                   (unsigned)i, (int)got, (unsigned)expect, (unsigned)remaining);
            errors++;
        }
        pos += (size_t)got;
    }

    if (pos != expected_len)
    {
        printf("fs_partial FAIL: short read total %u, expected %u\n",
               (unsigned)pos, (unsigned)expected_len);
        errors++;
    }
    buf[pos] = '\0';
    if (strcmp(buf, expected) != 0)
    {
        printf("fs_partial FAIL: content mismatch\n  got:      %s\n  expected: %s",
               buf, expected);
        errors++;
    }

    // Read past EOF must return 0.
    ssize_t eof = pi_fs_read(&file, buf, sizeof(buf));
    if (eof != 0)
    {
        printf("fs_partial FAIL: read past EOF returned %d\n", (int)eof);
        errors++;
    }

    pi_fs_close(PI_BSP_VFS, &file);
    pi_fs_flush(PI_BSP_VFS);

    if (errors)
    {
        printf("fs_partial FAILED (%d errors)\n", errors);
        return -1;
    }
    printf("fs_partial OK\n");
    return 0;
}
