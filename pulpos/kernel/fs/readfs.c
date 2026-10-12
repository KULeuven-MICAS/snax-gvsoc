// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Read-only file system driver matching the gvrun ``readfs`` section layout
// (gvrun/python/gvrun/flash/sections/readfs.py):
//
//     uint64 fs_size              // total header area size (header + all per-file headers)
//     uint32 nb_files
//     repeat nb_files:
//         uint32 offset           // file data offset, relative to the partition start
//         uint32 file_size
//         uint32 name_len         // includes null terminator
//         char   name[name_len]
//     <file data, packed>
//
// The mount step reads the entire header area into RAM in one chunk and then walks it on each
// open / stat. ``read`` is a passthrough to ``pi_flash_read_async`` against the user event.

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/kernel/alloc.h>
#include <pmsis/kernel/event.h>
#include <kernel/fs/fs_internal.h>


#ifndef container_of
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))
#endif


typedef struct
{
    uint32_t addr;          // absolute address of the file data in the flash
    uint32_t offset;        // current read position within the file
    uint32_t size;          // total file size
    pi_device_t *flash;
} pi_fs_readfs_file_t;


typedef struct
{
    pi_flash_evt_t flash_evt;       // for chained flash ops during mount
    pi_device_t   *flash;
    uint32_t       partition_offset;
    uint64_t       fs_size;
    uint32_t       nb_files;
    uint32_t       _pad;
    uint8_t       *header;          // header[0..fs_size-1]
    pi_fs_evt_t   *caller_event;    // VFS event notified on mount completion
} pi_fs_readfs_t;


// On-disk per-file descriptor (matches the gvrun layout). Packed: ``name`` directly follows the
// three uint32 fields with no alignment padding; the next descriptor sits ``name_len`` bytes
// past the start of ``name``.
typedef struct
{
    uint32_t offset;
    uint32_t file_size;
    uint32_t name_len;
    char     name[];
} pi_fs_readfs_desc_t;


static pi_fs_readfs_desc_t *__pi_fs_readfs_get_desc(pi_fs_readfs_t *fs, const char *fs_path)
{
    // Header layout: [fs_size:8][nb_files:4][per-file desc array...].
    uint32_t off = 12;
    for (uint32_t i = 0; i < fs->nb_files; i++)
    {
        pi_fs_readfs_desc_t *desc = (pi_fs_readfs_desc_t *)&fs->header[off];
        if (strcmp(desc->name, fs_path) == 0)
        {
            return desc;
        }
        off += sizeof(pi_fs_readfs_desc_t) + desc->name_len;
    }
    return NULL;
}


static void __pi_fs_readfs_open(void *instance, pi_fs_file_t *file, const char *fs_path,
                                pi_fs_mode_t flags, pi_fs_evt_t *event)
{
    (void)flags;
    pi_fs_readfs_t      *fs   = (pi_fs_readfs_t *)instance;
    pi_fs_readfs_desc_t *desc = __pi_fs_readfs_get_desc(fs, fs_path);
    if (desc == NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return;
    }

    pi_fs_readfs_file_t *rf = pi_malloc(sizeof(pi_fs_readfs_file_t));
    if (rf == NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return;
    }
    rf->addr   = fs->partition_offset + desc->offset;
    rf->offset = 0;
    rf->size   = desc->file_size;
    rf->flash  = fs->flash;
    file->data = rf;

    pi_evt_status_set(&event->header, 0);
    pi_evt_notify(&event->header);
}


static void __pi_fs_readfs_close(void *instance, pi_fs_file_t *file, pi_fs_evt_t *event)
{
    (void)instance;
    if (file->data != NULL)
    {
        pi_free(file->data, sizeof(pi_fs_readfs_file_t));
        file->data = NULL;
    }
    pi_evt_status_set(&event->header, 0);
    pi_evt_notify(&event->header);
}


static void __pi_fs_readfs_read(void *instance, pi_fs_file_t *file, void *dest, size_t size,
                                pi_fs_evt_t *event)
{
    (void)instance;
    pi_fs_readfs_file_t *rf = (pi_fs_readfs_file_t *)file->data;

    size_t   remaining = (rf->offset >= rf->size) ? 0 : (rf->size - rf->offset);
    size_t   real_size = (size > remaining) ? remaining : size;
    uint32_t addr      = rf->addr + rf->offset;

    rf->offset += real_size;
    pi_evt_status_set(&event->header, (int)real_size);

    if (real_size == 0)
    {
        pi_evt_notify(&event->header);
        return;
    }

    // Pass-through to flash. The user event header is the same memory the flash driver expects
    // as the leading field of a pi_flash_evt_t — pi_fs_evt_t is laid out with pi_evt_t first so
    // a cast is safe.
    pi_flash_read_async(rf->flash, addr, dest, real_size, (pi_flash_evt_t *)event);
}


