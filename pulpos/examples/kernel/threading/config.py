#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun import systree
from pulpos import new_executable, PulposExecutable


def declare(target: systree.SystemTreeNode):

    hello: PulposExecutable = new_executable('test', target, parameters=[
        ('pulpos/kernel.threading', True)
    ])

    hello.add_cflags('-Os -g')
    hello.add_ldflags('-Os -g')
    hello.add_sources('test.c')
