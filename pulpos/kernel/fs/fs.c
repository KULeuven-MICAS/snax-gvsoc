// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

// Virtual file system layer. Holds a queue of pending FS operations per ``pi_vfs_t``; serves them
// strictly one at a time so the per-VFS scratch fields (current_*) only need to track one
// in-flight state machine. Each step of the state machine arms ``vfs->flash_evt.header`` as a
// callback event and issues an async flash op; the flash driver then calls back into the next
// step.

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <pmsis/kernel/fs.h>
#include <pmsis/kernel/alloc.h>
#include <pmsis/kernel/irq.h>
#include <kernel/fs/fs_internal.h>


#ifndef container_of
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))
#endif


// Partition magic bytes (gvrun PartitionTableSection):
// - 0x02BA  on the partition-table header
// - 0x01BA  on each entry
// We don't validate them here — we trust the gvrun-generated image — but they are documented
// for reference.

#define PI_PARTITION_SUBTYPE_DATA_RAW    0x80
#define PI_PARTITION_SUBTYPE_DATA_READFS 0x81


// Recover the VFS pointer from the ``flash_evt.header`` field that flash callbacks fire on.
static inline pi_vfs_t *__pi_fs_vfs_from_flash_evt(pi_evt_t *evt)
{
    return container_of(evt, pi_vfs_t, flash_evt.header);
}


// Forward decls — the open/close/stat/flush flows reference each other through the state machine.
static void __pi_fs_operation_done_evt(pi_evt_t *evt);
static void __pi_fs_get_check_fs_mounted(pi_vfs_t *vfs, pi_vfs_mp_t *mp, const char *file_name);


// ------- queue / dispatch primitives -------

static __attribute__((noinline))
void __pi_fs_enqueue_pending(pi_vfs_t *vfs, uint32_t arg0, uint32_t arg1, uint32_t arg2,
                             pi_fs_evt_t *event,
                             void (*callback)(pi_vfs_t *, uint32_t, uint32_t, uint32_t))
{
    // The exec callback needs to find arg0..arg2 again when it resumes — store them in the
    // user's event header status field (status holds the function ptr; the args go in the
    // padding the FS event already reserves). We use the simplest scheme: stash everything in a
    // small descriptor inside the header struct via the user data fields below.
    //
    // The new pi_evt_t API has no user-data slot, so we cannot stash on the user event itself.
    // Instead we serialise pending ops as a singly-linked list whose tail node carries the
    // exec callback + args via a private header allocated on the heap.
    //
    // To keep the patch minimal we degrade to one-at-a-time: pi_fs_*_async callers wait for
    // a signal event to drain before issuing the next call. That's still consistent with the
    // single-state-machine design and matches the expected use pattern (one open at a time per
    // VFS). If you need cross-thread queuing, layer it above this API.
    (void)arg0; (void)arg1; (void)arg2; (void)callback;
    vfs->waiting_last->next = event;
    vfs->waiting_last       = event;
    event->next             = NULL;
}


static inline void __pi_fs_add_first(pi_vfs_t *vfs, pi_fs_evt_t *event)
{
    vfs->waiting_first = event;
    vfs->waiting_last  = event;
    event->next        = NULL;
}


// Notify the active operation's user event and drain the queue.
static void __pi_fs_operation_done(pi_vfs_t *vfs)
{
    pi_fs_evt_t *user_event = vfs->waiting_first;
    pi_fs_evt_t *next       = user_event ? user_event->next : NULL;

    vfs->waiting_first = next;
    if (next == NULL)
        vfs->waiting_last = NULL;

    int status = pi_evt_status_get(&vfs->flash_evt.header);
    if (user_event)
    {
        pi_evt_status_set(&user_event->header, status);
        pi_evt_notify(&user_event->header);
    }
}

// Same callback signature as the flash driver expects.
static void __pi_fs_operation_done_evt(pi_evt_t *evt)
{
    __pi_fs_operation_done(__pi_fs_vfs_from_flash_evt(evt));
}


// ------- partition-table loading state machine -------

static void __pi_fs_get_fs_mounted(pi_evt_t *evt)
{
    pi_vfs_t   *vfs = __pi_fs_vfs_from_flash_evt(evt);
    int status = pi_evt_status_get(evt);
    if (status != 0)
    {
        __pi_fs_operation_done(vfs);
        return;
    }

    vfs->callback(vfs, vfs->current_fs, vfs->current_file_name);
}


