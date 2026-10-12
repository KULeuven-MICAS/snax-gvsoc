#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import os

def declare(target, container):

    if container.get_parameter('libc.io_device') is not None:
        container.add_define(f'CONFIG_LIBC_IO_{container.get_parameter("libc.io_device").upper()}', 1)

    container.add_includes([
        os.path.join(os.environ.get('PULPOS_HOME'), 'include/pmsis/lib/libc/minimal'),
    ])

    container.add_define('CONFIG_LIBC_MINIMAL', 1)

    container.add_sources([
        'lib/libc/minimal/io.c',
        'lib/libc/minimal/string.c',
    ])

    if container.get_parameter('libc.printf'):
        container.add_sources([
            'lib/libc/minimal/prf.c',
            'lib/libc/minimal/fprintf.c',
            'lib/libc/minimal/sprintf.c',
        ])
