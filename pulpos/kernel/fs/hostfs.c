// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Host (semi-hosting) file system driver.
//
// This is the "hostfs" of the classic PulpOS: instead of embedding files into a flash image,
// the application opens files that live on the workstation running the simulator. Every
// operation is forwarded to the host through the RISC-V semi-hosting interface, which GVSoC
// implements with the matching open/read/write/seek/close/flen host syscalls (see the ISS
// syscalls handler).
//
// The driver plugs into the VFS through the standard pi_vfs_mp_fs_api_t vtable, but it is
// reached through a flash-less mount point (see fs.c): there is no partition table to read and
// no flash device to open. The VFS path after the mount prefix is passed verbatim to the host
// as an absolute path, e.g. opening "/host/home/me/in.bin" reads "/home/me/in.bin" on the
// workstation.
//
// Semi-hosting is synchronous from the model's point of view (a single trapping instruction),
// so every async entry point completes inline and notifies its event immediately.

#include <stddef.h>
#include <stdint.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/kernel/event.h>
#include <kernel/fs/fs_internal.h>
#include <kernel/semihost.h>


// Semi-hosting open modes (indices into the host's open_modeflags table). The VFS now forwards
// the open flags, so read, write (truncate) and append are all reachable.
#define HOSTFS_MODE_RDONLY 0
#define HOSTFS_MODE_WRONLY 4   // O_WRONLY | O_CREAT | O_TRUNC
#define HOSTFS_MODE_APPEND 8   // O_WRONLY | O_CREAT | O_APPEND


// The driver keeps no per-mount or per-file allocation: the host file descriptor is small enough
// to stash directly in the opaque file->data slot.
static inline void __pi_fs_hostfs_set_fd(pi_fs_file_t *file, int fd)
{
    file->data = (void *)(intptr_t)fd;
}

static inline int __pi_fs_hostfs_get_fd(pi_fs_file_t *file)
{
    return (int)(intptr_t)file->data;
}


static int __pi_fs_hostfs_mode(pi_fs_mode_t flags)
{
    if (flags & PI_FS_O_APPEND)
    {
        return HOSTFS_MODE_APPEND;
    }
    if (flags & PI_FS_O_WRITE)
    {
        return HOSTFS_MODE_WRONLY;
    }
    return HOSTFS_MODE_RDONLY;
}


static void __pi_fs_hostfs_open(void *instance, pi_fs_file_t *file, const char *fs_path,
                                pi_fs_mode_t flags, pi_fs_evt_t *event)
{
    (void)instance;

    int fd = __pi_libc_semihost_open(fs_path, __pi_fs_hostfs_mode(flags));
    if (fd == -1)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return;
    }

    __pi_fs_hostfs_set_fd(file, fd);

    pi_evt_status_set(&event->header, 0);
    pi_evt_notify(&event->header);
}


static void __pi_fs_hostfs_close(void *instance, pi_fs_file_t *file, pi_fs_evt_t *event)
{
    (void)instance;
    __pi_libc_semihost_close(__pi_fs_hostfs_get_fd(file));
    pi_evt_status_set(&event->header, 0);
    pi_evt_notify(&event->header);
}


static void __pi_fs_hostfs_read(void *instance, pi_fs_file_t *file, void *dest, size_t size,
                                pi_fs_evt_t *event)
{
    (void)instance;

    // The host read syscall returns the number of bytes it could NOT serve (ARM semi-hosting
    // convention), so the count actually read is the requested size minus that remainder.
    int not_read = __pi_libc_semihost_read(__pi_fs_hostfs_get_fd(file), (uint8_t *)dest,
                                           (int)size);
    int read_size = (int)size - not_read;
    if (read_size < 0)
    {
        read_size = -1;
    }

    pi_evt_status_set(&event->header, read_size);
    pi_evt_notify(&event->header);
}


static void __pi_fs_hostfs_write(void *instance, pi_fs_file_t *file, const void *src, size_t size,
                                 pi_fs_evt_t *event)
{
    (void)instance;

    // The host write syscall returns the number of bytes it could NOT write (ARM semi-hosting
    // convention), so the count actually written is the requested size minus that remainder.
    int not_written = __pi_libc_semihost_write(__pi_fs_hostfs_get_fd(file),
                                               (uint8_t *)(uintptr_t)src, (int)size);
    int write_size = (int)size - not_written;
    if (write_size < 0)
    {
        write_size = -1;
    }

    pi_evt_status_set(&event->header, write_size);
    pi_evt_notify(&event->header);
}


static void __pi_fs_hostfs_seek(void *instance, pi_fs_file_t *file, size_t offset)
{
    (void)instance;
    __pi_libc_semihost_seek(__pi_fs_hostfs_get_fd(file), (uint_t)offset);
}


static void __pi_fs_hostfs_stat(void *instance, const char *path, struct pi_fs_dirent *entry,
                                pi_fs_evt_t *event)
{
    (void)instance;

    // No fd-less stat over semi-hosting: open the file, query its length, close it.
    int fd = __pi_libc_semihost_open(path, HOSTFS_MODE_RDONLY);
    if (fd == -1)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return;
    }

    int len = __pi_libc_semihost_flen(fd);
    __pi_libc_semihost_close(fd);

    if (len < 0)
    {
        pi_evt_status_set(&event->header, -1);
    }
    else
    {
        entry->size = (size_t)len;
        pi_evt_status_set(&event->header, 0);
    }
    pi_evt_notify(&event->header);
}


pi_vfs_mp_fs_api_t __pi_fs_hostfs_api =
{
    .open    = __pi_fs_hostfs_open,
    .close   = __pi_fs_hostfs_close,
    .read    = __pi_fs_hostfs_read,
    .write   = __pi_fs_hostfs_write,
    .seek    = __pi_fs_hostfs_seek,
    .mount   = NULL,    // flash-less: the VFS resolves host mount points without a mount step
    .unmount = NULL,
    .stat    = __pi_fs_hostfs_stat,
};


// Single shared FS instance for every host mount point. The driver is stateless (no per-mount
// data), so all host mount points can point a file at this same descriptor.
pi_vfs_mp_fs_t __pi_fs_hostfs_mp_fs =
{
    .api      = &__pi_fs_hostfs_api,
    .instance = NULL,
    .flash    = NULL,
};
