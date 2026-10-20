#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu target: snax_cluster's cfg/snax_alu_cluster_old.hjson at b2672f8,
unchanged up to the pin, 9fbf35d (sw/cfg/), read by the generic target
(snax_hjson.py, LNK2a): written by hand from it until then.

One cluster with a compute core (hart 0, the one that drives the accelerator)
and a DMA core (hart 1), both rv32ima, 128 KiB TCDM in 32 banks and the plain
interconnect. The compute core's slot, snax_alu, is snax_alu_acc.py (the
registered accelerator of that name). The file is fixed: the target takes no
hjson option.

    gvrun --target snax_alu --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

import gvsoc.runner
from snax_hjson import SnaxHjsonBoard


class SnaxAluBoard(SnaxHjsonBoard):

    cluster_file = 'snax_alu_cluster_old.hjson'
    hjson_option = False


class Target(gvsoc.runner.Target):

    gapy_description = "snax_cluster's snax_alu cluster (old hjson)"
    model = SnaxAluBoard
    name = "snax_alu"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxAluBoard, name=name)
