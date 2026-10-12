#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun.parameter import BuildParameter

def declare(target, container):

    BuildParameter(container, 'libc.printf', True, 'Include printf in libc')
    minimal = BuildParameter(container, 'libc.minimal', True, 'Include minimal libc')
    io_device = BuildParameter(container, 'libc.io_device', None, 'Device to be used for input/output in libc')

    if io_device is None:
        # If no device is specified, always take stdout for RTL as it is usally the only one
        # supported, and semihost for others to match the board on simulation platforms
        if container.get_parameter('/platform') == 'rtl':
            container.set_parameter('libc.io_device', 'stdout')
        else:
            container.set_parameter('libc.io_device', 'semihost')

    if minimal:
        container.add_subdirectory('minimal', target)