static void __pi_fs_get_check_fs_mounted(pi_vfs_t *vfs, pi_vfs_mp_t *mp, const char *file_name)
{
    for (int i = 0; i < mp->pt_header.nb_entries; i++)
    {
        pi_fs_partition_t *info = &mp->partitions[i];
        size_t fs_len = strlen((const char *)info->label);

        if (strncmp((const char *)info->label, file_name, fs_len) == 0
            && file_name[fs_len] == '/')
        {
            pi_vfs_mp_fs_t *fs = &mp->file_systems[i];
            const char     *fs_file_name = &file_name[fs_len + 1];

            if (fs->api == NULL)
            {
                pi_evt_status_set(&vfs->flash_evt.header, -1);
                __pi_fs_operation_done(vfs);
                return;
            }

            if (fs->instance == NULL)
            {
                vfs->current_file_name = fs_file_name;
                vfs->current_fs        = fs;
                pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_get_fs_mounted);
                pi_evt_status_set(&vfs->flash_evt.header, 0);
                fs->instance = fs->api->mount(mp->flash, info->offset, info->size,
                                              (pi_fs_evt_t *)&vfs->flash_evt);
            }
            else
            {
                vfs->callback(vfs, fs, fs_file_name);
            }
            return;
        }
    }

    pi_evt_status_set(&vfs->flash_evt.header, -1);
    __pi_fs_operation_done(vfs);
}


static void __pi_fs_get_fs_pt_read(pi_evt_t *evt)
{
    pi_vfs_t   *vfs = __pi_fs_vfs_from_flash_evt(evt);
    pi_vfs_mp_t *mp = vfs->current_mp;

    for (int i = 0; i < mp->pt_header.nb_entries; i++)
    {
        pi_fs_partition_t *info = &mp->partitions[i];
        mp->file_systems[i].instance = NULL;
        mp->file_systems[i].flash    = mp->flash;
        switch (info->subtype)
        {
            case PI_PARTITION_SUBTYPE_DATA_READFS:
                mp->file_systems[i].api = &__pi_fs_readfs_api;
                break;
            default:
                mp->file_systems[i].api = NULL;
                break;
        }
    }

    mp->opened = 1;
    __pi_fs_get_check_fs_mounted(vfs, mp, vfs->current_file_name);
}


static void __pi_fs_get_fs_pt_header_read(pi_evt_t *evt)
{
    pi_vfs_t    *vfs = __pi_fs_vfs_from_flash_evt(evt);
    pi_vfs_mp_t *mp  = vfs->current_mp;
    int          n   = mp->pt_header.nb_entries;

    if (n <= 0)
    {
        pi_evt_status_set(&vfs->flash_evt.header, -1);
        __pi_fs_operation_done(vfs);
        return;
    }

    mp->partitions = pi_malloc((sizeof(pi_fs_partition_t) + sizeof(pi_vfs_mp_fs_t)) * n);
    if (mp->partitions == NULL)
    {
        pi_evt_status_set(&vfs->flash_evt.header, -1);
        __pi_fs_operation_done(vfs);
        return;
    }
    mp->file_systems = (pi_vfs_mp_fs_t *)((char *)mp->partitions + sizeof(pi_fs_partition_t) * n);

    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_get_fs_pt_read);
    pi_flash_read_async(mp->flash,
                        vfs->current_pt_offset + sizeof(flash_partition_table_header_t),
                        mp->partitions, sizeof(pi_fs_partition_t) * n,
                        &vfs->flash_evt);
}


static void __pi_fs_get_fs_offset_read(pi_evt_t *evt)
{
    pi_vfs_t    *vfs = __pi_fs_vfs_from_flash_evt(evt);
    pi_vfs_mp_t *mp  = vfs->current_mp;

    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_get_fs_pt_header_read);
    pi_flash_read_async(mp->flash, vfs->current_pt_offset,
                        &mp->pt_header, sizeof(mp->pt_header),
                        &vfs->flash_evt);
}


static void __pi_fs_get_fs_flash_opened(pi_evt_t *evt)
{
    pi_vfs_t    *vfs = __pi_fs_vfs_from_flash_evt(evt);
    pi_vfs_mp_t *mp  = vfs->current_mp;

    mp->flash_opened = 1;
    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_get_fs_offset_read);
    pi_flash_read_async(mp->flash, 0, &vfs->current_pt_offset, 4, &vfs->flash_evt);
}


