// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Open / read / close, then pi_fs_flush, then re-open the same file. ``pi_fs_flush`` releases
// the lazily-mounted partition table and FS instance; the second ``pi_fs_open`` must redo the
// full open path (re-read partitions, re-mount the readfs, allocate a fresh per-file state) and
// return the same content.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/bsp/bsp.h>      // PI_BSP_VFS (the board's /mram VFS)


static const char *expected = "readfs remount cycle test payload\n";


static int read_full_and_check(const char *label)
{
    pi_fs_file_t file;
    if (pi_fs_open(PI_BSP_VFS, &file, "/mram/readfs/data.txt", PI_FS_O_READ) != 0)
    {
        printf("fs_remount FAIL: %s open\n", label);
        return 1;
    }

    char    buf[128];
    ssize_t n = pi_fs_read(&file, buf, sizeof(buf) - 1);
    pi_fs_close(PI_BSP_VFS, &file);

    if (n < 0 || (size_t)n != strlen(expected))
    {
        printf("fs_remount FAIL: %s short read (%d, expected %u)\n",
               label, (int)n, (unsigned)strlen(expected));
        return 1;
    }
    buf[n] = '\0';
    if (strcmp(buf, expected) != 0)
    {
        printf("fs_remount FAIL: %s content mismatch\n  got:      %s\n  expected: %s",
               label, buf, expected);
        return 1;
    }
    return 0;
}


int main(void)
{
    int errors = 0;

    errors += read_full_and_check("first");

    if (pi_fs_flush(PI_BSP_VFS) != 0)
    {
        printf("fs_remount FAIL: flush\n");
        errors++;
    }

    // After the flush the second open must redo the full mount path. We exercise this twice to
    // cover the queue/operation-done bookkeeping for back-to-back full-mount cycles.
    errors += read_full_and_check("second");

    if (pi_fs_flush(PI_BSP_VFS) != 0)
    {
        printf("fs_remount FAIL: second flush\n");
        errors++;
    }
    errors += read_full_and_check("third");

    if (errors)
    {
        printf("fs_remount FAILED (%d errors)\n", errors);
        return -1;
    }
    printf("fs_remount OK\n");
    return 0;
}
