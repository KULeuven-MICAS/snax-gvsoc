#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from gvrun.parameter import BuildParameter
from pulpos import SourceContainer


def declare(target, container: SourceContainer):

    container.add_sources([
        'kernel/fs/fs.c',
        'kernel/fs/readfs.c',
        'kernel/fs/hostfs.c',
    ])
