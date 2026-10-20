#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu_sparse target: snax_cluster's cfg/snax_alu_cluster.hjson at the
pin (sw/cfg/, sw/README.md), which is snax_alu_cluster_old.hjson with the
sparse interconnect, read by the generic target (snax_hjson.py).

The snax_alu target (snax_alu.py) with its SNAX crossbar sparse: priority
first, then round robin from the last pick (snax_tcdm_xbar.cpp). The
accelerator's ports (its sparse_interconnect_config, [[12, 1]]), then the two
cores' and AXI's, [1, 1] each, as snaxgen lists them; the DMA's beats take
their superbank as on the plain target. The file is fixed: the target takes
no hjson option.

    gvrun --target snax_alu_sparse --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

from snax_hjson import fixed_target

SnaxAluSparseBoard, Target = fixed_target(__name__, 'SnaxAluSparseBoard', 'snax_alu_cluster.hjson',
    "snax_cluster's snax_alu cluster (sparse interconnect)")
