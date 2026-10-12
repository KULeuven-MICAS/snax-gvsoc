#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import os
import pulpos


def declare(target):
    test = pulpos.new_executable('test', target)
    test.set_optimization_level('-Os -g')
    test.add_sources('test.c')

    here = os.path.dirname(os.path.abspath(__file__))

    # Input file served from the host (workstation) via semi-hosting. Its absolute path exists at
    # both build and run time, so it is passed straight through with the "/host" mount prefix (the
    # VFS strips that prefix and forwards the rest to the host as an absolute path).
    input_file = os.path.join(here, 'files', 'input.txt')
    test.add_define('HOSTFS_INPUT_PATH', '"/host%s"' % input_file)

    # Output file written on the host during the test, then read back. It goes into this
    # executable's own (absolute) build directory so it is writable and isolated per test run.
    out_file = os.path.join(os.path.dirname(test.get_binary()), 'hostfs_write.bin')
    test.add_define('HOSTFS_OUTPUT_PATH', '"/host%s"' % out_file)
