#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The snax_hjson target: a SNAX cluster read from its hjson
(snax_cfg.py), the path a target option.

    gvrun --target snax_hjson --work-dir build/work/<name> \
        --param hjson=<cluster.hjson> --param chip/soc/binary=<elf> run

(or --target snax_hjson:hjson=<cluster.hjson>). A relative path is taken
from gvrun's working directory. Without it, the build's default:
forge/vecadd/snax_forge.hjson, snax-forge's vecadd fixture's cluster (with
its streamer file and accelerator.json), installed beside this module as
cfg/forge/vecadd/ (snax/CMakeLists.txt); snax_cluster's synced copy in
sw/cfg/snax_forge/ is never read (snax-forge D126). The build's platform tree holds the default file's
components and bindings: a file with the same ones (forge/vecadd/'s) uses it, its properties coming through the JSON
config as always; one with others (another accelerator) does not match, so
gvrun warns and runs it on the JSON config (runner_gvrun2.py).

From the hjson: the core count over the hives (the DMA core last, as GVSoC's
Snitch cluster takes it), misa from the cores' isa, int_loads_in_flight from
their num_int_outstanding_loads, boot_addr, cluster_base_addr, the TCDM
(size, banks, data_width), cluster_periph_size and zero_mem_size, the DMA
(dma_data_width, dma_req_fifo_depth as its transfer queue,
dma_axi_req_fifo_depth as its bursts in flight), dram, and the SNAX
crossbar's sparse interconnect (each slot's sparse_interconnect_config;
tcdm.sparse_interconnect false is an error: the plain interconnect is not
modelled). Each core's accelerator slot gets the standard
composite (snax_unit_acc.py) from its accelerator.json (snax_datapath_cfg); a
slot without one is an error.

Not in the hjson, so constants here, calibrated to snax_cluster's RTL: the
DMA's read path and write latency and its one cycle per stage, the DRAM's
latency and width, the cores' added latency, the HTIF poll backdoor, the
10 MHz clock and the bootrom's range.

