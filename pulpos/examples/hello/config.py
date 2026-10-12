#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import pulpos

def declare(target):

    hello = pulpos.new_executable('test', target)

    hello.set_optimization_level('-Os -g')
    hello.add_sources('test.c')
