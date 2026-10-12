// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#ifndef LANGUAGE_ASSEMBLY


#define PI_PARTITION_LABEL_LENGTH 16U


typedef struct pi_vfs_mp_fs_s pi_vfs_mp_fs_t;
typedef struct pi_vfs_mp_fs_api_s pi_vfs_mp_fs_api_t;
typedef struct pi_fs_partition_s pi_fs_partition_t;
typedef struct flash_partition_table_header_s flash_partition_table_header_t;


// Partition table header (matches the gvrun PartitionTableSection layout).
struct flash_partition_table_header_s
{
    uint16_t magic_bytes;
    uint8_t  format_version;
    uint8_t  nb_entries;
    uint8_t  crc;
    uint8_t  padding[11];
    uint8_t  md5[16];
};


// Partition entry in the partition table (32 bytes).
struct pi_fs_partition_s
{
    uint16_t magic_bytes;
    uint8_t  type;
    uint8_t  subtype;
    uint32_t offset;
    uint32_t size;
    uint8_t  label[PI_PARTITION_LABEL_LENGTH];
    uint32_t flags;
};


// Per-partition mounted-FS state (one slot per partition entry).
struct pi_vfs_mp_fs_s
{
    pi_vfs_mp_fs_api_t *api;
    void               *instance;
    pi_device_t        *flash;
};


// One BSP-declared mount point (a flash mounted at a path prefix).
struct pi_vfs_mp_s
{
    const char        *path;
    pi_device_t       *flash;
    int                opened;
    int                flash_opened;
    pi_fs_partition_t *partitions;
    pi_vfs_mp_fs_t    *file_systems;
    flash_partition_table_header_t pt_header;
};


// Opaque file handle. Allocated by the user; populated on open.
struct pi_fs_file_s
{
    pi_vfs_mp_fs_t      *fs;
    void                *data;
    pi_vfs_mp_fs_api_t  *api;
    void                *instance;
};


// FS-driver vtable. Each FS implementation (readfs, ...) provides an instance of this.
struct pi_vfs_mp_fs_api_s
{
    void  (*open)   (void *fs, pi_fs_file_t *file, const char *fs_path,
                     pi_fs_mode_t flags, pi_fs_evt_t *event);
    void  (*close)  (void *fs, pi_fs_file_t *file, pi_fs_evt_t *event);
    void  (*read)   (void *fs, pi_fs_file_t *file, void *dest, size_t nbytes,
                     pi_fs_evt_t *event);
    void  (*write)  (void *fs, pi_fs_file_t *file, const void *src, size_t nbytes,
                     pi_fs_evt_t *event);
    void  (*seek)   (void *fs, pi_fs_file_t *file, size_t offset);
    void *(*mount)  (pi_device_t *flash, uint32_t offset, uint32_t size, pi_fs_evt_t *event);
    void  (*unmount)(void *fs);
    void  (*stat)   (void *fs, const char *path, struct pi_fs_dirent *entry,
                     pi_fs_evt_t *event);
};


// VFS instance. Allocated by the user via PI_BSP_VFS_INST.
struct pi_vfs_s
{
    pi_flash_evt_t flash_evt;          // event used to chain internal flash ops
    int            nb_mount_points;
    pi_vfs_mp_t   *mount_points;

    // Pending-operation queue. The head is the active operation (the one whose state machine is
    // in flight); newer operations link in at the tail.
    pi_fs_evt_t   *waiting_first;
    pi_fs_evt_t   *waiting_last;

    // Temporaries for the in-flight operation. Only the active op is mid-flight at any time, so
    // these scalars are safely reused across steps of one state machine.
    uint32_t            current_pt_offset;
    pi_fs_mode_t        current_flags;
    const char         *current_file_name;
    pi_vfs_mp_t        *current_mp;
    pi_fs_file_t       *current_file;
    pi_vfs_mp_fs_t     *current_fs;
    struct pi_fs_dirent *current_entry;
    void              (*callback)(pi_vfs_t *vfs, pi_vfs_mp_fs_t *fs, const char *fs_path);
};


#endif