Everything else is the Snitch chip of pulp/pulp/chips/snitch/snitch.py,
whose own arch tree fixes the core count at 9.
"""

import os
from pathlib import Path

import gvsoc.runner
import gvsoc.systree
import memory.memory
from vp.clock_domain import Clock_domain
from gvrun.attribute import Tree, Area
from pulp.snitch.snitch_cluster.snitch_cluster import ClusterArch
from pulp.chips.snitch.snitch import Snitch
import snax_cfg
from snax_cfg import CfgTargetError
from snax_unit_acc import SnaxUnitAcc, compile_components

# GVSoC reads a target twice: `make build` lists its components through gapy
# without USE_GVRUN, and gvrun runs it with USE_GVRUN set. Each pulp module
# defines different arch classes for the two, so this target does too: the
# build reuses SnitchArch with the core count and the cluster's values
# changed, the run uses SnaxHjsonAttr below. Only the run needs misa, a value
# read at run time; both need the accelerators and the interconnect, since the
# build compiles their sources and checks the crossbar's configuration.
if os.environ.get('USE_GVRUN') is None:
    from pulp.chips.snitch.snitch import SnitchArch, SnitchArchProperties


HERE = Path(__file__).resolve().parent
# Where a target's cluster file is found by name: cfg/ beside this module in
# the install (snax/CMakeLists.txt copies sw/cfg/ and forge/vecadd/ there),
# the repo's sw/cfg/ and its root when the build reads the sources
CFG_DIRS = (HERE / 'cfg', HERE.parent / 'sw' / 'cfg', HERE.parent)
DEFAULT_HJSON = 'forge/vecadd/snax_forge.hjson'

# The DMA and DRAM measured on the RTL (docs/notes/NOTES.md), with the hjson's
# snax_alu cluster: one beat of dma_data_width per cycle into L1, the DMA's
# queues the hjson's. A DMA read's first beat comes 5 cycles after
# its request from L1 and 11 from DRAM: the 5 common to both are the DMA's own
# read path (read_latency), the other 6 are the DRAM's. From the RTL's DMA write
# path (docs/plans/SG7.md): a beat reaches L1 2 cycles after the DMA sends
# it, the wide crossbar's cut and axi_to_mem_interleaved, and the DMA is done at
# the send (tcdm_write_latency); the DMA's midend, backend and AXI read each
# take a cycle, whatever else the DMA is doing (one_cycle_per_stage).
DMA_TIMING = {'read_latency': 5, 'tcdm_write_latency': 2, 'one_cycle_per_stage': True}
DRAM_LATENCY = 6
DRAM_WIDTH_LOG2 = 6  # 64 B per cycle

# The cores' loads, measured on the RTL (docs/notes/NOTES.md) in snax-alu's
# check loop, with one integer load in flight (the hjson's
# num_int_outstanding_loads: 1): a load issues only once the previous load's
# data is back. From one load to the next, 4 cycles from L1 and 14 from DRAM;
# the core's data path gets the cycles GVSoC lacks for that (core_latency), on
# its TCDM port and on its way out of the cluster (narrow_axi). Instruction
# fetches keep their own path. On the TCDM port the SNAX crossbar answers a
# core's read one cycle after its grant plus these cycles; the core goes on
# meanwhile, and the next load or an instruction on the loaded register runs in
# the cycle after: 4 from one L1 load to the next with tcdm 2.
CORE_LATENCY = {'tcdm': 2, 'narrow': 6}
# GVSoC's host reads tohost every 1000 cycles; the RTL's host does not use the
# bus, so the poll reads DRAM through the zero-time debug backdoor.
HTIF_POLL_BACKDOOR = True
CLOCK_FREQUENCY = 10000000
# The bootrom's range, as the Snitch chip's
BOOTROM = (0x0000_1000, 0x0001_0000)


def cfg_file(name: str) -> Path:
    """The cluster file name in the first of CFG_DIRS that holds it."""
    for folder in CFG_DIRS:
        if (folder / name).is_file():
            return folder / name
    return CFG_DIRS[0] / name


def accelerator(cfg, slot):
    """The accelerator class of a slot: the standard composite of its accelerator.json."""
    if slot.accelerator is None:
        raise CfgTargetError(cfg.path, f'{slot.at}.snax_datapath_cfg',
            f'missing: {slot.name!r} has no accelerator.json, which the model builds a slot from')
    return SnaxUnitAcc.for_slot(slot, cfg.tcdm.size, cfg.path)


def _one(cfg, values: dict, what: str):
    """The value every core gives (values: {core index: value})."""
    found = set(values.values())
    if len(found) != 1:
        raise CfgTargetError(cfg.path, 'cluster.hives',
            f'the cores differ in {what} ({values}); the cluster model takes one')
    return found.pop()


class SnaxHjson:
    """What the board takes from a cluster file (cfg, a snax_cfg.ClusterCfg), as ClusterArch
    arguments."""

    def __init__(self, cfg):
        self.cfg = cfg
        cores = cfg.cores
        if not cores:
            raise CfgTargetError(cfg.path, 'cluster.hives', 'no cores')
        dma_cores = [i for i, core in enumerate(cores) if core.xdma]
        if dma_cores != [len(cores) - 1]:
            raise CfgTargetError(cfg.path, 'cluster.hives',
                f'xdma on cores {dma_cores}; the model takes the last core, '
                f'{len(cores) - 1}, as the one DMA core')
        self.nb_core = len(cores)
        # misa as the ISA string gives it (MXL and the base letters); snax_cluster's
        # start-up code reads it to skip the FP registers. Only the CSR value
        # changes: the model still executes FP instructions.
        self.misa = _one(cfg, {i: core.misa for i, core in enumerate(cores)}, 'isa')
        loads = _one(cfg, {i: core.num_int_outstanding_loads for i, core in enumerate(cores)},
            'num_int_outstanding_loads')

        # The accelerators by core, and their sparse interconnect ports
        if not cfg.tcdm.sparse_interconnect:
            raise CfgTargetError(cfg.path, 'cluster.tcdm.sparse_interconnect',
                'is false: only the sparse interconnect is modelled, not the plain one')
        self.snax_acc = {}
        sparse_config = {}
        for i, core in enumerate(cores):
            if len(core.accelerators) > 1:
                raise CfgTargetError(cfg.path, core.accelerators[1].at,
                    'more than one accelerator on a core; the model takes one per core')
            for slot in core.accelerators:
                if slot.wide_tcdm_ports:
                    raise CfgTargetError(cfg.path, f'{slot.at}.snax_wide_tcdm_ports',
                        f'{slot.wide_tcdm_ports} wide ports, not modelled')
                self.snax_acc[i] = accelerator(cfg, slot)
                if slot.sparse_config is not None:
                    sparse_config[i] = slot.sparse_config
        self.interconnect = {'snax_sparse_config': sparse_config}

        # A DMA beat is one superbank: dma_data_width bits
        self.dma = {'tcdm_width': cfg.dma.data_width // 8,
            'transfer_queue_size': cfg.dma.req_fifo_depth,
            'burst_queue_size': cfg.dma.axi_req_fifo_depth, **DMA_TIMING}
        self.core = {'int_loads_in_flight': loads, 'htif_poll_backdoor': HTIF_POLL_BACKDOOR}
        self.tcdm = {'tcdm_size': cfg.tcdm.size, 'tcdm_banks': cfg.tcdm.banks,
            'tcdm_bank_width': cfg.tcdm.bank_width, 'periph_size': cfg.periph_size,
            'zero_mem_size': cfg.zero_mem_size}
        self.cluster_size = cfg.tcdm.size + cfg.periph_size + cfg.zero_mem_size


class SnaxHjsonAttr(Tree):
    """The address map and cluster of the target, as SnitchAttr gives them."""

    def __init__(self, parent, name, arch: SnaxHjson):
        super().__init__(parent, name)
        self.chip = SnaxHjsonAttr.Chip(self, 'chip', arch)
        self.hbm = SnaxHjsonAttr.Hbm(self, 'hbm', arch)

    class Hbm(Tree):

        def __init__(self, parent, name, arch):
            super().__init__(parent, name)
            self.type = 'simple'
            self.size = arch.cfg.dram.length

    class Chip(Tree):

        def __init__(self, parent, name, arch):
            super().__init__(parent, name)
            self.soc = SnaxHjsonAttr.Chip.Soc(self, 'soc', arch)

        class Soc(Tree):

            def __init__(self, parent, name, arch):
                super().__init__(parent, name)
                cfg = arch.cfg
                self.bootrom = Area(self, 'rom', *BOOTROM, description='Bootrom range')
                self.hbm = Area(self, 'hbm', cfg.dram.address, cfg.dram.length,
                    description='DRAM range')
                self.cluster = Area(self, 'cluster', cfg.base, arch.cluster_size,
                    description='Cluster range')
                self.hbm_latency = DRAM_LATENCY
                self.floonoc = False
                self.use_spatz = False
                self.nb_cluster = 1
                self.clusters = [
                    ClusterArch(self, 'cluster', self.get_cluster_base(0), 0,
                        boot_addr=cfg.boot_addr, nb_core_per_cluster=arch.nb_core,
                        misa=arch.misa, snax_acc=arch.snax_acc, dma=arch.dma, core=arch.core,
                        core_latency=CORE_LATENCY, snax_dma_data_width=cfg.dma.data_width,
                        **arch.interconnect, **arch.tcdm)
                ]

            def get_cluster_base(self, id: int):
                return self.cluster.base + id * self.cluster.size

            def get_cluster(self, id: int):
                return self.clusters[id]


class SnaxHjsonBoard(gvsoc.systree.Component):

    def __init__(self, parent, name: str, parser, options):
        super().__init__(parent, name, options=options)

        path = self.declare_user_property(name='hjson', value=str(cfg_file(DEFAULT_HJSON)),
            description='the cluster hjson (snax_cfg.py)')
        arch = SnaxHjson(snax_cfg.load(path))

        clock = Clock_domain(self, 'clock', frequency=CLOCK_FREQUENCY)

        if os.environ.get('USE_GVRUN') is None:
            compile_components()
            properties = SnitchArchProperties()
            properties.nb_core_per_cluster = arch.nb_core
            properties.snax_acc = arch.snax_acc
            properties.dma = arch.dma
            properties.snax_dma_data_width = arch.cfg.dma.data_width
            for key, value in {**arch.interconnect, **arch.tcdm}.items():
                setattr(properties, key, value)
            board_arch = SnitchArch(self, properties=properties)
        else:
            board_arch = SnaxHjsonAttr(self, 'snax_hjson', arch)
        # Exposed so tools like the build process can query the memory map.
        self.set_attributes(board_arch)

        chip = Snitch(self, 'chip', parser, board_arch.chip, None, [])
        mem = memory.memory.Memory(self, 'mem', size=board_arch.hbm.size, atomics=True,
            width_log2=DRAM_WIDTH_LOG2)

        self.bind(clock, 'out', chip, 'clock')
        self.bind(clock, 'out', mem, 'clock')
        self.bind(chip, 'hbm', mem, 'input')


class Target(gvsoc.runner.Target):

    gapy_description = "a SNAX cluster read from its hjson (option hjson)"
    model = SnaxHjsonBoard
    name = "snax_hjson"

    def __init__(self, parser, options=None, name=None):
        super().__init__(parser, options, model=SnaxHjsonBoard, name=name)

