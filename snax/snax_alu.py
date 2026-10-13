#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_alu target: snax_cluster's cfg/snax_alu_cluster_old.hjson at b2672f8.

One cluster with a compute core (hart 0, the one that drives the accelerator)
and a DMA core (hart 1), both rv32ima, 128 KiB TCDM in 32 banks and the plain
interconnect. The compute core's accelerator CSRs go to a stub that holds
them (snax_csr_stub.py) until the streamer and ALU models replace it. The values are written here by hand; everything else is the
Snitch chip of pulp/pulp/chips/snitch/snitch.py, whose own arch tree fixes the
core count at 9.

    gvrun --target snax_alu --work-dir build/work/<name> \
        --param chip/soc/binary=<elf> run
"""

import os

import gvsoc.runner
import gvsoc.systree
import memory.memory
from vp.clock_domain import Clock_domain
from gvrun.attribute import Tree, Area
from pulp.snitch.snitch_cluster.snitch_cluster import ClusterArch
from pulp.chips.snitch.snitch import Snitch
from snax_csr_stub import SnaxCsrStub

# GVSoC reads a target twice: `make build` lists its components through gapy
# without USE_GVRUN, and gvrun runs it with USE_GVRUN set. Each pulp module
# defines different arch classes for the two, so this target does too: the
# build reuses SnitchArch with the core count changed, the run uses
# SnaxAluAttr below. Only the run needs misa, a value read at run time; both
# need the accelerators, since the build compiles their sources.
if os.environ.get('USE_GVRUN') is None:
    from pulp.chips.snitch.snitch import SnitchArch, SnitchArchProperties


# Cores per cluster in the hjson's hive: the compute core, then the DMA core
# (GVSoC's Snitch cluster takes its last core as the DMA core).
NB_CORE = 2

# misa of an rv32ima core: MXL = 1 (32 bit), extensions A (bit 0), I (bit 8)
# and M (bit 12). snax_cluster's start-up code reads it to skip the FP
# registers. Only the CSR value changes: the model still executes FP
# instructions.
MISA_RV32IMA = (1 << 30) | (1 << 12) | (1 << 8) | (1 << 0)

# The accelerator CSRs of the compute core, from the app's
# streamer_csr_addr_map.h and snax-alu-lib.h: the streamer's read-write CSRs
# (3 streamers x 5, then start) and read-only CSRs (busy, performance counter),
# then the ALU's (mode, length, start; busy, performance counter).
STREAMER_RW_CSRS = list(range(960, 976))
STREAMER_RO_CSRS = [976, 977]
ALU_RW_CSRS = [978, 979, 980]
ALU_RO_CSRS = [981, 982]


def snax_alu_acc(parent, name):
    """The accelerator of the compute core: for now a stub that holds its CSRs."""
    return SnaxCsrStub(parent, name, rw_csrs=STREAMER_RW_CSRS + ALU_RW_CSRS,
        ro_csrs=STREAMER_RO_CSRS + ALU_RO_CSRS)


# SNAX accelerators per core index: the compute core (hart 0) drives the ALU.
SNAX_ACC = {0: snax_alu_acc}

# The DMA and DRAM measured on the RTL in SG2 (docs/notes/NOTES.md, SG2 step 4):
# one 64 B beat per cycle into L1 (dma_data_width 512), 3 transfers queued
# (dma_req_fifo_depth) and 3 bursts in flight (dma_axi_req_fifo_depth). A DMA
# read's first beat comes 5 cycles after its request from L1 and 11 from DRAM:
# the 5 common to both are the DMA's own read path (read_latency), the other 6
# are the DRAM's. The cores' fetches and loads from DRAM take the same path;
# their latency on the RTL is not measured (SG5).
SNAX_DMA = {'tcdm_width': 64, 'transfer_queue_size': 3, 'burst_queue_size': 3,
    'read_latency': 5}
DRAM_LATENCY = 6
DRAM_WIDTH_LOG2 = 6  # 64 B per cycle


class SnaxAluAttr(Tree):
    """The address map and cluster of the target, as SnitchAttr gives them."""

    def __init__(self, parent, name):
        super().__init__(parent, name)
        self.chip = SnaxAluAttr.Chip(self, 'chip')
        self.hbm = SnaxAluAttr.Hbm(self, 'hbm')

    class Hbm(Tree):

        def __init__(self, parent, name):
            super().__init__(parent, name)
            self.type = 'simple'
            self.size = 0x8000_0000

    class Chip(Tree):

        def __init__(self, parent, name):
            super().__init__(parent, name)
            self.soc = SnaxAluAttr.Chip.Soc(self, 'soc')

        class Soc(Tree):

            def __init__(self, parent, name):
                super().__init__(parent, name)
                self.bootrom = Area(self, 'rom', 0x0000_1000, 0x0001_0000,
                    description='Bootrom range')
                self.hbm = Area(self, 'hbm', 0x8000_0000, 0x8000_0000,
                    description='DRAM range')
                self.cluster = Area(self, 'cluster', 0x1000_0000, 0x0004_0000,
                    description='Cluster range')
                self.hbm_latency = DRAM_LATENCY
                self.floonoc = False
                self.use_spatz = False
                self.nb_cluster = 1
                self.clusters = [
                    ClusterArch(self, 'cluster', self.get_cluster_base(0), 0,
                        nb_core_per_cluster=NB_CORE, misa=MISA_RV32IMA,
                        snax_acc=SNAX_ACC, dma=SNAX_DMA)
                ]

            def get_cluster_base(self, id: int):
                return self.cluster.base + id * self.cluster.size

            def get_cluster(self, id: int):
                return self.clusters[id]


class SnaxAluBoard(gvsoc.systree.Component):

    def __init__(self, parent, name: str, parser, options):
        super().__init__(parent, name, options=options)

        clock = Clock_domain(self, 'clock', frequency=10000000)

        if os.environ.get('USE_GVRUN') is None:
            properties = SnitchArchProperties()
            properties.nb_core_per_cluster = NB_CORE
            properties.snax_acc = SNAX_ACC
            properties.dma = SNAX_DMA
            arch = SnitchArch(self, properties=properties)
        else:
            arch = SnaxAluAttr(self, 'snax_alu')
        # Exposed so tools like the build process can query the memory map.
        self.set_attributes(arch)

        chip = Snitch(self, 'chip', parser, arch.chip, None, [])
        mem = memory.memory.Memory(self, 'mem', size=arch.hbm.size, atomics=True,
            width_log2=DRAM_WIDTH_LOG2)

        self.bind(clock, 'out', chip, 'clock')
        self.bind(clock, 'out', mem, 'clock')
        self.bind(chip, 'hbm', mem, 'input')


class Target(gvsoc.runner.Target):

    gapy_description = "snax_cluster's snax_alu cluster (old hjson)"
    model = SnaxAluBoard
    name = "snax_alu"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxAluBoard, name=name)
