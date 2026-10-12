// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <pmsis/kernel/fs.h>


// Read pass-through: the active FS driver issues a single async flash read straight against
// the user-supplied event header, so this is a trivial vtable dispatch.
ALWAYS_INLINE void pi_fs_read_async(pi_fs_file_t *file, void *ptr, size_t size, pi_fs_evt_t *event)
{
    file->api->read(file->instance, file, ptr, size, event);
}


// Write pass-through, mirroring the read path. Drivers that do not support writing (e.g. the
// read-only readfs) leave the vtable slot NULL, so fail the op cleanly rather than crashing.
ALWAYS_INLINE void pi_fs_write_async(pi_fs_file_t *file, const void *ptr, size_t size,
                                     pi_fs_evt_t *event)
{
    if (file->api->write == NULL)
    {
        pi_evt_status_set(&event->header, -1);
        pi_evt_notify(&event->header);
        return;
    }
    file->api->write(file->instance, file, ptr, size, event);
}