static void __pi_fs_readfs_seek(void *instance, pi_fs_file_t *file, size_t offset)
{
    (void)instance;
    pi_fs_readfs_file_t *rf = (pi_fs_readfs_file_t *)file->data;
    rf->offset = (uint32_t)offset;
}


static void __pi_fs_readfs_stat(void *instance, const char *path, struct pi_fs_dirent *entry,
                                pi_fs_evt_t *event)
{
    pi_fs_readfs_t      *fs   = (pi_fs_readfs_t *)instance;
    pi_fs_readfs_desc_t *desc = __pi_fs_readfs_get_desc(fs, path);
    if (desc != NULL)
    {
        entry->size = desc->file_size;
        pi_evt_status_set(&event->header, 0);
    }
    else
    {
        pi_evt_status_set(&event->header, -1);
    }
    pi_evt_notify(&event->header);
}


// --- Mount state machine ---

static void __pi_fs_readfs_mount_done(pi_evt_t *evt)
{
    pi_fs_readfs_t *fs = container_of(evt, pi_fs_readfs_t, flash_evt.header);
    int status = pi_evt_status_get(evt);
    pi_evt_status_set(&fs->caller_event->header, status);
    pi_evt_notify(&fs->caller_event->header);
}


static void __pi_fs_readfs_mount_top_read(pi_evt_t *evt)
{
    pi_fs_readfs_t *fs = container_of(evt, pi_fs_readfs_t, flash_evt.header);

    // Sanity-check: cap the header allocation so a corrupt / huge fs_size doesn't blow up
    // the heap. 1 MB of file index would be enormous; clamp there.
    if (fs->fs_size < 12 || fs->fs_size > (1u << 20))
    {
        pi_evt_status_set(&fs->caller_event->header, -1);
        pi_evt_notify(&fs->caller_event->header);
        return;
    }

    fs->header = pi_malloc((size_t)fs->fs_size);
    if (fs->header == NULL)
    {
        pi_evt_status_set(&fs->caller_event->header, -1);
        pi_evt_notify(&fs->caller_event->header);
        return;
    }

    pi_evt_cb_init(&fs->flash_evt.header, __pi_fs_readfs_mount_done);
    pi_evt_status_set(&fs->flash_evt.header, 0);
    pi_flash_read_async(fs->flash, fs->partition_offset,
                        fs->header, (size_t)fs->fs_size,
                        &fs->flash_evt);
}


static void *__pi_fs_readfs_mount(pi_device_t *flash, uint32_t offset, uint32_t size,
                                  pi_fs_evt_t *event)
{
    (void)size;
    pi_fs_readfs_t *fs = pi_malloc(sizeof(pi_fs_readfs_t));
    if (fs == NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return NULL;
    }
    fs->flash            = flash;
    fs->partition_offset = offset;
    fs->fs_size          = 0;
    fs->nb_files         = 0;
    fs->header           = NULL;
    fs->caller_event     = event;

    pi_evt_cb_init(&fs->flash_evt.header, __pi_fs_readfs_mount_top_read);
    pi_evt_status_set(&fs->flash_evt.header, 0);
    pi_flash_read_async(flash, offset, &fs->fs_size, 12, &fs->flash_evt);
    return fs;
}


static void __pi_fs_readfs_unmount(void *instance)
{
    pi_fs_readfs_t *fs = (pi_fs_readfs_t *)instance;
    if (fs->header != NULL)
    {
        pi_free(fs->header, (size_t)fs->fs_size);
    }
    pi_free(fs, sizeof(pi_fs_readfs_t));
}


pi_vfs_mp_fs_api_t __pi_fs_readfs_api =
{
    .open    = __pi_fs_readfs_open,
    .close   = __pi_fs_readfs_close,
    .read    = __pi_fs_readfs_read,
    .seek    = __pi_fs_readfs_seek,
    .mount   = __pi_fs_readfs_mount,
    .unmount = __pi_fs_readfs_unmount,
    .stat    = __pi_fs_readfs_stat,
};
