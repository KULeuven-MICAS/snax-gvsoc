// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <pmsis/kernel/fs.h>


// FS drivers register their vtable via this symbol. Add new entries below as additional FS
// drivers (writefs, ...) come online.
extern pi_vfs_mp_fs_api_t __pi_fs_readfs_api;

// Host (semi-hosting) file system. Reached through flash-less mount points; the VFS resolves
// such mount points directly to this shared, stateless instance (see __pi_fs_get_fs in fs.c).
extern pi_vfs_mp_fs_api_t __pi_fs_hostfs_api;
extern pi_vfs_mp_fs_t     __pi_fs_hostfs_mp_fs;
