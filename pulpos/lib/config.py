#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun.parameter import BuildParameter

def declare(target, container):

    enabled = BuildParameter(container, 'libc.enabled', True, 'Include libc')

    if enabled:
        container.add_define('CONFIG_LIBC', 1)

        container.add_subdirectory('libc', target)
