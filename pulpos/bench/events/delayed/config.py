#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import pulpos

def declare(target):

    test = pulpos.new_executable('test', target)

    test.set_optimization_level('-O3 -g')
    test.add_sources('test.c')
