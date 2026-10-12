#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import pulpos

def declare(target):

    test = pulpos.new_executable('test', target,
        parameters=[('pulpos/kernel.threading', True)])

    test.set_optimization_level('-Os -g')
    # The OS is compiled at -O3 (its default in the make flow) so both flows
    # measure the same kernel and share one set of bench references.
    test.pulpos.set_optimization_level('-O3 -g')
    test.add_sources('test.c')
