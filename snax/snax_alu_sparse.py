#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu_sparse target: snax_cluster's cfg/snax_alu_cluster.hjson at the
pin, 9fbf35d, which is snax_alu_cluster_old.hjson with the sparse
interconnect (SG7).

The snax_alu target (snax_alu.py) with its SNAX crossbar sparse: priority
first, then round robin from the last pick (snax_tcdm_xbar.cpp). The
accelerator's ports, then the two cores' and AXI's, [1, 1] each, as snaxgen
lists them; the DMA's beats take their superbank as on the plain target.

    gvrun --target snax_alu_sparse --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

import gvsoc.runner
from snax_alu import SnaxAluBoard

# The accelerator's sparse_interconnect_config in the hjson, by core: the
# compute core's ALU, 12 TCDM ports of granularity 1
SPARSE_CONFIG = {0: [[12, 1]]}


class SnaxAluSparseBoard(SnaxAluBoard):

    interconnect = {'snax_interconnect': 'sparse', 'snax_sparse_config': SPARSE_CONFIG}


class Target(gvsoc.runner.Target):

    gapy_description = "snax_cluster's snax_alu cluster (sparse interconnect)"
    model = SnaxAluSparseBoard
    name = "snax_alu_sparse"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxAluSparseBoard, name=name)
