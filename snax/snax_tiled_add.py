#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_tiled_add target (GEN3 step 2): the snax_alu target (snax_alu.py)
with the hand-written tiled add accelerator of snax_tiled_add_acc.py in the
compute core's accelerator slot; everything else as snax_alu.

    gvrun --target snax_tiled_add --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

import gvsoc.runner
from snax_alu import SnaxAluBoard
from snax_tiled_add_acc import SnaxTiledAddAcc


class SnaxTiledAddBoard(SnaxAluBoard):

    accelerator = SnaxTiledAddAcc


class Target(gvsoc.runner.Target):

    gapy_description = "snax_alu's cluster with a tiled add accelerator on SnaxShell and SnaxUnit"
    model = SnaxTiledAddBoard
    name = "snax_tiled_add"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxTiledAddBoard, name=name)
