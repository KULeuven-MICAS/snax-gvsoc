#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu target: snax_cluster's cfg/snax_alu_cluster_old.hjson at the pin
(sw/cfg/, sw/README.md), read by the generic target (snax_hjson.py).

One cluster with a compute core (hart 0, the one that drives the accelerator)
and a DMA core (hart 1), both rv32ima, 128 KiB TCDM in 32 banks and the plain
interconnect. The compute core's slot, snax_alu, is snax_alu_acc.py
(snax_hjson.ACCELERATORS). The file is fixed: the target takes no
hjson option.

    gvrun --target snax_alu --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

from snax_hjson import fixed_target

SnaxAluBoard, Target = fixed_target(__name__, 'SnaxAluBoard', 'snax_alu_cluster_old.hjson',
    "snax_cluster's snax_alu cluster (old hjson)")
