# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from config_tree import Config, cfg_field
from build_tree.script_typing import *


class KernelSoftwareConfig(Config):
    crt0: bool = cfg_field(default=True, write=True, read=True)
    threading: bool = cfg_field(default=True, write=True, read=True)
    preemption: bool = cfg_field(default=True, write=True, read=True)
    thread_slice: int = cfg_field(default=1000, write=True, read=True)
    event: bool = cfg_field(default=True, write=True, read=True)
    alloc: bool = cfg_field(default=False, write=True, read=True)
    fs: bool = cfg_field(default=False, write=True, read=True)
    asserts: bool = cfg_field(default=False, write=True, read=True)

kernel_sw = KernelSoftwareConfig('kernel_sw', label='pmsis_os_kernel')

os_src = get_os_src()

os_src.add('init.c')

with builder.if_(kernel_sw.refs.asserts.logical_not()):
    os_src.with_define('PI_ASSERT_INACTIVE', 1)

with builder.if_(kernel_sw.get_ref('crt0')):
    os_src.add('crt0.S')

with builder.if_(kernel_sw.get_ref('threading')):
    os_src.with_define('CONFIG_THREAD', 1)
    os_src.add('thread.c', 'thread_asm.S')

    with builder.if_(kernel_sw.get_ref('preemption')):
        os_src.with_define('CONFIG_THREAD_PREEMPTION', 1)
        os_src.with_define('CONFIG_THREAD_SLICE', kernel_sw.thread_slice)

with builder.if_(kernel_sw.get_ref('event')):
    os_src.with_define('CONFIG_EVENT', 1)
    os_src.add('event.c', 'event_asm.S')

with builder.if_(kernel_sw.get_ref('alloc')):
    os_src.with_define('CONFIG_KERNEL_ALLOC', 1)
    os_src.add('alloc.c')

with builder.if_(kernel_sw.get_ref('fs')):
    os_src.with_define('CONFIG_KERNEL_FS', 1)
    os_src.add('fs/fs.c', 'fs/readfs.c', 'fs/hostfs.c')

set_os_src(os_src)

exports.kernel_sw = kernel_sw
