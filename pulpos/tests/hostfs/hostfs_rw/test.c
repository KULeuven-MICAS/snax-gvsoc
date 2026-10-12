// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Read/write test for the host (semi-hosting) file system. The EVK BSP mounts the workstation's
// file system at "/host", so this test exercises both directions through the standard VFS API:
//
//   1. Read  - opens a build-provided input file living on the workstation (HOSTFS_INPUT_PATH)
//              and checks its content byte-for-byte.
//   2. Write - opens an output file on the workstation for writing (HOSTFS_OUTPUT_PATH, truncate),
//              writes a payload, closes it, then reopens it read-only and reads it back, checking
//              the round-trip matches. It also stats the file to confirm the written size.
//
// Every operation is forwarded to the host by GVSoC's semi-hosting syscalls (open/read/write/
// seek/close/flen), so nothing is embedded into a flash image.

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/bsp/bsp.h>      // PI_BSP_VFS (the board VFS, with the "/host" mount point)


// Paths are injected by config.py (absolute host paths, prefixed with the "/host" mount point).
// The fallbacks keep the file self-describing but are not expected to be used.
#ifndef HOSTFS_INPUT_PATH
#define HOSTFS_INPUT_PATH "/host/tmp/hostfs_input.txt"
#endif
#ifndef HOSTFS_OUTPUT_PATH
#define HOSTFS_OUTPUT_PATH "/host/tmp/hostfs_write.bin"
#endif

// Known content of the build-provided input file (files/input.txt).
static const char INPUT_EXPECTED[] = "hostfs read/write round-trip\n";

// Payload written to the host and then read back.
static const char PAYLOAD[] = "PulpOS wrote this through hostfs.\n";


// Read a host file fully and compare it against 'expected'.
static int read_and_check(const char *path, const char *expected)
{
    pi_fs_file_t file;
    if (pi_fs_open(PI_BSP_VFS, &file, path, PI_FS_O_READ) != 0)
    {
        printf("hostfs_rw FAIL: open (read) %s\n", path);
        return 1;
    }

    size_t expected_len = strlen(expected);
    char   buf[256];
    ssize_t n = pi_fs_read(&file, buf, sizeof(buf) - 1);
    pi_fs_close(PI_BSP_VFS, &file);

    if (n < 0 || (size_t)n != expected_len)
    {
        printf("hostfs_rw FAIL: read %s returned %d, expected %u\n",
               path, (int)n, (unsigned)expected_len);
        return 1;
    }
    buf[n] = '\0';
    if (memcmp(buf, expected, expected_len) != 0)
    {
        printf("hostfs_rw FAIL: %s content mismatch\n  got:      %s  expected: %s",
               path, buf, expected);
        return 1;
    }
    return 0;
}


// Write 'payload' to a host file (truncating), then read it back and verify the round-trip.
static int write_read_back(const char *path, const char *payload)
{
    size_t len = strlen(payload);

    // --- write ---
    pi_fs_file_t file;
    if (pi_fs_open(PI_BSP_VFS, &file, path, PI_FS_O_WRITE) != 0)
    {
        printf("hostfs_rw FAIL: open (write) %s\n", path);
        return 1;
    }
    ssize_t w = pi_fs_write(&file, payload, len);
    pi_fs_close(PI_BSP_VFS, &file);
    if (w < 0 || (size_t)w != len)
    {
        printf("hostfs_rw FAIL: write %s returned %d, expected %u\n",
               path, (int)w, (unsigned)len);
        return 1;
    }

    // --- stat: the file on the host should now be exactly 'len' bytes ---
    struct pi_fs_dirent ent;
    if (pi_fs_stat(PI_BSP_VFS, path, &ent) != 0 || ent.size != len)
    {
        printf("hostfs_rw FAIL: stat %s size=%u, expected %u\n",
               path, (unsigned)ent.size, (unsigned)len);
        return 1;
    }

    // --- read back ---
    return read_and_check(path, payload);
}


int main(void)
{
    printf("hostfs_rw start\n");

    int errors = 0;

    // 1. Read an existing host file.
    errors += read_and_check(HOSTFS_INPUT_PATH, INPUT_EXPECTED);

    // 2. Write a host file and read it back.
    errors += write_read_back(HOSTFS_OUTPUT_PATH, PAYLOAD);

    if (errors == 0)
    {
        printf("hostfs_rw OK\n");
    }
    else
    {
        printf("hostfs_rw FAILED with %d error(s)\n", errors);
    }

    return errors;
}