// Entry point: find the mount point, open the flash if needed, read the partition table, and
// hand the resolved (FS, sub-path) pair back through ``vfs->callback``.
static void __pi_fs_get_fs(pi_vfs_t *vfs, const char *file_name,
                           void (*callback)(pi_vfs_t *, pi_vfs_mp_fs_t *, const char *))
{
    vfs->callback = callback;

    pi_vfs_mp_t *found_mp = NULL;
    for (int i = 0; i < vfs->nb_mount_points; i++)
    {
        pi_vfs_mp_t *mp = &vfs->mount_points[i];
        size_t       n  = strlen(mp->path);
        if (strncmp(mp->path, file_name, n) == 0 && file_name[n] == '/')
        {
            found_mp = mp;
            break;
        }
    }

    if (found_mp == NULL)
    {
        pi_evt_status_set(&vfs->flash_evt.header, -1);
        __pi_fs_operation_done(vfs);
        return;
    }

    // Flash-less mount point: a host (semi-hosting) file system. There is no flash to open and
    // no partition table to read — resolve straight to the shared hostfs instance. The VFS path
    // after the mount prefix (leading '/' kept) is the absolute host path, e.g.
    // "/host/home/me/in.bin" -> "/home/me/in.bin".
    if (found_mp->flash == NULL)
    {
        vfs->callback(vfs, &__pi_fs_hostfs_mp_fs, &file_name[strlen(found_mp->path)]);
        return;
    }

    const char *flash_file_name = &file_name[strlen(found_mp->path) + 1];
    vfs->current_mp        = found_mp;
    vfs->current_file_name = flash_file_name;

    if (found_mp->opened)
    {
        __pi_fs_get_check_fs_mounted(vfs, found_mp, flash_file_name);
        return;
    }

    if (found_mp->flash_opened)
    {
        __pi_fs_get_fs_offset_read(&vfs->flash_evt.header);
        return;
    }

    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_get_fs_flash_opened);
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    pi_flash_open_async(found_mp->flash, &vfs->flash_evt);
}


// ------- open -------

static void __pi_fs_open_resume(pi_vfs_t *vfs, pi_vfs_mp_fs_t *fs, const char *fs_path)
{
    if (fs == NULL)
    {
        pi_evt_status_set(&vfs->flash_evt.header, -1);
        __pi_fs_operation_done(vfs);
        return;
    }

    vfs->current_file->fs       = fs;
    vfs->current_file->api      = fs->api;
    vfs->current_file->instance = fs->instance;
    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_operation_done_evt);
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    fs->api->open(fs->instance, vfs->current_file, fs_path, vfs->current_flags,
                  (pi_fs_evt_t *)&vfs->flash_evt);
}


void pi_fs_open_async(pi_vfs_t *vfs, pi_fs_file_t *file, const char *file_name,
                      pi_fs_mode_t flags, pi_fs_evt_t *event)
{
    int irq = pi_irq_lock();

    pi_evt_status_set(&event->header, 0);
    event->next = NULL;

    if (vfs->waiting_first != NULL)
    {
        // A prior op is in flight. Queueing requires storing the per-op exec args; the new evt
        // API doesn't have user slots, so for now keep it strict: callers must serialise their
        // own usage of the VFS.
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        pi_irq_unlock(irq);
        return;
    }

    __pi_fs_add_first(vfs, event);
    vfs->current_file  = file;
    vfs->current_flags = flags;
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    __pi_fs_get_fs(vfs, file_name, __pi_fs_open_resume);

    pi_irq_unlock(irq);
}


// ------- close -------

void pi_fs_close_async(pi_vfs_t *vfs, pi_fs_file_t *file, pi_fs_evt_t *event)
{
    int irq = pi_irq_lock();

    pi_evt_status_set(&event->header, 0);
    event->next = NULL;

    if (vfs->waiting_first != NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        pi_irq_unlock(irq);
        return;
    }

    __pi_fs_add_first(vfs, event);
    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_operation_done_evt);
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    file->api->close(file->instance, file, (pi_fs_evt_t *)&vfs->flash_evt);

    pi_irq_unlock(irq);
}


// ------- stat -------

