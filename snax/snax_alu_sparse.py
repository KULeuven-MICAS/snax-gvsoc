#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu_sparse target: snax_cluster's cfg/snax_alu_cluster.hjson at the
pin, 9fbf35d (sw/cfg/), which is snax_alu_cluster_old.hjson with the sparse
interconnect (SG7), read by the generic target (snax_hjson.py, LNK2a).

The snax_alu target (snax_alu.py) with its SNAX crossbar sparse: priority
first, then round robin from the last pick (snax_tcdm_xbar.cpp). The
accelerator's ports (its sparse_interconnect_config, [[12, 1]]), then the two
cores' and AXI's, [1, 1] each, as snaxgen lists them; the DMA's beats take
their superbank as on the plain target. The file is fixed: the target takes
no hjson option.

    gvrun --target snax_alu_sparse --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

import gvsoc.runner
from snax_hjson import SnaxHjsonBoard


class SnaxAluSparseBoard(SnaxHjsonBoard):

    cluster_file = 'snax_alu_cluster.hjson'
    hjson_option = False


class Target(gvsoc.runner.Target):

    gapy_description = "snax_cluster's snax_alu cluster (sparse interconnect)"
    model = SnaxAluSparseBoard
    name = "snax_alu_sparse"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxAluSparseBoard, name=name)
