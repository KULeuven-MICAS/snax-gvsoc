#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_cluster's cluster hjson, read for a SNAX-GVSoC target.

    load(path) -> ClusterCfg

The hjson is the contract: snax_cluster's clustergen and snaxgen read the
same file. A design is the cluster file, named after its base platform
(snax_forge.hjson), one streamer file per streamer set, named after the
slot's tag and the set (snax_forge_<design>_streamer_<set>.hjson, the set's
streamer template), and accelerator.json, the accelerators' one description.
The cluster's snax_acc_cfg entry (the slot)
keeps the slot keys; each of its snax_streamer_sets has its name, its
snax_streamer_cfg (a $ref to its streamer file) and its own CSR counts, and
its snax_datapath_cfg is a $ref to accelerator.json, each the whole file.

$ref: {$ref: "#/a/b"} is the value at /a/b of the file it is in;
{$ref: "other.hjson#/a/b"} the value at /a/b of other.hjson, a path relative
to the file that holds the ref, whose own refs are resolved in that file;
{$ref: "other.hjson"} (or "other.hjson#") the whole of other.hjson.
snax_cluster's clustergen and snaxgen resolve only the first form so far
(JsonRef.replace_refs without a base_uri).

What is read, and how a target uses it:

    cluster.name                          ClusterCfg.name
    cluster.boot_addr                     boot_addr
    cluster.cluster_base_addr             base
    cluster.data_width                    tcdm.bank_width (bytes)
    cluster.tcdm.size (KiB), .banks       tcdm.size (bytes), tcdm.banks
    cluster.tcdm.sparse_interconnect      tcdm.sparse_interconnect
    cluster.cluster_periph_size (KiB)     periph_size (bytes)
    cluster.zero_mem_size (KiB)           zero_mem_size (bytes)
    cluster.dma_data_width                dma.data_width (bits)
    cluster.dma_req_fifo_depth            dma.req_fifo_depth
    cluster.dma_axi_req_fifo_depth        dma.axi_req_fifo_depth
    cluster.hives[].cores[]               hives[].cores[] (Core): isa, xdma,
                                          num_int_outstanding_loads, the
                                          slots of snax_acc_cfg (AccSlot)
    dram.address, dram.length             dram.address, dram.length

A slot (AccSlot): snax_acc_name (the tag), snax_tcdm_ports,
snax_narrow_tcdm_ports and snax_wide_tcdm_ports or sparse_interconnect_config,
its streamer sets (AccSlot.sets, StreamerSet: name, streamer, num_rw_csr,
num_ro_csr) and snax_datapath_cfg (accelerator.json, optional; Description).
The sets are snax_streamer_sets, each {name, snax_streamer_cfg (the streamer
template, as the hjson has it), snax_num_rw_csr, snax_num_ro_csr} (snax_cluster's
schema; the slot needs snax_disable_csr_manager); a slot with
snax_streamer_cfg in their place is one set, named after the slot, with the
slot's snax_num_rw_csr and snax_num_ro_csr, as snax_cluster's snaxgen reads it.