static void __pi_fs_stat_resume(pi_vfs_t *vfs, pi_vfs_mp_fs_t *fs, const char *fs_path)
{
    if (fs == NULL)
    {
        pi_evt_status_set(&vfs->flash_evt.header, -1);
        __pi_fs_operation_done(vfs);
        return;
    }
    pi_evt_cb_init(&vfs->flash_evt.header, __pi_fs_operation_done_evt);
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    fs->api->stat(fs->instance, fs_path, vfs->current_entry, (pi_fs_evt_t *)&vfs->flash_evt);
}


void pi_fs_stat_async(pi_vfs_t *vfs, const char *path, struct pi_fs_dirent *entry,
                      pi_fs_evt_t *event)
{
    int irq = pi_irq_lock();

    pi_evt_status_set(&event->header, 0);
    event->next = NULL;

    if (vfs->waiting_first != NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        pi_irq_unlock(irq);
        return;
    }

    __pi_fs_add_first(vfs, event);
    vfs->current_entry = entry;
    pi_evt_status_set(&vfs->flash_evt.header, 0);
    __pi_fs_get_fs(vfs, path, __pi_fs_stat_resume);

    pi_irq_unlock(irq);
}


// ------- flush -------

void pi_fs_flush_async(pi_vfs_t *vfs, pi_fs_evt_t *event)
{
    int irq = pi_irq_lock();

    pi_evt_status_set(&event->header, 0);
    event->next = NULL;

    if (vfs->waiting_first != NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        pi_irq_unlock(irq);
        return;
    }

    __pi_fs_add_first(vfs, event);

    for (int i = 0; i < vfs->nb_mount_points; i++)
    {
        pi_vfs_mp_t *mp = &vfs->mount_points[i];
        if (mp->opened)
        {
            mp->opened = 0;
            for (int j = 0; j < mp->pt_header.nb_entries; j++)
            {
                pi_vfs_mp_fs_t *fs = &mp->file_systems[j];
                if (fs->instance != NULL && fs->api != NULL)
                {
                    fs->api->unmount(fs->instance);
                    fs->instance = NULL;
                }
            }
            pi_free(mp->partitions,
                    (sizeof(pi_fs_partition_t) + sizeof(pi_vfs_mp_fs_t))
                        * mp->pt_header.nb_entries);
            mp->partitions   = NULL;
            mp->file_systems = NULL;
        }
    }

    pi_evt_status_set(&vfs->flash_evt.header, 0);
    __pi_fs_operation_done(vfs);

    pi_irq_unlock(irq);
}


// ------- sync wrappers -------

int pi_fs_open(pi_vfs_t *vfs, pi_fs_file_t *file, const char *file_name, pi_fs_mode_t flags)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_open_async(vfs, file, file_name, flags, &event);
    pi_evt_sig_wait(&event.header);
    return pi_evt_status_get(&event.header);
}


int pi_fs_close(pi_vfs_t *vfs, pi_fs_file_t *file)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_close_async(vfs, file, &event);
    pi_evt_sig_wait(&event.header);
    return pi_evt_status_get(&event.header);
}


ssize_t pi_fs_read(pi_fs_file_t *file, void *ptr, size_t size)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_read_async(file, ptr, size, &event);
    pi_evt_sig_wait(&event.header);
    return (ssize_t)pi_evt_status_get(&event.header);
}


ssize_t pi_fs_write(pi_fs_file_t *file, const void *ptr, size_t size)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_write_async(file, ptr, size, &event);
    pi_evt_sig_wait(&event.header);
    return (ssize_t)pi_evt_status_get(&event.header);
}


int pi_fs_seek(pi_fs_file_t *file, size_t offset)
{
    // Seek is purely local to the FS driver (it just moves the read cursor), so there is no
    // async flash op to wait on — dispatch straight through the vtable.
    if (file->api->seek == NULL)
    {
        return -1;
    }
    file->api->seek(file->instance, file, offset);
    return 0;
}


int pi_fs_stat(pi_vfs_t *vfs, const char *path, struct pi_fs_dirent *entry)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_stat_async(vfs, path, entry, &event);
    pi_evt_sig_wait(&event.header);
    return pi_evt_status_get(&event.header);
}


int pi_fs_flush(pi_vfs_t *vfs)
{
    pi_fs_evt_t event;
    pi_evt_sig_init(&event.header);
    pi_fs_flush_async(vfs, &event);
    pi_evt_sig_wait(&event.header);
    return pi_evt_status_get(&event.header);
}
