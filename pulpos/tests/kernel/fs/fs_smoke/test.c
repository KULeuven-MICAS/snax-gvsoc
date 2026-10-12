// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Smoke test for the read-only FS layer. Mounts the on-chip MRAM as a partitioned flash with a
// gvrun-generated readfs section containing two files (host paths in files/), opens each one,
// reads its full content, and verifies it byte-for-byte. The flash image is built and preloaded
// into the simulated MRAM by gvrun; the test is firmware-only.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/bsp/bsp.h>      // PI_BSP_VFS (the board's /mram VFS)


static int read_and_check(pi_vfs_t *vfs, const char *path, const char *expected)
{
    pi_fs_file_t file;
    if (pi_fs_open(vfs, &file, path, PI_FS_O_READ) != 0)
    {
        printf("fs_smoke FAIL: open %s\n", path);
        return 1;
    }

    struct pi_fs_dirent ent;
    if (pi_fs_stat(vfs, path, &ent) != 0)
    {
        printf("fs_smoke FAIL: stat %s\n", path);
        pi_fs_close(vfs, &file);
        return 1;
    }
    size_t expected_len = strlen(expected);
    if (ent.size != expected_len)
    {
        printf("fs_smoke FAIL: stat size for %s = %u, expected %u\n",
               path, (unsigned)ent.size, (unsigned)expected_len);
        pi_fs_close(vfs, &file);
        return 1;
    }

    char buf[256];
    ssize_t n = pi_fs_read(&file, buf, sizeof(buf) - 1);
    if (n < 0 || (size_t)n != expected_len)
    {
        printf("fs_smoke FAIL: read %s returned %d, expected %u\n",
               path, (int)n, (unsigned)expected_len);
        pi_fs_close(vfs, &file);
        return 1;
    }
    buf[n] = '\0';
    if (strcmp(buf, expected) != 0)
    {
        printf("fs_smoke FAIL: %s content mismatch\n  got:      %s\n  expected: %s",
               path, buf, expected);
        pi_fs_close(vfs, &file);
        return 1;
    }

    if (pi_fs_close(vfs, &file) != 0)
    {
        printf("fs_smoke FAIL: close %s\n", path);
        return 1;
    }
    return 0;
}


int main(void)
{
    int errors = 0;

    errors += read_and_check(PI_BSP_VFS, "/mram/readfs/hello.txt",
                             "Hello, readfs!\n");
    errors += read_and_check(PI_BSP_VFS, "/mram/readfs/world.txt",
                             "The quick brown fox jumps over the lazy dog.\n");

    // Stat for a missing file should fail without crashing.
    struct pi_fs_dirent ent;
    if (pi_fs_stat(PI_BSP_VFS, "/mram/readfs/missing.txt", &ent) == 0)
    {
        printf("fs_smoke FAIL: stat of missing file unexpectedly succeeded\n");
        errors++;
    }

    if (pi_fs_flush(PI_BSP_VFS) != 0)
    {
        printf("fs_smoke FAIL: flush\n");
        errors++;
    }

    if (errors)
    {
        printf("fs_smoke FAILED (%d errors)\n", errors);
        return -1;
    }

    printf("fs_smoke OK\n");
    return 0;
}