accelerator.json, what the standard composite
(snax_accelerator.py) builds the slot's streamers, shells and units from:

    design_point, tag         Description.design_point, .tag
    accelerators[]            Accelerator, one per streamer set, in the
                              sets' order:
      name                    Accelerator.name (the header's <ACC>, the set's)
      inputs, outputs         the outer ports, "<unit>.<port>", in its set's
                              streamer's reader and writer order; a forked
                              input one entry of inputs, the list of
                              the ports its reader feeds, the reader's first
      groups[]                Group: name, csrs (START, JOBS, STATUS,
                              BUSY_COUNTER; with several chains a
                              JOBS_<SINK> per chain in place of JOBS, in the
                              order of their sinks), units, links,
                              fork_links (optional)
    groups[].units[]          Unit: name, brm, datapath (a unit datapath of
                              snax_datapath.hpp's registry: SimdLanes,
                              TreeAccumulate, Mac, SerialAccumulate,
                              LaneAccumulate), ports
                              (per BRM port: port, the datapath's; dir, in or
                              out; dtype, NumPy's name; lanes; a fold's seed,
                              the BRM port seed of a TreeAccumulate or
                              SerialAccumulate, an in port of 1 lane at its
                              output's dtype, read once per job),
                              opType (SimdLanes and Mac),
                              params (op: SimdLanes' and
                              TreeAccumulate's, add, or SimdLanes' axpby, two
                              inputs, k1 * a + k2 * b, axpbypcz, three,
                              (k1 * a + k2 * b + k3 * c) // d, requant, one,
                              min(max(a // d, lo), hi), or threshold, one,
                              hi * min(max(a - k + 1, 0), 1); k: SimdLanes'
                              constant at one stream, its one input, an int of
                              its opType, and threshold's; k1, k2, k3: axpby's
                              and axpbypcz's baked; d, lo, hi: baked, d a power
                              of two; accumulate, regOut: Mac's;
                              rows: a Mac's bank, absent at 1; T: a
                              fold's rate fixed at design time), scalars
                              (SimdLanes' slots read from CSRs, k at one
                              stream, k1, k2, k3, each at its opType, none
                              baked),
                              timing (latency, ii, span: 1 when missing), csrs
                              (its R/W ones: JOB_BEATS, a fold's without T, ROWS,
                              a bank's, of the bits of rows, CARRY, a carried
                              seed's, of JOBS' width, then per scalar K1, or
                              K1_LO and K1_HI at 64 bits, its pin the slot, its
                              width the type's bits, 32 a word)
    groups[].links[]          Link: name, from (an out port, "<unit>.<port>"),
                              to (an in port), depth (0 a wire, >= 1 a buffer)
    groups[].fork_links[]     ForkLink: name, to (a forked in port, not its
                              reader's first), depth (>= 1): the fork's beat
                              through a ring buffer of that many beats
    a CSR                     Csr: name, access (rw, ro), offset (from the
                              accelerator's first CSR), width (its bits, every
                              CSR: START 1, JOBS and JOB_BEATS job_width, STATUS
                              2, BUSY_COUNTER busy_counter_width), pin

Per group the CSRs in CSR order are START, JOBS (or each JOBS_<SINK>), its units'
R/W CSRs, STATUS, BUSY_COUNTER, and the offsets over all groups of all accelerators in that order
are contiguous from 0 (the shell's view): they are read, never computed
(a group's window starts at its START). Unit, group and accelerator names
are each the file's once.

The slot's counts must agree with what its refs give: each mover's
spatial_bounds multiply to its num_channel (snax_cluster's StreamerParam);
snax_tcdm_ports is num_channel summed over every set's movers, and the
narrow and wide ports or the sparse config's widths add up to it; with
accelerator.json, the sets' names and order are the accelerators' (a slot of
one snax_streamer_cfg takes one accelerator, whatever its name); each
accelerator's inputs and outputs are its set's readers and writers in number;
they are exactly the ports on no link, group by group, unit by unit in port
order, a fork's at its reader's place (gen.outer), each link goes from an out port to an in port of its
group's units with the same dtype and lanes, neither end sliced nor packed nor a
broadcast, but a held broadcast bank input, the link's one lane, of depth 1 or more
(gen.link), a fork link goes to a forked port but its reader's first, of depth 1 or more
(gen.link), no port is on two links (gen.link_port), a group's links and
forks connect its units (gen.group), and a fork gives one reader to two or more
outer inputs of one group's chain heads, alike in dtype, lanes, d_in and
broadcast (gen.fork; never beside shared movers, gen.share), the
codes snax-forge's reader gives; each outer port's words per beat (lanes *
its dtype's bits / 64) are its mover's num_channel (a fold's one-lane output:
1); a held input (``hold``) is a broadcast input of a bank (outer, or a held link's), read
once a row, and a carried seed (``carry``) a seed, 0 before CARRY jobs
(gen.args, gen.hold, gen.seed); an outer output with d_out fills one
word with d_out results, on one channel, through SnaxGroup's packer; an outer input with d_in takes one
word on one channel, d_in pops of its lanes through SnaxGroup's slicer, d_in
the word's elements / lanes; a broadcast input (a lane-wise datapath's:
SimdLanes, Mac) keeps its unit's lanes, its reader moving one lane a beat, so
its words per beat and d_in count one lane; a seed has its output's lanes
(one on a fold that sums its lanes, the unit's on a Mac); each set's snax_num_rw_csr and
snax_num_ro_csr are its accelerator's R/W and R/O CSRs. A SimdLanes unit's
opType holds its inputs' NumPy result type (snax_types.hpp's
snax_op_result_type: a signed type with uint64 has none), a Mac's that of a
and b: that type itself, or a wider one the kernel's casts chose.

Everything wrong is a SnaxCfgError naming the file and the key's path:
CfgParseError (not an hjson object), CfgRefError (a $ref that does not
resolve), CfgKeyError (a key missing), CfgTypeError (a value of the wrong
type), CfgSlotError (slot counts, sets or CSRs that disagree with the files,
or both snax_streamer_cfg and snax_streamer_sets); a
target refuses what it cannot model with CfgTargetError (a datapath not in
the registry, a TreeAccumulate op other than add, a unit CSR other than a
fold's JOB_BEATS, a latency or span other than its datapath's, and SnaxGroup's
shape with snax-forge's codes and wording: gen.chain, a group whose links are
not a chain in unit order with the last unit's output the only outer one, or
with a fork the chains it joins, each forward in unit order with only its
sink's output outer (and then its JOBS_<SINK>, one per chain, CfgSlotError);
gen.span, a unit of span > 1 fed by the streamer, but for its seed; gen.seed, a
seed on another datapath, of more than 1 lane, another dtype than its
output's, or on a link). The datapath block before accelerator.json
(<slot>_acc.hjson: unit, control, config, wait, fields) is refused at its key,
and so is accelerator.json's older flat form (name, inputs, outputs, groups
at the top, no accelerators).
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import hjson


class SnaxCfgError(Exception):
    """A cluster hjson SNAX-GVSoC cannot read, at file and path."""

    def __init__(self, file, path: str, why: str):
        self.file = str(file)
        self.path = path
        self.why = why
        super().__init__(f'{self.file}: {path}: {why}' if path else f'{self.file}: {why}')


class CfgParseError(SnaxCfgError):
    """The file is not an hjson object."""


class CfgRefError(SnaxCfgError):
    """A $ref that does not resolve."""


class CfgKeyError(SnaxCfgError):
    """A key missing."""


class CfgTypeError(SnaxCfgError):
    """A value of the wrong type."""


class CfgSlotError(SnaxCfgError):
    """An accelerator slot's counts disagree with what its refs give."""


class CfgTargetError(SnaxCfgError):
    """A cluster hjson a target cannot model."""


# The movers of a streamer template the model has, in snax_cluster's order
# (snax_streamer.py reads these); snax_cluster's data_reader_writer_params is
# refused
MOVERS = ('data_reader_params', 'data_writer_params')
UNMODELLED_MOVERS = ('data_reader_writer_params',)


@dataclass(frozen=True)
class Datapath:
    """A unit datapath's facts (snax-forge's catalogue), each from its params
    (accelerator.json's unit params: accumulate, regOut) where it depends on them."""

    nb_inputs: object           # params -> its input ports
    is_fold: object             # params -> a result every T firings (a JOB_BEATS CSR or params.T)
    latency: object             # params -> its latency
    serial: bool = False        # span = lanes (it reads a beat's lanes one a cycle), else 1
    reduces: bool = False       # its output is one lane, one 64-bit word (the lanes summed)
    typed: bool = False         # it runs its op at an opType, its inputs' result type
    needs_op: bool = False      # params.op is given
    only_op: str = None         # the one op it computes
    seedable: bool = False      # it takes a seed port (SEED), its fold's start once per job
    lanewise: bool = False      # each lane computes on its own: an input may be a broadcast


def _accumulates(params: dict) -> bool:
    return bool(params.get('accumulate', True))


# The unit datapaths SnaxGroup models, one entry each: snax_datapath.hpp's registry but
# LinkBuffer and HaloLink, a link's (LINK_DATAPATHS). A new datapath is an entry here and one in
# the registry.
CATALOGUE = {
    'SimdLanes': Datapath(nb_inputs=lambda p: NAMED[p['op']][0] if p.get('op') in NAMED
                          else 1 if 'k' in p else 2, is_fold=lambda p: False,
                          latency=lambda p: 0, typed=True, needs_op=True, lanewise=True),
    'TreeAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                               latency=lambda p: 1, reduces=True, needs_op=True, only_op='add',
                               seedable=True),
    'Mac': Datapath(nb_inputs=lambda p: 2 if _accumulates(p) else 3, is_fold=_accumulates,
                    latency=lambda p: int(_accumulates(p) or bool(p.get('regOut', False))),
                    typed=True, seedable=True, lanewise=True),
    'SerialAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                                 latency=lambda p: 1, serial=True, reduces=True, seedable=True),
    'LaneAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                               latency=lambda p: 1),
}
# A link's datapaths, the registry's other entries: per name its int params with the least each
# takes, besides its ends' dtype. A LinkBuffer's ring of depth beats; a HaloLink gives its
# consumer's taps inputs one stream's beat as windows shifted by 0 ... taps - 1 elements
LINK_DATAPATHS = {
    'LinkBuffer': {'depth': 1, 'lanes': 1},
    'HaloLink': {'taps': 2, 'lanes': 1},
}


def link_datapath_why(name: str, params: dict, dtype: str) -> str:
    """Why a link's datapath name cannot take params (its ints) at dtype, or '' when it
    can."""
    if name not in LINK_DATAPATHS:
        return f'{name!r}, not a link\'s datapath ({", ".join(LINK_DATAPATHS)})'
    want = LINK_DATAPATHS[name]
    if set(params) != set(want):
        return f'params {sorted(params)}; {name} takes {", ".join(want)}'
    for key, least in want.items():
        v = params[key]
        if type(v) is not int or v < least:
            return f'{key} {v!r}; {name} takes an int of at least {least}'
    if dtype not in DTYPES:
        return f'{dtype!r}, not a NumPy integer type'
    return ''


def halo_held(taps: int, lanes: int) -> int:
    """H, the beats a halo link of taps windows over beats of lanes elements holds:
    ceil((taps - 1) / lanes), 1 at lanes >= 2 with taps 3, 2 at lanes 1."""
    return -(-(taps - 1) // lanes)


def halo_outputs(beats: int, taps: int, lanes: int) -> int:
    """The outputs a job of beats beats gives through a halo link: its first H beats only fill,
    every later one gives one (beats - H, none for a job shorter than the fill)."""
    return max(0, beats - halo_held(taps, lanes))


# A fold's seed port (snax-forge's brm.SEED): its output's lanes (one on a fold that sums its
# lanes), read once per job
SEED = 'seed'
# A group's own CSRs: START and JOBS (with several chains a JOBS_<SINK> per chain, as
# jobs_names names them), read-write, first; STATUS and BUSY_COUNTER, read-only, last
GROUP_RO = ('STATUS', 'BUSY_COUNTER')


def jobs_names(sinks: list) -> list:
    """A group's JOBS CSRs for its chains' sinks, in their order: JOBS for one chain,
    JOBS_<SINK> for each of several (snax-forge's design/streamers.py's jobs_csr)."""
    return ['JOBS'] if len(sinks) == 1 else [f'JOBS_{s.upper()}' for s in sinks]
# The unit CSRs modelled: a fold's JOB_BEATS, a bank's ROWS, a carried seed's CARRY, then its
# scalars' (scalar_csrs)
UNIT_RW = ('JOB_BEATS', 'ROWS', 'CARRY')
# The op names (snax_types.hpp's snax_op_names), and SimdLanes' axpby
OPS = ('add', 'sub', 'mul', 'and', 'or', 'xor', 'min', 'max')
AXPBY = 'axpby'
# SimdLanes' slots: k at one stream (and threshold's), axpby's and axpbypcz's k1 and k2,
# axpbypcz's k3, the divisor d (axpbypcz's and requant's), requant's lo and hi (hi threshold's
# too)
SLOTS = ('k', 'k1', 'k2', 'k3', 'd', 'lo', 'hi')
# The slots a CSR may hold; d, lo and hi are baked into the hardware
CSR_SLOTS = ('k', 'k1', 'k2', 'k3')
# SimdLanes' ops of their own (snax_types.hpp's snax_named_ops): their inputs, the slots they
# need and the ones they take
NAMED = {
    AXPBY: (2, {'k1'}, {'k1', 'k2'}),
    'axpbypcz': (3, {'d'}, {'k1', 'k2', 'k3', 'd'}),
    'requant': (1, {'d', 'lo', 'hi'}, {'d', 'lo', 'hi'}),
    'threshold': (1, {'k', 'hi'}, {'k', 'hi'}),
}


def scalar_csrs(slot: str, dtype: str) -> list:
    """A scalar's CSRs (name, width): K1, or K1_LO and K1_HI at 64 bits (low word first)."""
    width = DTYPES[dtype][0]
    name = slot.upper()
    return [(f'{name}_LO', 32), (f'{name}_HI', 32)] if width == 64 else [(name, width)]
# The keys of the datapath block accelerator.json replaced: refused at their key
OLD_DATAPATH_KEYS = ('unit', 'control', 'config', 'wait', 'fields')


# =============================================================================
# $ref
# =============================================================================


def _parse(path: Path):
    try:
        return hjson.loads(path.read_text())
    except OSError as e:
        raise CfgParseError(path, '', f'cannot read: {e.strerror}') from None
    except hjson.HjsonDecodeError as e:
        raise CfgParseError(path, '', str(e)) from None


class _Resolver:
    """Resolves the $refs of one file and of the files it refers to, each parsed once."""

    def __init__(self):
        self.files = {}

    def top(self, path: Path):
        path = path.resolve()
        if path not in self.files:
            self.files[path] = _parse(path)
        return self.files[path]

    def resolve(self, node, file: Path, at: str, seen=()):
        if isinstance(node, dict):
            if '$ref' in node:
                return self.ref(node, file, at, seen)
            return {k: self.resolve(v, file, f'{at}.{k}' if at else k, seen)
                for k, v in node.items()}
        if isinstance(node, list):
            return [self.resolve(v, file, f'{at}[{i}]', seen) for i, v in enumerate(node)]
        return node

    def ref(self, node: dict, file: Path, at: str, seen):
        ref = node['$ref']
        if len(node) != 1 or not isinstance(ref, str) or not ref or ref == '#':
            raise CfgRefError(file, at,
                f'{dict(node)!r} is not {{$ref: "[file]#/<pointer>"}} or {{$ref: "<file>"}}')
        # A file without a pointer is the whole file
        name, _, pointer = ref.partition('#')
        target = (file.parent / name).resolve() if name else file.resolve()
        if pointer and not pointer.startswith('/'):
            raise CfgRefError(file, at, f'{ref!r}: the pointer must start with /')
        key = (target, pointer)
        if key in seen:
            raise CfgRefError(file, at, f'{ref!r} refers to itself')
        if not target.is_file():
            raise CfgRefError(file, at, f'{ref!r}: no file {target}')
        value = self.top(target)
        for part in pointer[1:].split('/') if pointer else []:
            part = part.replace('~1', '/').replace('~0', '~')
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                raise CfgRefError(file, at, f'{ref!r}: no {part!r} in {target.name}')
        return self.resolve(value, target, f'{target.name}#{pointer}', (*seen, key))


# =============================================================================
# Typed access
# =============================================================================


_TYPE_NAMES = {int: 'an integer', str: 'a string', bool: 'a boolean', list: 'a list',
    dict: 'an object'}


class _Node:
    """A resolved object of the file, with its path, for typed access."""

    def __init__(self, file: Path, value: dict, at: str):
        self.file = file
        self.value = value
        self.at = at

    def where(self, key) -> str:
        return f'{self.at}.{key}' if self.at else key

    def get(self, key, kind, default=...):
        if key not in self.value:
            if default is ...:
                raise CfgKeyError(self.file, self.where(key), 'missing')
            return default
        value = self.value[key]
        # hjson gives a bool for true and false, which isinstance(int) accepts
        if (kind is int and isinstance(value, bool)) or not isinstance(value, kind):
            raise CfgTypeError(self.file, self.where(key),
                f'must be {_TYPE_NAMES[kind]}, got {value!r}')
        return value

    def node(self, key, default=...):
        value = self.get(key, dict, default)
        return None if value is None else _Node(self.file, value, self.where(key))

    def nodes(self, key, default=...):
        """A list of objects."""
        values = self.get(key, list, default)
        if values is None:
            return None
        out = []
        for i, value in enumerate(values):
            if not isinstance(value, dict):
                raise CfgTypeError(self.file, f'{self.where(key)}[{i}]',
                    f'must be an object, got {value!r}')
            out.append(_Node(self.file, value, f'{self.where(key)}[{i}]'))
        return out


# =============================================================================
# The configuration
# =============================================================================


@dataclass(frozen=True)
class Tcdm:
    """The cluster's L1: size in bytes, banks, a bank's width in bytes, the interconnect."""

    size: int
    banks: int
    bank_width: int
    sparse_interconnect: bool


@dataclass(frozen=True)
class Dma:
    """The cluster's DMA: data width in bits, its two queue depths."""

    data_width: int
    req_fifo_depth: int
    axi_req_fifo_depth: int


@dataclass(frozen=True)
class Dram:
    address: int
    length: int


@dataclass(frozen=True)
class Csr:
    """A CSR of accelerator.json: its offset from the accelerator's first CSR, its width
    (its bits; a read gives them, the upper bits 0) and a scalar's datapath pin (None)."""

    name: str
    access: str
    offset: int
    width: int = None
    pin: str = None


@dataclass(frozen=True)
class Port:
    """A unit's BRM port: the datapath's port, its dtype (NumPy's name), its lanes, its
    direction (in or out) and, on an outer output a packer feeds, d_out, on an outer input a
    slicer feeds, d_in; ``broadcast`` on an outer input whose reader gives one lane to all of
    them; ``hold`` on one read once a bank row and kept; ``carry`` on a seed that is its unit's
    own output, 0 before CARRY jobs."""

    port: str
    dtype: str
    lanes: int
    dir: str
    d_out: int = 1
    d_in: int = 1
    broadcast: bool = False
    hold: bool = False
    carry: bool = False

    @property
    def stream_lanes(self) -> int:
        """The lanes its reader moves a beat: one for a broadcast, else its lanes."""
        return 1 if self.broadcast else self.lanes

    @property
    def width(self) -> int:
        return DTYPES[self.dtype][0]

    @property
    def signed(self) -> bool:
        return DTYPES[self.dtype][1]


@dataclass(frozen=True)
class Unit:
    """A unit of a group: its datapath, its ports by BRM port (in the BRM's order), its op
    type (SimdLanes; None for a fold), params, timing and its R/W CSRs."""

    name: str
    brm: str
    datapath: str
    ports: dict
    op_type: str
    params: dict
    latency: int
    ii: int
    csrs: list
    span: int = 1
    scalars: dict = field(default_factory=dict)

    @property
    def seeded(self) -> bool:
        """It has a seed port (SEED), a fold's start read once per job."""
        return SEED in self.ports

    @property
    def slot_params(self) -> dict:
        """Its params with each scalar's slot (None: read from its CSR), as CATALOGUE's facts
        read them: a one-stream SimdLanes has k, baked or not."""
        return {**self.params, **dict.fromkeys(self.scalars)}


@dataclass(frozen=True)
class Link:
    """A link of a group: from an out port to an in port, each "<unit>.<port>"; depth
    0 a wire, >= 1 a buffer of that many beats."""

    name: str
    from_: str
    to: str
    depth: int


@dataclass(frozen=True)
class ForkLink:
    """A fork's buffered branch: ``to`` a forked in port, not its reader's first, fed through
    a ring buffer of ``depth`` beats, one pushed each beat the fork takes."""

    name: str
    to: str
    depth: int


@dataclass(frozen=True)
class Group:
    """A group: its own CSRs (START, JOBS or a JOBS_<SINK> per chain, STATUS,
    BUSY_COUNTER), its units and links, and its forks' buffered branches."""

    name: str
    csrs: list
    units: list
    links: list
    fork_links: list = field(default_factory=list)

    @property
    def window(self) -> list:
        """Its CSRs in CSR order: START, its JOBS, its units' R/W CSRs, STATUS, BUSY_COUNTER."""
        own = [c for c in self.csrs if c.access == 'rw']
        return (own + [c for u in self.units for c in u.csrs]
                + [c for c in self.csrs if c.access == 'ro'])

    @property
    def jobs(self) -> list:
        """Its JOBS CSRs' names: JOBS, or a JOBS_<SINK> per chain in its sinks' order."""
        return [c.name for c in self.csrs if c.access == 'rw' and c.name != 'START']

    def chains(self) -> list:
        """Its chains, each its units' names from head to sink along its links, in the order
        of their sinks among its units (one for a group no fork joins)."""
        nxt = {k.from_.split('.')[0]: k.to.split('.')[0] for k in self.links}
        prev = {b: a for a, b in nxt.items()}
        out = []
        for u in self.units:
            if u.name in nxt:
                continue
            chain = [u.name]
            while chain[0] in prev:
                chain.insert(0, prev[chain[0]])
            out.append(chain)
        return out

    @property
    def rw(self) -> list:
        """Its read-write CSRs' names in CSR order: START, its JOBS, the units'."""
        return [c.name for c in self.window if c.access == 'rw']

    @property
    def rw_widths(self) -> list:
        """Its read-write CSRs' widths, in the order of rw."""
        return [c.width for c in self.window if c.access == 'rw']

    @property
    def busy_counter_width(self) -> int:
        """Its BUSY_COUNTER's width: the counter saturates at 2^width - 1."""
        return next(c.width for c in self.csrs if c.name == 'BUSY_COUNTER')


@dataclass(frozen=True)
class MoverUser:
    """A group's port on a shared mover: the group, the port
    ("<unit>.<port>", one of the accelerator's inputs or outputs) and its words per beat, at
    most the mover's."""

    group: str
    port: str
    num_channel: int


@dataclass(frozen=True)
class SharedMover:
    """A mover of a streamer set whose groups share its movers, in the
    streamer's order: its name (reader<i>, writer<j>), role (read or write), channels, whether
    it has configurable_channel (masked: a user narrower than it) and its users, at most one
    per group."""

    name: str
    role: str
    num_channel: int
    masked: bool
    users: list


@dataclass(frozen=True)
class PortMux:
    """The data-side mux of a shared streamer set: its groups in
    PORT_MUX_SEL's order, and PORT_MUX_SEL, the accelerator's last CSR."""

    groups: list
    csr: Csr


@dataclass(frozen=True)
class Accelerator:
    """An accelerator of accelerator.json, one streamer set's: its outer ports, in its set's
    reader and writer order, and its groups. With share_ports its groups
    share the set's movers: movers says which port of each group each mover serves, and
    port_mux which group is connected; its outer ports are then in no mover order."""

    name: str
    inputs: list    # a fork's ports as one entry, a list, the reader's first
    outputs: list
    groups: list
    movers: list = field(default_factory=list)
    port_mux: PortMux = None

    @property
    def readers(self) -> list:
        """Its input ports with a reader of their own, in reader order: a fork's by its
        first port."""
        return [x if isinstance(x, str) else x[0] for x in self.inputs]

    @property
    def forks(self) -> list:
        """Its forked inputs, each the ports one reader feeds, the reader's first."""
        return [list(x) for x in self.inputs if not isinstance(x, str)]

    @property
    def input_ports(self) -> list:
        """Every outer input port, a fork's each, in inputs' order."""
        return [p for x in self.inputs for p in ([x] if isinstance(x, str) else x)]

    @property
    def csrs(self) -> list:
        """Its CSRs in CSR order: its groups' windows, then PORT_MUX_SEL when shared."""
        own = [] if self.port_mux is None else [self.port_mux.csr]
        return [c for g in self.groups for c in g.window] + own

    @property
    def num_rw(self) -> int:
        return sum(c.access == 'rw' for c in self.csrs)

    @property
    def num_ro(self) -> int:
        return sum(c.access == 'ro' for c in self.csrs)

    def unit(self, name: str) -> Unit:
        return next(u for g in self.groups for u in g.units if u.name == name)

    def ports_of(self, unit: str, outer: list) -> list:
        """The (index, BRM port) of each of outer's entries ("<unit>.<port>", or a fork's
        list of them) that name unit."""
        return [(i, p.split('.', 1)[1]) for i, entry in enumerate(outer)
                for p in ([entry] if isinstance(entry, str) else entry)
                if p.split('.', 1)[0] == unit]


@dataclass(frozen=True)
class Description:
    """accelerator.json: the design point, the tag and the
    accelerators, one per streamer set, in the sets' order."""

    design_point: str
    tag: str
    accelerators: list

    @property
    def groups(self) -> list:
        """Every group, accelerator by accelerator."""
        return [g for a in self.accelerators for g in a.groups]

    @property
    def csrs(self) -> list:
        """Every CSR in CSR order: the offsets 0, 1, ..."""
        return [c for a in self.accelerators for c in a.csrs]


@dataclass(frozen=True)
class StreamerSet:
    """A streamer set of a slot (snax_streamer_sets[k]; a slot's snax_streamer_cfg is one):
    its name, its streamer template as the hjson has it, its accelerator's own CSR counts,
    and the key its values are at, from the slot ('' for the slot's own keys)."""

    name: str
    streamer: dict
    num_rw_csr: int
    num_ro_csr: int
    at: str = ''

    def key(self, key: str) -> str:
        """key's path from the slot."""
        return f'{self.at}.{key}' if self.at else key


@dataclass(frozen=True)
class AccSlot:
    """One snax_acc_cfg entry of a core: the slot's keys, its streamer sets in order, and its
    accelerator.json when the slot has one (None otherwise)."""

    name: str
    tcdm_ports: int
    narrow_tcdm_ports: int
    wide_tcdm_ports: int
    sparse_config: list
    sets: list
    description: Description
    at: str

    @property
    def num_rw_csr(self) -> int:
        """The sets' read-write CSRs, their streamers' not counted."""
        return sum(s.num_rw_csr for s in self.sets)

    @property
    def num_ro_csr(self) -> int:
        """The sets' read-only CSRs, their streamers' not counted."""
        return sum(s.num_ro_csr for s in self.sets)


@dataclass(frozen=True)
class Core:
    isa: str
    xdma: bool
    num_int_outstanding_loads: int
    accelerators: list

    @property
    def misa(self) -> int:
        return misa(self.isa)


@dataclass(frozen=True)
class Hive:
    cores: list


@dataclass(frozen=True)
class ClusterCfg:
    """A cluster hjson, $refs resolved; see the module doc."""

    path: Path
    name: str
    boot_addr: int
    base: int
    tcdm: Tcdm
    periph_size: int
    zero_mem_size: int
    dma: Dma
    dram: Dram
    hives: list = field(default_factory=list)

    @property
    def cores(self) -> list:
        """Every core of every hive, in hart order."""
        return [core for hive in self.hives for core in hive.cores]


def misa(isa: str) -> int:
    """The misa CSR of an ISA string such as rv32ima: MXL (1 for 32 bit, 2 for 64) and one bit
    per base letter; G is IMAFD."""
    name = isa.lower().split('_')[0]
    if not name.startswith('rv') or name[2:4] not in ('32', '64'):
        raise ValueError(f'ISA {isa!r} is not rv32... or rv64...')
    letters = name[4:].replace('g', 'imafd')
    if not letters.isalpha():
        raise ValueError(f'ISA {isa!r}: base letters {letters!r}')
    value = (1 if name[2:4] == '32' else 2) << (30 if name[2:4] == '32' else 62)
    for letter in letters:
        value |= 1 << (ord(letter) - ord('a'))
    return value


def spatial_mismatch(spatial_bounds: list, num_channel: int):
    """Why a mover's spatial bounds do not fit its channels, or None: snax_cluster's
    StreamerParam requires their product to be num_channel."""
    product = math.prod(spatial_bounds)
    if product == num_channel:
        return None
    return (f'spatial bounds {spatial_bounds} unroll {product} channels, but num_channel is '
            f'{num_channel}: snax_cluster\'s StreamerParam requires spatialBounds.product == '
            'numChannel')


# The keys of a mover group in the hjson's streamer template that the model
# reads; any other key is refused by name. dynamicPriority (default true) and
# higherStaticPriority (default false) are read as stream_param_gen.scala.tpl
# reads them.
MOVER_KEYS = ['spatial_bounds', 'temporal_dim', 'num_channel', 'fifo_depth', 'dynamicPriority',
    'higherStaticPriority', 'configurable_channel']
# The keys of the streamer template the model reads (MOVERS), or that do not change it
TEMPLATE_KEYS = [*MOVERS, 'snax_library_name']


def check_template(template: dict):
    """Refuses a streamer template the model does not cover: a key it does not read, or a
    mover whose spatial bounds do not multiply to its num_channel, as snax_cluster's
    StreamerParam requires (spatial_mismatch). A RuntimeError naming it.

    Parameters
    ----------
    template : dict
        The streamer template, as the cluster hjson gives it (e.g.
        snax_forge_streamer.hjson).
    """
    for key in template:
        if key not in TEMPLATE_KEYS:
            raise RuntimeError(f'Streamer template key not modelled: {key}')
    for group in MOVERS:
        for key in template.get(group, {}):
            if key not in MOVER_KEYS:
                raise RuntimeError(f'Streamer template key not modelled: {group}.{key}')
    for group in MOVERS:
        params = template.get(group, {})
        for i, (bounds, channels) in enumerate(zip(params.get('spatial_bounds', []),
                                                   params.get('num_channel', []))):
            why = spatial_mismatch(list(bounds), channels)
            if why is not None:
                raise RuntimeError(f'{group}[{i}]: {why}')


def template_movers(template: dict) -> list:
    """The template's movers in the streamer's order, readers first: each {name (reader<i>,
    writer<j>), is_reader, num_channel, configurable_channel}."""
    out = []
    for group, kind in (('data_reader_params', 'reader'), ('data_writer_params', 'writer')):
        params = template.get(group, {})
        flags = params.get('configurable_channel', [])
        for i, channels in enumerate(params.get('num_channel', [])):
            out.append({'name': f'{kind}{i}', 'is_reader': kind == 'reader',
                        'num_channel': channels,
                        'configurable_channel': i < len(flags) and bool(flags[i])})
    return out


def streamer_channels(template: dict) -> int:
    """The streamer's TCDM ports: num_channel summed over its movers."""
    return sum(sum(template.get(mover, {}).get('num_channel', [])) for mover in MOVERS)


def _names(node: _Node, key, default=...) -> list:
    """A list of strings."""
    values = node.get(key, list, default)
    if values is not None and not all(isinstance(v, str) for v in values):
        raise CfgTypeError(node.file, node.where(key), f'must be a list of strings, got {values!r}')
    return values


def _inputs(node: _Node) -> list:
    """An accelerator's inputs: each a port, or a fork's list of two or more ports."""
    values = node.get('inputs', list)
    for v in values:
        if not (isinstance(v, str) or (isinstance(v, list) and v
                                       and all(isinstance(x, str) for x in v))):
            raise CfgTypeError(node.file, node.where('inputs'), 'must be a list of ports, each a '
                               f'string or a fork\'s list of strings, got {values!r}')
    return [v if isinstance(v, str) else list(v) for v in values]


def type_name(width: int, signed: bool) -> str:
    """NumPy's name of an integer type: int32, uint8, ..."""
    return f'{"int" if signed else "uint"}{width}'


# NumPy's integer type names -> (width, signed)
DTYPES = {type_name(w, s): (w, s) for w in (8, 16, 32, 64) for s in (True, False)}


def fits(value: int, t: tuple) -> bool:
    """value is one of integer type t's (width, signed)."""
    width, signed = t
    lo, hi = (-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else (0, (1 << width) - 1)
    return lo <= value <= hi


def result_type(a: tuple, b: tuple):
    """NumPy's result type of two integer types (width, signed), as snax_types.hpp's
    snax_op_result_type; None past 64 bits (a signed type with uint64: NumPy's float64)."""
    if a[1] == b[1]:
        return max(a[0], b[0]), a[1]
    s, u = (a, b) if a[1] else (b, a)
    if s[0] > u[0]:
        return s
    return (2 * u[0], True) if 2 * u[0] <= 64 else None


def _csr(node: _Node) -> Csr:
    access = node.get('access', str)
    if access not in ('rw', 'ro'):
        raise CfgTypeError(node.file, node.where('access'), f'{access!r}, must be rw or ro')
    width = node.get('width', int, None)
    if width is None:
        raise CfgKeyError(node.file, node.where('width'), 'missing: every CSR has a width')
    if not 1 <= width <= 32:
        raise CfgTypeError(node.file, node.where('width'), f'{width}, must be 1 to 32 bits')
    offset = node.get('offset', int)
    if offset < 0:
        raise CfgTypeError(node.file, node.where('offset'), f'{offset}, must be 0 or more')
    return Csr(name=node.get('name', str), access=access, offset=offset, width=width,
               pin=node.get('pin', str, None))


def _port(node: _Node) -> Port:
    dtype = node.get('dtype', str)
    if dtype not in DTYPES:
        raise CfgTypeError(node.file, node.where('dtype'),
            f'{dtype!r}, not a NumPy integer type ({", ".join(DTYPES)})')
    lanes = node.get('lanes', int)
    if lanes < 1:
        raise CfgTypeError(node.file, node.where('lanes'), f'{lanes}, must be 1 or more')
    direction = node.get('dir', str)
    if direction not in ('in', 'out'):
        raise CfgTypeError(node.file, node.where('dir'), f'{direction!r}, must be in or out')
    d_out = node.get('d_out', int, 1)
    if d_out not in (1, 2, 4, 8) or (d_out > 1 and direction != 'out'):
        raise CfgTypeError(node.file, node.where('d_out'),
            f'{d_out}: an output\'s results per word, 2, 4 or 8 (absent at 1)')
    d_in = node.get('d_in', int, 1)
    if d_in not in (1, 2, 4, 8) or (d_in > 1 and direction != 'in'):
        raise CfgTypeError(node.file, node.where('d_in'),
            f'{d_in}: an input\'s pops per word, 2, 4 or 8 (absent at 1)')
    broadcast = node.get('broadcast', bool, False)
    if broadcast and (direction != 'in' or lanes < 2):
        raise CfgTypeError(node.file, node.where('broadcast'),
            'an input of 2 lanes or more takes a broadcast, one lane given to all of them '
            '(absent when false)')
    hold, carry = node.get('hold', bool, False), node.get('carry', bool, False)
    if (hold or carry) and direction != 'in':
        raise CfgTypeError(node.file, node.where('hold' if hold else 'carry'),
            'an input is held or carried (absent when false)')
    return Port(port=node.get('port', str), dtype=dtype, lanes=lanes, dir=direction, d_out=d_out,
                d_in=d_in, broadcast=broadcast, hold=hold, carry=carry)


def _unit(node: _Node) -> Unit:
    datapath = node.get('datapath', str)
    if datapath not in CATALOGUE:
        raise CfgTargetError(node.file, node.where('datapath'),
            f'{datapath!r}, not a datapath SnaxGroup models ({", ".join(CATALOGUE)})')
    facts = CATALOGUE[datapath]
    ports = node.node('ports')
    if not ports.value:
        raise CfgTypeError(node.file, node.where('ports'), 'no port')
    timing = node.node('timing')
    latency, ii = timing.get('latency', int), timing.get('ii', int)
    span = timing.get('span', int, 1)
    if latency < 0:
        raise CfgTypeError(node.file, timing.where('latency'), f'{latency}, must be 0 or more')
    if ii < 1:
        raise CfgTypeError(node.file, timing.where('ii'), f'{ii}, must be 1 or more')
    if span < 1:
        raise CfgTypeError(node.file, timing.where('span'), f'{span}, must be 1 or more')
    params = node.node('params')
    op = params.get('op', str, None)
    if facts.needs_op and op is None:
        raise CfgKeyError(node.file, params.where('op'), f'missing: {datapath} needs an op')
    if op is not None and op not in OPS and not (op in NAMED and datapath == 'SimdLanes'):
        raise CfgTypeError(node.file, params.where('op'), f'{op!r}, not an op ({", ".join(OPS)}; '
                           f'SimdLanes\' {", ".join(NAMED)})')
    if facts.only_op is not None and op != facts.only_op:
        raise CfgTargetError(node.file, params.where('op'),
            f'{op!r}: {datapath} {facts.only_op}s; a fold of another op is not modelled')
    for key in ('accumulate', 'regOut'):
        params.get(key, bool, None)
    rows = params.get('rows', int, 1)
    if rows < 1:
        raise CfgTargetError(node.file, params.where('rows'),
            f'gen.args: rows {rows}; a bank has one row or more')
    k = params.get('k', int, None)
    if k is not None and datapath != 'SimdLanes':
        raise CfgTypeError(node.file, params.where('k'), f'a {datapath} unit has no constant k')
    baked = {s: params.get(s, int, None) for s in SLOTS}
    scalars = node.get('scalars', dict, {})
    for s, dtype in scalars.items():
        if datapath != 'SimdLanes' or s not in CSR_SLOTS or baked[s] is not None:
            raise CfgTypeError(node.file, f'{node.where("scalars")}.{s}',
                f'not a slot of SimdLanes a CSR holds ({", ".join(CSR_SLOTS)}) that is not baked')
    given = {s for s in SLOTS if baked[s] is not None or s in scalars}
    takes = NAMED[op][2] if op in NAMED else {'k'}
    for s in sorted(given - takes, key=SLOTS.index):
        owners = "'s and ".join(o for o, (_, _, t) in NAMED.items() if s in t)
        raise CfgTypeError(node.file, params.where(s), f'{s} is {owners}\'s, not {op}\'s')
    for s in sorted(NAMED[op][1] - given if op in NAMED else (), key=SLOTS.index):
        raise CfgKeyError(node.file, params.where(s), f'missing: {op} takes {s}, baked in params'
                          + (' or read from its CSR (scalars)' if s in CSR_SLOTS else ''))
    d = baked['d']
    if d is not None and (d < 1 or d & (d - 1)):
        raise CfgTypeError(node.file, params.where('d'),
            f'{d}: not a power of two; the unit divides by shifting')
    t = params.get('T', int, None)
    if t is not None and t < 1:
        raise CfgTypeError(node.file, params.where('T'), f'{t}, must be 1 or more')
    op_type = node.get('opType', str, None)
    typed = facts.typed
    if not typed and op_type is not None:
        raise CfgTypeError(node.file, node.where('opType'), f'a {datapath} unit has none')
    if typed and op_type is None:
        raise CfgKeyError(node.file, node.where('opType'),
            f'missing: a {datapath} unit runs its op at its inputs\' result type')
    if op_type is not None and op_type not in DTYPES:
        raise CfgTypeError(node.file, node.where('opType'), f'{op_type!r}, not a NumPy integer type')
    for s, v in baked.items():
        if v is not None and not fits(v, DTYPES[op_type]):
            raise CfgTypeError(node.file, params.where(s), f'{v}: does not fit the opType {op_type}')
    for s, dtype in scalars.items():
        if dtype != op_type:
            raise CfgTypeError(node.file, f'{node.where("scalars")}.{s}',
                f'{dtype!r}: a scalar is at the opType, {op_type}')
    csrs = [_csr(c) for c in node.nodes('csrs')]
    own = [c for c in csrs if c.pin is None]
    for i, c in enumerate(csrs):
        if c.access != 'rw' or (c.pin is None and c.name not in UNIT_RW):
            raise CfgTargetError(node.file, f'{node.where("csrs")}[{i}]',
                f'{c.name} ({c.access}): the unit CSRs modelled are {", ".join(UNIT_RW)} and its '
                'scalars\' (rw)')
    want = [(n, w, s) for s, dtype in scalars.items() for n, w in scalar_csrs(s, dtype)]
    got = [(c.name, c.width, c.pin) for c in csrs if c.pin is not None]
    if got != want or csrs[:len(own)] != own:
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: the scalars {scalars} are the CSRs (name, width, pin) '
            f'{want} after the JOB_BEATS')
    fold = facts.is_fold(params.value)
    if (fold and t is None) != ('JOB_BEATS' in [c.name for c in csrs]):
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: a fold without params.T has JOB_BEATS, any other unit '
            'none')
    unit_ports = {key: _port(ports.node(key)) for key in ports.value}
    carried = [k for k, x in unit_ports.items() if x.carry]
    mine = (['JOB_BEATS'] if fold and t is None else []) + (['ROWS'] if rows > 1 else []) + (
        ['CARRY'] if carried else [])
    if [c.name for c in own] != mine:
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: a unit\'s own CSRs are {mine} (JOB_BEATS, a fold\'s '
            'without params.T; ROWS, a bank\'s; CARRY, a carried seed\'s), then its scalars\'')
    if rows > 1 and own[mine.index('ROWS')].width != rows.bit_length():
        raise CfgSlotError(node.file, node.where('csrs'),
            f'ROWS: width {own[mine.index("ROWS")].width}; a bank of {rows} rows has ROWS of '
            f'{rows.bit_length()} bits')
    if rows > 1 and (datapath != 'Mac' or not fold):
        raise CfgTargetError(node.file, params.where('rows'),
            f'gen.args: rows {rows}; only an accumulating Mac has a bank (set accumulate '
            'true, or rows 1)')
    if [k for k in carried if k != SEED]:
        raise CfgTargetError(node.file, f'{node.where("ports")}.{carried[0]}',
            'gen.seed: a carried port is a fold\'s seed, its unit\'s own output: carry only '
            'the seed')
    for key, x in unit_ports.items():
        if x.hold and (rows == 1 or not x.broadcast or key == SEED):
            raise CfgTargetError(node.file, f'{node.where("ports")}.{key}',
                f'gen.hold: port {key} is held for a bank row but is not a broadcast input of a '
                'bank; a held input is one lane for all for now')
    lanes = next(iter(unit_ports.values())).lanes
    if SEED in unit_ports:
        seed = unit_ports[SEED]
        outs = [x for x in unit_ports.values() if x.dir == 'out']
        seed_lanes = 1 if facts.reduces else lanes  # its output's lanes
        why = (f'{datapath} takes no seed (TreeAccumulate, SerialAccumulate and Mac do)'
               if not facts.seedable else f'{datapath} takes a seed only as a fold'
               if not fold else 'an in port' if seed.dir != 'in'
               else f'{seed.lanes} lanes, a seed has its output\'s {seed_lanes}'
               if seed.lanes != seed_lanes
               else 'a seed is not a broadcast' if seed.broadcast
               else f'{seed.dtype}, a seed is its output\'s {outs[0].dtype}'
               if outs and seed.dtype != outs[0].dtype
               else f'the last in port, after {list(unit_ports)}' if
               [k for k, x in unit_ports.items() if x.dir == 'in'][-1] != SEED else None)
        if why is not None:
            raise CfgTargetError(node.file, f'{node.where("ports")}.{SEED}', f'gen.seed: {why}')
    for key, p in unit_ports.items():
        if p.broadcast and not facts.lanewise:
            raise CfgTargetError(node.file, f'{node.where("ports")}.{key}',
                f'gen.broadcast: {datapath} sums its lanes; a broadcast feeds a datapath whose '
                'lanes compute on their own (SimdLanes, Mac)')
    want = (facts.latency(params.value), lanes if facts.serial else 1)
    if (latency, ii, span) != (*want[:1], 1, want[1]):
        raise CfgTargetError(node.file, node.where('timing'),
            f'gen.timing: latency {latency}, ii {ii}, span {span}; {datapath} here is latency '
            f'{want[0]}, ii 1, span {want[1]}')
    return Unit(name=node.get('name', str), brm=node.get('brm', str), datapath=datapath,
                ports=unit_ports, op_type=op_type, params=dict(params.value), latency=latency,
                ii=ii, csrs=csrs, span=span, scalars=dict(scalars))


def _link(node: _Node) -> Link:
    depth = node.get('depth', int)
    if depth < 0:
        raise CfgSlotError(node.file, node.where('depth'),
                           f'gen.link: depth {depth}; 0 is a wire, >= 1 a buffer')
    return Link(name=node.get('name', str), from_=node.get('from', str), to=node.get('to', str),
                depth=depth)


def _fork_link(node: _Node) -> ForkLink:
    depth = node.get('depth', int)
    if depth < 1:
        raise CfgSlotError(node.file, node.where('depth'),
                           f"gen.link: depth {depth}; a fork's branch is a buffer, depth 1 or more")
    return ForkLink(name=node.get('name', str), to=node.get('to', str), depth=depth)


def _group(node: _Node) -> Group:
    links = [_link(k) for k in node.nodes('links')]
    fork_links = [_fork_link(k) for k in node.nodes('fork_links', [])]
    units = [_unit(u) for u in node.nodes('units')]
    if not units:
        raise CfgTypeError(node.file, node.where('units'), 'no unit')
    csrs = [_csr(c) for c in node.nodes('csrs')]
    own = [(c.name, c.access) for c in csrs]
    jobs = [n for n, _ in own[1:-2]]
    many = len(jobs) > 1 and all(re.fullmatch(r'JOBS_\w+', n) for n in jobs)
    want = ([('START', 'rw')] + [(n, 'rw') for n in (jobs if many else ['JOBS'])]
            + [(n, 'ro') for n in GROUP_RO])
    if own != want:
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: a group\'s own CSRs are START, JOBS (rw), STATUS, '
            'BUSY_COUNTER (ro), in that order, with several chains a JOBS_<SINK> per chain in '
            'place of JOBS')
    jobs_width = next(c.width for c in csrs if c.access == 'rw' and c.name != 'START')
    for k, u in enumerate(units):
        for c in u.csrs:
            if c.name == 'CARRY' and c.width != jobs_width:
                raise CfgSlotError(node.file, f'{node.where("units")}[{k}].csrs',
                    f'CARRY: width {c.width}; it counts jobs, as JOBS ({jobs_width} bits)')
    return Group(name=node.get('name', str), csrs=csrs, units=units, links=links,
                 fork_links=fork_links)


def _mover(node: _Node) -> SharedMover:
    role = node.get('role', str)
    if role not in ('read', 'write'):
        raise CfgTypeError(node.file, node.where('role'), f'{role!r}, must be read or write')
    users = [MoverUser(group=u.get('group', str), port=u.get('port', str),
                       num_channel=u.get('num_channel', int)) for u in node.nodes('users')]
    return SharedMover(name=node.get('name', str), role=role,
                       num_channel=node.get('num_channel', int), masked=node.get('masked', bool),
                       users=users)


def _port_mux(node: _Node) -> PortMux:
    return PortMux(groups=_names(node, 'groups'), csr=_csr(node.node('csr')))


def _accelerator(node: _Node) -> Accelerator:
    """An entry of accelerator.json's accelerators."""
    movers = node.nodes('movers', None)
    mux = node.node('port_mux', None)
    acc = Accelerator(
        name=node.get('name', str),
        inputs=_inputs(node),
        outputs=_names(node, 'outputs'),
        groups=[_group(g) for g in node.nodes('groups')],
        movers=[] if movers is None else [_mover(m) for m in movers],
        port_mux=None if mux is None else _port_mux(mux),
    )
    if not acc.groups:
        raise CfgTypeError(node.file, node.where('groups'), 'no group')
    if (movers is None) != (mux is None):
        raise CfgSlotError(node.file, node.where('movers' if movers is None else 'port_mux'),
            'missing: a shared streamer set has both movers and port_mux')
    return acc


def _check_shared(at: _Node, acc: Accelerator):
    """A shared set's movers and port mux against its groups and outer ports:
    port_mux names every group once and PORT_MUX_SEL is R/W; each user is a group's outer port
    of the mover's direction, at most as wide as the mover, one per group and mover, a narrower
    one only on a masked mover; every outer port is on one mover."""
    def fail(key, why):
        raise CfgSlotError(at.file, at.where(key), why)

    if acc.forks:
        fail('inputs', f'gen.share: accelerator {acc.name}: a fork and shared movers in one '
             'accelerator; share_ports or fork_read, not both')
    groups = [g.name for g in acc.groups]
    mux = acc.port_mux
    if sorted(mux.groups) != sorted(groups):
        fail('port_mux.groups', f'{mux.groups}, but accelerator {acc.name}\'s groups are '
             f'{groups}: each once')
    if (mux.csr.name, mux.csr.access) != ('PORT_MUX_SEL', 'rw'):
        fail('port_mux.csr', f'{mux.csr.name} ({mux.csr.access}), must be PORT_MUX_SEL (rw)')
    unit_group = {u.name: g.name for g in acc.groups for u in g.units}
    placed = {}
    for k, m in enumerate(acc.movers):
        outer = acc.inputs if m.role == 'read' else acc.outputs
        seen = set()
        for i, user in enumerate(m.users):
            where = f'movers[{k}].users[{i}]'
            if user.port not in outer:
                fail(where, f'{user.port!r} is not one of accelerator {acc.name}\'s '
                     f'{"inputs" if m.role == "read" else "outputs"}, the ports {m.name} '
                     'can serve')
            if unit_group[user.port.split('.', 1)[0]] != user.group:
                fail(where, f'{user.port!r} is not a port of group {user.group}')
            if user.group in seen:
                fail(where, f'a second port of group {user.group} on {m.name}')
            seen.add(user.group)
            if not 1 <= user.num_channel <= m.num_channel:
                fail(where, f'{user.port} has {user.num_channel} channels, {m.name} '
                     f'{m.num_channel}')
            if user.num_channel < m.num_channel and not m.masked:
                fail(where, f'{user.port} is narrower than {m.name}, which is not masked '
                     '(configurable_channel)')
            if user.port in placed:
                fail(where, f'{user.port} is on {placed[user.port]} already')
            placed[user.port] = m.name
    for entry in [*acc.input_ports, *acc.outputs]:
        if entry not in placed:
            fail('movers', f'{entry} is on no mover')


# The top-level keys of accelerator.json's older flat form (one accelerator, no accelerators list)
FLAT_KEYS = ('name', 'inputs', 'outputs', 'groups')


def _description(node: _Node) -> Description:
    """accelerator.json, checked on its own (the slot's checks: _check_slot)."""
    for key in OLD_DATAPATH_KEYS:
        if key in node.value:
            raise CfgTypeError(node.file, node.where(key), 'a key of the datapath block, which '
                'accelerator.json replaced: regenerate the design point')
    for key in FLAT_KEYS:
        if key in node.value:
            raise CfgTypeError(node.file, node.where(key), 'a top-level key of accelerator.json '
                'before streamer sets, whose accelerators now hold it: '
                'regenerate the design point')
    nodes = node.nodes('accelerators')
    desc = Description(
        design_point=node.get('design_point', str),
        tag=node.get('tag', str),
        accelerators=[_accelerator(a) for a in nodes],
    )
    if not desc.accelerators:
        raise CfgTypeError(node.file, node.where('accelerators'), 'no accelerator')

    # The offsets in CSR order over every accelerator, contiguous from 0: read, never computed
    for i, csr in enumerate(desc.csrs):
        if csr.offset != i:
            group = next((f'group {g.name}' for g in desc.groups
                          if any(c is csr for c in g.window)), 'the port mux')
            raise CfgSlotError(node.file, node.where('accelerators'),
                f'{group}\'s {csr.name} has offset {csr.offset}, but is CSR {i} in CSR '
                'order (accelerator by accelerator, per group START, JOBS, the units\' R/W CSRs, '
                'STATUS, BUSY_COUNTER, then a shared set\'s PORT_MUX_SEL): the offsets must be '
                'contiguous from 0')

    # Names: an accelerator's, a group's (its components') and a unit's are the file's once
    for what, names in (('accelerator', [a.name for a in desc.accelerators]),
                        ('group', [g.name for g in desc.groups])):
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise CfgSlotError(node.file, node.where('accelerators'),
                f'{what} {twice[0]!r} twice: names are the file\'s once')
    units = {}
    for g in desc.groups:
        for u in g.units:
            if u.name in units:
                raise CfgSlotError(node.file, node.where('accelerators'), f'unit {u.name!r} twice')
            units[u.name] = u

    # Per accelerator, its outer ports: each names a port of one of its units, once
    for acc, at in zip(desc.accelerators, nodes):
        own = {u.name: u for g in acc.groups for u in g.units}
        seen = set()
        for key in ('inputs', 'outputs'):
            for i, item in enumerate(getattr(acc, key)):
                for entry in [item] if isinstance(item, str) else item:
                    unit, _, port = entry.partition('.')
                    if unit not in own or port not in own[unit].ports:
                        raise CfgSlotError(node.file, f'{at.where(key)}[{i}]',
                            f'{entry!r} names no port of accelerator {acc.name}\'s units '
                            f'({", ".join(own)})')
                    if entry in seen:
                        raise CfgSlotError(node.file, f'{at.where(key)}[{i}]', f'{entry!r} twice')
                    seen.add(entry)
        _check_links(at, acc)
        for u in own.values():
            _check_shape(at, acc, u)
        if acc.port_mux is not None:
            _check_shared(at, acc)
    return desc


def dirs_of(unit: Unit) -> dict:
    """Each BRM port of unit's: its dir."""
    return {name: port.dir for name, port in unit.ports.items()}


def _check_links(node: _Node, acc: Accelerator):
    """The links, the outer ports and each group's connectedness, with snax-forge's codes
    (its gen/accelerator.py's reader); then the chain SnaxGroup models."""
    def fail(key, why):
        raise CfgSlotError(node.file, node.where(key), why)

    linked = set()
    outer = {'in': [], 'out': []}
    for f in acc.forks:
        if len(f) < 2 or len(set(f)) != len(f):
            fail('inputs', f'gen.fork: accelerator {acc.name}: the fork {f}: a fork gives one '
                 'reader to two or more outer input ports of its units')
    for g in acc.groups:
        ports = {f'{u.name}.{k}': (p, dirs_of(u)[k]) for u in g.units
                 for k, p in u.ports.items()}
        parent = {u.name: u.name for u in g.units}

        def root(name):
            while parent[name] != name:
                name = parent[name]
            return name

        for k in g.links:
            what = f'gen.link: group {g.name}\'s link {k.name}'
            a, b = ports.get(k.from_), ports.get(k.to)
            if a is None or b is None or a[1] != 'out' or b[1] != 'in':
                fail('groups', f'{what} goes from {k.from_} to {k.to}; a link goes from an out '
                     'port to an in port of the group\'s units')
            # NB (D197): a held link's beat is one lane, kept a bank row and broadcast
            lanes = 1 if b[0].broadcast and b[0].hold else b[0].lanes
            if (a[0].dtype, a[0].lanes) != (b[0].dtype, lanes):
                fail('groups', f'{what}: {k.from_} is {a[0].lanes} lanes of {a[0].dtype}, '
                     f'{k.to} {lanes} of {b[0].dtype}; both ends are the same')
            for end, p in ((k.from_, a[0]), (k.to, b[0])):
                if p.d_in > 1 or p.d_out > 1:
                    fail('groups', f'{what}: {end} has d_in {p.d_in} and d_out {p.d_out}; a '
                         'linked port has no slicer or packer, so both are 1 (absent)')
                if p.broadcast and not p.hold:
                    fail('groups', f'{what}: {end} is a broadcast; a linked port takes its '
                         'lanes from the link, so it is not one unless held for a bank row '
                         '(absent)')
            if b[0].hold and k.depth < 1:
                fail('groups', f'{what}: depth {k.depth} into {k.to}, held for a bank row; a '
                     'held link is a buffer, depth 1 or more')
            for end in (k.from_, k.to):
                if end in linked:
                    fail('groups', f'gen.link_port: group {g.name}\'s link {k.name}: port {end} '
                         'is on another link too')
                linked.add(end)
            parent[root(k.from_.split('.')[0])] = root(k.to.split('.')[0])
        for k in g.fork_links:
            what = f'gen.link: group {g.name}\'s fork link {k.name}'
            if not any(k.to in f[1:] for f in acc.forks) or k.to not in ports:
                fail('groups', f"{what} goes to {k.to}; a fork's buffered branch goes to a "
                     "forked port of the group, not its reader's first")
            if k.to in linked:
                fail('groups', f'gen.link_port: group {g.name}\'s fork link {k.name}: port '
                     f'{k.to} is on another link too')
        for f in acc.forks:
            mine = [x.split('.')[0] for x in f if x.split('.')[0] in parent]
            for u in mine[1:]:
                parent[root(u)] = root(mine[0])
        if len({root(u.name) for u in g.units}) > 1:
            fail('groups', f'gen.group: group {g.name}\'s units {[u.name for u in g.units]} are '
                 'not connected by its links')
        for name, (_, direction) in ports.items():
            if name not in linked:
                outer[direction].append(name)
    want_in = list(outer['in'])
    for f in acc.forks:
        _check_fork(node, acc, f, outer['in'])
        want_in = [list(f) if x == f[0] else x for x in want_in if x not in f[1:]]
    for key, want in (('inputs', want_in), ('outputs', outer['out'])):
        if list(getattr(acc, key)) != want:
            fail(key, f'gen.outer: {list(getattr(acc, key))}; the unlinked ports are '
                 f'{want}, in group, unit and port order')

    # SnaxGroup's shape, with snax-forge's codes and wording (its gen/accelerator.py's
    # _check_chain): gen.chain, a chain in unit order whose last unit's output alone is outer,
    # or with a fork the chains it joins, each forward in unit order with its sink's
    # output outer; gen.span, a unit of span > 1 reads from a link
    for g in acc.groups:
        names = [u.name for u in g.units]
        hops = [(k.from_.split('.')[0], k.to.split('.')[0]) for k in g.links]
        outs = {u.name: [f'{u.name}.{p}' for p, d in dirs_of(u).items() if d == 'out']
                for u in g.units}
        forked = [{x.split('.')[0] for x in f} & set(names) for f in acc.forks]
        if not any(len(f) > 1 for f in forked):
            chain = sorted(hops) == sorted(zip(names, names[1:]))
            for k, u in enumerate(g.units):
                outer_out = [p for p in outs[u.name] if p not in linked]
                chain = chain and bool(outer_out) == (k == len(g.units) - 1)
        else:
            at = {u: k for k, u in enumerate(names)}
            froms, tos = [a for a, _ in hops], [b for _, b in hops]
            chain = (len(set(froms)) == len(froms) and len(set(tos)) == len(tos)
                     and all(at[a] < at[b] for a, b in hops))
            for u in names:
                outer_out = [p for p in outs[u] if p not in linked]
                chain = chain and bool(outer_out) == (u not in froms)
        if not chain:
            raise CfgTargetError(node.file, node.where('groups'),
                f"gen.chain: accelerator {acc.name}: group {g.name}'s links {hops} over its "
                f'units {names}: a group is a chain, or chains a fork joins (fork_read)')
        want = jobs_names([c[-1] for c in g.chains()])
        if g.jobs != want:
            raise CfgSlotError(node.file, node.where('groups'),
                f"group {g.name}'s JOBS CSRs {g.jobs}: its chains {g.chains()} take {want}, "
                'one per chain in the order of their sinks')
        for u in g.units:
            if u.seeded and f'{u.name}.{SEED}' in linked:
                raise CfgTargetError(node.file, node.where('groups'),
                    f'gen.seed: accelerator {acc.name}: unit {u.name}\'s seed is on a link; '
                    'it is read from the streamer')
            outer_in = [p for p, d in dirs_of(u).items()
                        if d == 'in' and f'{u.name}.{p}' not in linked and p != SEED]
            if u.span > 1 and outer_in:
                raise CfgTargetError(node.file, node.where('inputs'),
                    f'gen.span: accelerator {acc.name}: unit {u.name} (span {u.span}) reads '
                    f'{outer_in} from the streamer: a unit with span > 1 reads from a link')


def _check_fork(node: _Node, acc: Accelerator, f: list, outer: list):
    """gen.fork, snax-forge's in its wording: a forked input's ports, two or more outer
    inputs of one group's chain heads (or a port down a chain behind a buffer, a fork link),
    alike in dtype, lanes, slicing and broadcast."""
    def fail(why):
        raise CfgSlotError(node.file, node.where('inputs'), f'gen.fork: {what}: {why}')

    what = f'accelerator {acc.name}: the fork {f}'
    group_of = {u.name: g for g in acc.groups for u in g.units}
    port = {f'{u.name}.{k}': p for g in acc.groups for u in g.units for k, p in u.ports.items()}
    if len(f) < 2 or len(set(f)) != len(f) or any(x not in outer for x in f):
        fail(f'a fork gives one reader to two or more outer input ports of its units ({outer})')
    if len({group_of[x.split('.')[0]].name for x in f}) > 1:
        fail('its ports are in several groups; a fork feeds the chains of one group')
    fed = {k.to.split('.')[0] for g in acc.groups for k in g.links}
    buffered = {k.to for g in acc.groups for k in g.fork_links}
    for x in f:
        if x.split('.')[0] in fed and x not in buffered:
            fail(f"{x}'s unit is fed by a link; a fork feeds the heads of chains")
    kinds = {(port[x].dtype, port[x].lanes, port[x].d_in, port[x].broadcast) for x in f}
    if len(kinds) > 1:
        fail("its ports differ in dtype, lanes, d_in or broadcast; one reader's beat is the "
             'same for all')
    if any(port[x].hold for x in f):
        fail('a port is held for a bank row; a held input is read by its own reader')


def _check_shape(node: _Node, acc: Accelerator, u: Unit):
    """A unit's ports against its datapath: their number, lanes and types."""
    dirs = dirs_of(u)
    ins = [u.ports[p] for p in u.ports if dirs[p] == 'in' and p != SEED]  # the seed: _unit
    outs = [u.ports[p] for p in u.ports if dirs[p] == 'out']
    facts = CATALOGUE[u.datapath]
    n_in = facts.nb_inputs(u.slot_params)
    plain = u.datapath == 'Mac' and n_in == 3
    if (len(ins), len(outs)) != (n_in, 1):
        raise CfgTargetError(node.file, node.where('inputs'),
            f'unit {u.name}: {len(ins)} inputs and {len(outs)} outputs; {u.datapath} takes '
            f'{n_in} and 1')
    if facts.reduces:
        if outs[0].lanes != 1:
            raise CfgTargetError(node.file, node.where('outputs'),
                f'unit {u.name}: a fold\'s output has 1 lane, not {outs[0].lanes}')
        return
    if len({p.lanes for p in (*ins, *outs)}) != 1:
        raise CfgTargetError(node.file, node.where('inputs'),
            f'unit {u.name}: lanes {[p.lanes for p in (*ins, *outs)]}; {u.datapath} has one lane '
            'count on every port')
    if plain and (ins[2].dtype != outs[0].dtype):
        raise CfgTargetError(node.file, node.where('inputs'),
            f'unit {u.name}: c is {ins[2].dtype}, out {outs[0].dtype}; a plain Mac\'s c is '
            'out\'s type')
    if not facts.typed:  # no opType (LaneAccumulate: its input extended to out's type)
        if u.op_type is not None:
            raise CfgTypeError(node.file, node.where('groups'),
                f'unit {u.name}: opType {u.op_type}; a {u.datapath} unit has none')
        return
    if n_in == 1:  # one stream: a cast to opType, then the op with k
        a = (ins[0].width, ins[0].signed)
        # NB (D175): a k from its CSR has opType's width, so the op may be wider than a
        if result_type(DTYPES[u.op_type], a) != DTYPES[u.op_type]:
            raise CfgSlotError(node.file, node.where('groups'),
                f'unit {u.name}: opType {u.op_type} does not hold its one input\'s type '
                f'{type_name(*a)}')
        return
    # a plain Mac's c is out's type; SimdLanes' axpbypcz runs at its three inputs' result type
    ops = [(p.width, p.signed) for p in (ins if u.datapath == 'SimdLanes' else ins[:2])]
    t = ops[0]
    for x in ops[1:]:
        t = None if t is None else result_type(t, x)
    if t is None:
        raise CfgTypeError(node.file, node.where('groups'),
            f'unit {u.name}: {" with ".join(type_name(*x) for x in ops)} has no integer result '
            'type (NumPy gives float64)')
    # NB (D175): the kernel's casts may set the op wider than the inputs' result type
    if result_type(DTYPES[u.op_type], t) != DTYPES[u.op_type]:
        raise CfgSlotError(node.file, node.where('groups'),
            f'unit {u.name}: opType {u.op_type} does not hold its inputs\' result type '
            f'{type_name(*t)} (snax_op_result_type)')


def _sets(acc: _Node) -> list:
    """The slot's streamer sets (StreamerSet), as snax_cluster's snaxgen reads them: its
    snax_streamer_sets, or its snax_streamer_cfg as one set named after the slot with the
    slot's CSR counts, or none."""
    streamer = acc.get('snax_streamer_cfg', dict, None)
    nodes = acc.nodes('snax_streamer_sets', None)
    if nodes is None:
        name = acc.get('snax_acc_name', str)
        rw, ro = acc.get('snax_num_rw_csr', int), acc.get('snax_num_ro_csr', int)
        return [] if streamer is None else [StreamerSet(name, streamer, rw, ro)]
    if streamer is not None:
        raise CfgSlotError(acc.file, acc.where('snax_streamer_sets'),
            'the slot has both snax_streamer_cfg and snax_streamer_sets; give one')
    if not nodes:
        raise CfgSlotError(acc.file, acc.where('snax_streamer_sets'), 'no set')
    if not acc.get('snax_disable_csr_manager', bool, False):
        raise CfgSlotError(acc.file, acc.where('snax_streamer_sets'), 'streamer sets need the '
            "shell's own CSRs: snax_disable_csr_manager must be true (snax_cluster's schema)")
    sets = []
    for k, node in enumerate(nodes):
        name = node.get('name', str)
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise CfgTypeError(acc.file, node.where('name'),
                f'{name!r}, not a C identifier (it prefixes the set\'s header macros)')
        if any(s.name == name for s in sets):
            raise CfgSlotError(acc.file, node.where('name'), f'set {name!r} twice')
        rw, ro = node.get('snax_num_rw_csr', int), node.get('snax_num_ro_csr', int)
        for key, n in (('snax_num_rw_csr', rw), ('snax_num_ro_csr', ro)):
            if n < 0:
                raise CfgTypeError(acc.file, node.where(key), f'{n}, must be 0 or more')
        sets.append(StreamerSet(name, node.get('snax_streamer_cfg', dict), rw, ro,
                                f'snax_streamer_sets[{k}]'))
    return sets


def _slot(acc: _Node) -> AccSlot:
    ports = acc.get('snax_tcdm_ports', int)
    sparse = acc.get('sparse_interconnect_config', list, None)
    if sparse is not None:
        for i, entry in enumerate(sparse):
            if not (isinstance(entry, list) and len(entry) == 2
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in entry)):
                raise CfgTypeError(acc.file, f'{acc.where("sparse_interconnect_config")}[{i}]',
                    f'must be [width, granularity], got {entry!r}')
    description = acc.node('snax_datapath_cfg', None)
    slot = AccSlot(
        name=acc.get('snax_acc_name', str),
        tcdm_ports=ports,
        narrow_tcdm_ports=acc.get('snax_narrow_tcdm_ports', int, None),
        wide_tcdm_ports=acc.get('snax_wide_tcdm_ports', int, None),
        sparse_config=sparse,
        sets=_sets(acc),
        description=None if description is None else _description(description),
        at=acc.at,
    )
    _check_slot(acc, slot)
    return slot


def _check_slot(acc: _Node, slot: AccSlot):
    """The slot's counts against its streamers, ports and datapath."""
    def fail(key, why):
        raise CfgSlotError(acc.file, acc.where(key), why)

    for s in slot.sets:
        for mover in UNMODELLED_MOVERS:
            if mover in s.streamer:
                raise CfgTargetError(acc.file, acc.where(s.key(f'snax_streamer_cfg.{mover}')),
                    f'not modelled: the streamer has {", ".join(MOVERS)}')
        for mover in MOVERS:
            params = s.streamer.get(mover, {})
            for i, (bounds, channels) in enumerate(zip(params.get('spatial_bounds', []),
                                                       params.get('num_channel', []))):
                why = spatial_mismatch(bounds, channels)
                if why is not None:
                    fail(s.key(f'snax_streamer_cfg.{mover}.spatial_bounds[{i}]'), why)
    if slot.sets:
        channels = [streamer_channels(s.streamer) for s in slot.sets]
        if sum(channels) != slot.tcdm_ports:
            fail('snax_tcdm_ports', f'{slot.tcdm_ports}, but the streamers have {sum(channels)} '
                 'channels (num_channel over their movers' + (
                     f', set by set {dict(zip((s.name for s in slot.sets), channels))})'
                     if len(slot.sets) > 1 else ')'))
    if slot.narrow_tcdm_ports is not None or slot.wide_tcdm_ports is not None:
        narrow, wide = slot.narrow_tcdm_ports or 0, slot.wide_tcdm_ports or 0
        if narrow + wide != slot.tcdm_ports:
            fail('snax_narrow_tcdm_ports', f'narrow {narrow} + wide {wide} ports, not '
                f'snax_tcdm_ports {slot.tcdm_ports}')
    if slot.sparse_config is not None:
        widths = sum(width for width, _ in slot.sparse_config)
        if widths != slot.tcdm_ports:
            fail('sparse_interconnect_config', f'widths add up to {widths}, not '
                f'snax_tcdm_ports {slot.tcdm_ports}')
    if slot.description is not None:
        _check_description(acc, slot)


def _check_description(acc: _Node, slot: AccSlot):
    """accelerator.json against the slot: one accelerator per set, in the sets' order; each
    accelerator's outer ports against its set's movers, each port's words per beat against
    its mover's num_channel (or one word, sliced or packed: the streamer would refuse the
    beat's size mid-run), and each set's CSR counts."""
    desc = slot.description

    def fail(key, why):
        raise CfgSlotError(acc.file, acc.where(key), why)

    names = [a.name for a in desc.accelerators]
    if not slot.sets:
        fail('snax_streamer_sets', 'missing: accelerator.json needs the streamers it is fed by '
             '(snax_streamer_sets, or snax_streamer_cfg for one accelerator)')
    if not slot.sets[0].at:
        if len(names) != 1:
            fail('snax_streamer_cfg', f'one streamer, but accelerator.json has the accelerators '
                 f'{names}: give snax_streamer_sets, one set per accelerator')
    elif [s.name for s in slot.sets] != names:
        fail('snax_streamer_sets', f'the sets {[s.name for s in slot.sets]}, but '
             f"accelerator.json's accelerators are {names}: one set per accelerator, named "
             'after it, in its order')
    for k, (s, accelerator) in enumerate(zip(slot.sets, desc.accelerators)):
        at = f'snax_datapath_cfg.accelerators[{k}]'
        if accelerator.port_mux is not None:
            _check_shared_set(acc, at, s, accelerator)
        else:
            for key, mover in (('inputs', 'data_reader_params'), ('outputs', 'data_writer_params')):
                # a fork's ports share their reader, the first's
                ports = accelerator.readers if key == 'inputs' else accelerator.outputs
                channels = s.streamer.get(mover, {}).get('num_channel', [])
                if len(ports) != len(channels):
                    fail(f'{at}.{key}', f'{ports}, but set {s.name}\'s streamer has '
                         f'{len(channels)} {mover}: one port each, in order')
                for i, entry in enumerate(ports):
                    why = _port_words(accelerator, entry, key == 'outputs', channels[i],
                                      f"set {s.name}'s {mover}[{i}]")
                    if why is not None:
                        fail(f'{at}.{key}[{i}]', why)
        if s.num_rw_csr != accelerator.num_rw:
            fail(s.key('snax_num_rw_csr'), f'{s.num_rw_csr}, but accelerator '
                 f'{accelerator.name} has {accelerator.num_rw} read-write CSRs')
        if s.num_ro_csr != accelerator.num_ro:
            fail(s.key('snax_num_ro_csr'), f'{s.num_ro_csr}, but accelerator '
                 f'{accelerator.name} has {accelerator.num_ro} read-only CSRs (STATUS and '
                 'BUSY_COUNTER per group)')


def _port_words(accelerator: Accelerator, entry: str, output: bool, channels: int,
                mover: str):
    """Why an outer port's words per beat are not its mover's num_channel (or its user's on a
    shared mover), or None: they must match, or with d_out or d_in one word fills or empties
    in d results on one channel."""
    unit, _, name = entry.partition('.')
    u = accelerator.unit(unit)
    port = u.ports[name]
    if port.d_out > 1:  # packed: d_out results of lanes x width bits fill one word
        bits = (1 if CATALOGUE[u.datapath].reduces else port.lanes) * port.width * port.d_out
        if bits != 64 or channels != 1:
            return (f'{entry}: d_out {port.d_out} results of {bits // port.d_out} bits are '
                    f'{bits} bits, not one 64-bit word, or {mover} has num_channel {channels}, '
                    'not 1')
        return None
    lanes = port.stream_lanes  # a broadcast's reader moves one lane
    if port.d_in > 1:  # sliced: one word gives d_in pops of lanes x width bits
        if lanes * port.width * port.d_in != 64 or channels != 1:
            return (f'{entry}: d_in {port.d_in} pops of {lanes} x {port.width} bits are '
                    f'{lanes * port.width * port.d_in} bits, not one 64-bit word, or '
                    f'{mover} has num_channel {channels}, not 1')
        return None
    if CATALOGUE[u.datapath].reduces and output:
        if channels != 1:
            return (f"{entry}: a fold's output is one 64-bit word per beat, but {mover} has "
                    f'num_channel {channels}')
        return None
    bits = lanes * port.width
    if bits % 64 != 0:
        return (f'{entry}: lanes {lanes} x {port.width} bits is not a whole number of '
                '64-bit channel words')
    if bits // 64 != channels:
        return (f'{entry}: lanes {lanes} x {port.width} bits is {bits // 64} 64-bit words '
                f'per beat, but {mover} has num_channel {channels}: they must match')
    return None


def _check_shared_set(acc: _Node, at: str, s: StreamerSet, accelerator: Accelerator):
    """A shared accelerator's movers against its set's streamer: the same
    movers in the streamer's order (readers, then writers), each of its num_channel, masked
    exactly when its template has configurable_channel; each user's words per beat its
    num_channel."""
    def fail(key, why):
        raise CfgSlotError(acc.file, acc.where(key), why)

    streamer = template_movers(s.streamer)
    names = [m['name'] for m in streamer]
    if [m.name for m in accelerator.movers] != names:
        fail(f'{at}.movers', f'{[m.name for m in accelerator.movers]}, but set {s.name}\'s '
             f'streamer has the movers {names}, in that order')
    for k, (m, t) in enumerate(zip(accelerator.movers, streamer)):
        where = f'{at}.movers[{k}]'
        if (m.role == 'read') != t['is_reader'] or m.num_channel != t['num_channel']:
            fail(where, f'{m.name}: {m.role}, {m.num_channel} channels, but set {s.name}\'s '
                 f"{t['name']} is a {'reader' if t['is_reader'] else 'writer'} of "
                 f"{t['num_channel']}")
        if m.masked != t['configurable_channel']:
            fail(where, f'{m.name}: masked {m.masked}, but its configurable_channel is '
                 f"{t['configurable_channel']}")
        for i, user in enumerate(m.users):
            why = _port_words(accelerator, user.port, m.role == 'write', user.num_channel,
                              f'its user entry on {m.name}')
            if why is not None:
                fail(f'{where}.users[{i}]', why)


def _core(core: _Node) -> Core:
    return Core(
        isa=core.get('isa', str),
        xdma=core.get('xdma', bool, False),
        num_int_outstanding_loads=core.get('num_int_outstanding_loads', int),
        accelerators=[_slot(acc) for acc in core.nodes('snax_acc_cfg', [])],
    )


def from_dict(value, path) -> ClusterCfg:
    """The configuration of a parsed cluster file at path (its $refs resolved from there)."""
    path = Path(path)
    if not isinstance(value, dict):
        raise CfgParseError(path, '', f'must be an object, got {type(value).__name__}')
    resolver = _Resolver()
    resolver.files[path.resolve()] = value
    top = _Node(path, resolver.resolve(value, path, ''), '')

    cluster = top.node('cluster')
    tcdm = cluster.node('tcdm')
    width = cluster.get('data_width', int)
    if width % 8:
        raise CfgTypeError(path, cluster.where('data_width'), f'{width} is not whole bytes')
    dram = top.node('dram')
    return ClusterCfg(
        path=path,
        name=cluster.get('name', str),
        boot_addr=cluster.get('boot_addr', int),
        base=cluster.get('cluster_base_addr', int),
        tcdm=Tcdm(
            size=tcdm.get('size', int) * 1024,
            banks=tcdm.get('banks', int),
            bank_width=width // 8,
            sparse_interconnect=tcdm.get('sparse_interconnect', bool, False),
        ),
        periph_size=cluster.get('cluster_periph_size', int) * 1024,
        zero_mem_size=cluster.get('zero_mem_size', int) * 1024,
        dma=Dma(
            data_width=cluster.get('dma_data_width', int),
            req_fifo_depth=cluster.get('dma_req_fifo_depth', int),
            axi_req_fifo_depth=cluster.get('dma_axi_req_fifo_depth', int),
        ),
        dram=Dram(address=dram.get('address', int), length=dram.get('length', int)),
        hives=[Hive([_core(core) for core in hive.nodes('cores')])
            for hive in cluster.nodes('hives')],
    )


def load(path) -> ClusterCfg:
    """The cluster hjson at path; see the module doc."""
    path = Path(path)
    return from_dict(_parse(path), path)
