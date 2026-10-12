#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun import systree
from gvrun.parameter import set_parameters_from_node
from pulpos import new_executable, PulposExecutable


def declare(target: systree.SystemTreeNode):

    # stack-check is a top-level parameter (declared by the pulpos root
    # config.py), so it is set globally rather than through the executable
    # parameters, which are prefixed with the executable path
    set_parameters_from_node([('stack-check', True)])

    test: PulposExecutable = new_executable('test', target, parameters=[
        ('pulpos/kernel.threading', True),
    ])

    test.add_cflags('-Os -g')
    test.add_ldflags('-Os -g')
    test.add_sources('test.c')
