#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun.parameter import BuildParameter
from pulpos import SourceContainer

def declare(target, container: SourceContainer):

    crt0 = BuildParameter(container, 'crt0', True, 'Add crt0').value
    if crt0:
        container.add_sources(['kernel/crt0.S'])

    threading = BuildParameter(container, 'kernel.threading', True, 'Enable thread scheduling').value
    if threading:
        preemption = BuildParameter(container, 'kernel.threading.preemption', True, 'Enable thread scheduling preemption').value
        slice = BuildParameter(container, 'kernel.threading.slice', 1000, 'Thread slice duration in microseconds').value

        if preemption:
            container.add_define('CONFIG_THREAD_PREEMPTION', 1)
            container.add_define('CONFIG_THREAD_SLICE', slice)

        container.add_define('CONFIG_THREAD', 1)

        container.add_sources([
            'kernel/thread.c',
            'kernel/thread_asm.S',
        ])

    event = BuildParameter(container, 'kernel.event', True, 'Enable events').value
    if event:
        container.add_define('CONFIG_EVENT', 1)

        container.add_sources([
            'kernel/event.c',
            'kernel/event_asm.S',
        ])

    alloc = BuildParameter(container, 'kernel.alloc', False, 'Enable memory allocator').value
    if alloc:
        container.add_define('CONFIG_KERNEL_ALLOC', 1)

        container.add_sources([
            'kernel/alloc.c',
        ])

    # Defaults to the top-level /memcheck property (set from the --memcheck run
    # flag), so building and running with --memcheck compiles in the allocator
    # instrumentation automatically. Still overridable per app via
    # --parameter <exe>/kernel.memcheck=<bool>.
    memcheck = BuildParameter(container, 'kernel.memcheck',
        bool(container.get_parameter('/memcheck')),
        'Declare allocations to the gvsoc memory checker (defaults to the --memcheck run flag)').value
    if memcheck:
        container.add_define('CONFIG_MEMCHECK', 1)

    fs = BuildParameter(container, 'kernel.fs', False, 'Enable file system layer').value
    if fs:
        if not alloc:
            raise RuntimeError('kernel.fs requires kernel.alloc')
        container.add_define('CONFIG_KERNEL_FS', 1)
        container.add_subdirectory('fs', target)

    container.add_sources([
        'kernel/init.c',
    ])
