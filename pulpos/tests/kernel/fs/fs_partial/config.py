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

    files_dir = os.path.join(os.path.dirname(__file__), 'files')
    flash = target.get_flash('mram')
    flash.set_property('readfs', 'files', os.path.join(files_dir, 'lorem.txt'))
