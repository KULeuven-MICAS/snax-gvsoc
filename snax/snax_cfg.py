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
                              streamer's reader and writer order
      groups[]                Group: name, csrs (START, JOBS, STATUS,
                              BUSY_COUNTER), units, links
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
                              inputs, k1 * a + k2 * b; k: SimdLanes' constant at
                              one stream, its one input, an int of its opType;
                              k1, k2: axpby's baked; accumulate, regOut: Mac's;
                              T: a fold's rate fixed at design time), scalars
                              (SimdLanes' slots read from CSRs, k at one
                              stream, k1, k2, each at its opType, none baked),
                              timing (latency, ii, span: 1 when missing), csrs
                              (its R/W ones: JOB_BEATS, a fold's without T, then
                              per scalar K1, or K1_LO and K1_HI at 64 bits, its
                              pin the slot, its width the type's bits, 32 a word)
    groups[].links[]          Link: name, from (an out port, "<unit>.<port>"),
                              to (an in port), depth (0 a wire, >= 1 a buffer)
    a CSR                     Csr: name, access (rw, ro), offset (from the
                              accelerator's first CSR), width (its bits, every
                              CSR: START 1, JOBS and JOB_BEATS job_width, STATUS
                              2, BUSY_COUNTER busy_counter_width), pin

Per group the CSRs in CSR order are START, JOBS, its units' R/W CSRs, STATUS,
BUSY_COUNTER, and the offsets over all groups of all accelerators in that order
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
order (gen.outer), each link goes from an out port to an in port of its
group's units with the same dtype and lanes (gen.link), no port is on two
links (gen.link_port) and a group's links connect its units (gen.group), the
codes snax-forge's reader gives; each outer port's words per beat (lanes *
its dtype's bits / 64) are its mover's num_channel (a fold's one-lane output:
1), since SnaxGroup has no FIFO slicer; each set's snax_num_rw_csr and
snax_num_ro_csr are its accelerator's R/W and R/O CSRs. A SimdLanes unit's
opType is its inputs' NumPy result type (snax_types.hpp's
snax_op_result_type: a signed type with uint64 has none), a Mac's that of a
and b.

Everything wrong is a SnaxCfgError naming the file and the key's path:
CfgParseError (not an hjson object), CfgRefError (a $ref that does not
resolve), CfgKeyError (a key missing), CfgTypeError (a value of the wrong
type), CfgSlotError (slot counts, sets or CSRs that disagree with the files,
or both snax_streamer_cfg and snax_streamer_sets); a
target refuses what it cannot model with CfgTargetError (a datapath not in
the registry, a TreeAccumulate op other than add, a unit CSR other than a
fold's JOB_BEATS, a latency or span other than its datapath's, and SnaxGroup's
shape with snax-forge's codes and wording: gen.chain, a group whose links are
not a chain in unit order with the last unit's output the only outer one;
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


def _accumulates(params: dict) -> bool:
    return bool(params.get('accumulate', True))


# The unit datapaths SnaxGroup models, one entry each: snax_datapath.hpp's registry but
# LinkBuffer, a link's. A new datapath is an entry here and one in the registry.
CATALOGUE = {
    'SimdLanes': Datapath(nb_inputs=lambda p: 1 if 'k' in p else 2, is_fold=lambda p: False,
                          latency=lambda p: 0, typed=True, needs_op=True),
    'TreeAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                               latency=lambda p: 1, reduces=True, needs_op=True, only_op='add',
                               seedable=True),
    'Mac': Datapath(nb_inputs=lambda p: 2 if _accumulates(p) else 3, is_fold=_accumulates,
                    latency=lambda p: int(_accumulates(p) or bool(p.get('regOut', False))),
                    typed=True),
    'SerialAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                                 latency=lambda p: 1, serial=True, reduces=True, seedable=True),
    'LaneAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                               latency=lambda p: 1),
}
# A fold's seed port (snax-forge's brm.SEED): one element, read once per job
SEED = 'seed'
# A group's own CSRs: START and JOBS, read-write, first; STATUS and BUSY_COUNTER,
# read-only, last
GROUP_RW = ('START', 'JOBS')
GROUP_RO = ('STATUS', 'BUSY_COUNTER')
# The unit CSRs modelled: a fold's JOB_BEATS, then its scalars' (scalar_csrs)
UNIT_RW = ('JOB_BEATS',)
# The op names (snax_types.hpp's snax_op_names), and SimdLanes' axpby
OPS = ('add', 'sub', 'mul', 'and', 'or', 'xor', 'min', 'max')
AXPBY = 'axpby'
# SimdLanes' slots: k at one stream, axpby's k1 and k2
SLOTS = ('k', 'k1', 'k2')


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
    """A unit's BRM port: the datapath's port, its dtype (NumPy's name), its lanes and its
    direction (in or out)."""

    port: str
    dtype: str
    lanes: int
    dir: str

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
class Group:
    """A group: its own CSRs (START, JOBS, STATUS, BUSY_COUNTER), its units and links."""

    name: str
    csrs: list
    units: list
    links: list

    @property
    def window(self) -> list:
        """Its CSRs in CSR order: START, JOBS, its units' R/W CSRs, STATUS, BUSY_COUNTER."""
        own = {c.name: c for c in self.csrs}
        return ([own[n] for n in GROUP_RW] + [c for u in self.units for c in u.csrs]
                + [own[n] for n in GROUP_RO])

    @property
    def rw(self) -> list:
        """Its read-write CSRs' names in CSR order: START, JOBS, the units'."""
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
    inputs: list
    outputs: list
    groups: list
    movers: list = field(default_factory=list)
    port_mux: PortMux = None

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
        """The (index, BRM port) of each of outer's entries ("<unit>.<port>") that name unit."""
        return [(i, entry.split('.', 1)[1]) for i, entry in enumerate(outer)
                if entry.split('.', 1)[0] == unit]


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
    return Port(port=node.get('port', str), dtype=dtype, lanes=lanes, dir=direction)


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
    if op is not None and op not in OPS and not (op == AXPBY and datapath == 'SimdLanes'):
        raise CfgTypeError(node.file, params.where('op'), f'{op!r}, not an op ({", ".join(OPS)}; '
                           f'SimdLanes\' {AXPBY})')
    if facts.only_op is not None and op != facts.only_op:
        raise CfgTargetError(node.file, params.where('op'),
            f'{op!r}: {datapath} {facts.only_op}s; a fold of another op is not modelled')
    for key in ('accumulate', 'regOut'):
        params.get(key, bool, None)
    k = params.get('k', int, None)
    if k is not None and datapath != 'SimdLanes':
        raise CfgTypeError(node.file, params.where('k'), f'a {datapath} unit has no constant k')
    baked = {s: params.get(s, int, None) for s in SLOTS}
    scalars = node.get('scalars', dict, {})
    for s, dtype in scalars.items():
        if datapath != 'SimdLanes' or s not in SLOTS or baked[s] is not None:
            raise CfgTypeError(node.file, f'{node.where("scalars")}.{s}',
                f'not a slot of SimdLanes ({", ".join(SLOTS)}) that is not baked')
    for s in ('k1', 'k2'):
        if (baked[s] is not None or s in scalars) and op != AXPBY:
            raise CfgTypeError(node.file, params.where(s), f'{s} is {AXPBY}\'s, not {op}\'s')
    if op == AXPBY and baked['k1'] is None and 'k1' not in scalars:
        raise CfgKeyError(node.file, params.where('k1'),
            f'missing: {AXPBY} takes k1, baked in params or read from its CSR (scalars)')
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
    lanes = next(iter(unit_ports.values())).lanes
    if SEED in unit_ports:
        seed = unit_ports[SEED]
        outs = [x for x in unit_ports.values() if x.dir == 'out']
        why = (f'{datapath} takes no seed (TreeAccumulate and SerialAccumulate do)'
               if not facts.seedable else 'an in port' if seed.dir != 'in'
               else f'{seed.lanes} lanes, a seed is 1' if seed.lanes != 1
               else f'{seed.dtype}, a seed is its output\'s {outs[0].dtype}'
               if outs and seed.dtype != outs[0].dtype
               else f'the last in port, after {list(unit_ports)}' if
               [k for k, x in unit_ports.items() if x.dir == 'in'][-1] != SEED else None)
        if why is not None:
            raise CfgTargetError(node.file, f'{node.where("ports")}.{SEED}', f'gen.seed: {why}')
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


def _group(node: _Node) -> Group:
    links = [_link(k) for k in node.nodes('links')]
    units = [_unit(u) for u in node.nodes('units')]
    if not units:
        raise CfgTypeError(node.file, node.where('units'), 'no unit')
    csrs = [_csr(c) for c in node.nodes('csrs')]
    own = [(c.name, c.access) for c in csrs]
    want = [(n, 'rw') for n in GROUP_RW] + [(n, 'ro') for n in GROUP_RO]
    if own != want:
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: a group\'s own CSRs are START, JOBS (rw), STATUS, '
            'BUSY_COUNTER (ro), in that order')
    return Group(name=node.get('name', str), csrs=csrs, units=units, links=links)


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
        inputs=_names(node, 'inputs'),
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
    for entry in [*acc.inputs, *acc.outputs]:
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
            for i, entry in enumerate(getattr(acc, key)):
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
            if (a[0].dtype, a[0].lanes) != (b[0].dtype, b[0].lanes):
                fail('groups', f'{what}: {k.from_} is {a[0].lanes} lanes of {a[0].dtype}, '
                     f'{k.to} {b[0].lanes} of {b[0].dtype}; both ends are the same')
            for end in (k.from_, k.to):
                if end in linked:
                    fail('groups', f'gen.link_port: group {g.name}\'s link {k.name}: port {end} '
                         'is on another link too')
                linked.add(end)
            parent[root(k.from_.split('.')[0])] = root(k.to.split('.')[0])
        if len({root(u.name) for u in g.units}) > 1:
            fail('groups', f'gen.group: group {g.name}\'s units {[u.name for u in g.units]} are '
                 'not connected by its links')
        for name, (_, direction) in ports.items():
            if name not in linked:
                outer[direction].append(name)
    for key, direction in (('inputs', 'in'), ('outputs', 'out')):
        if list(getattr(acc, key)) != outer[direction]:
            fail(key, f'gen.outer: {list(getattr(acc, key))}; the unlinked ports are '
                 f'{outer[direction]}, in group, unit and port order')

    # SnaxGroup's shape, with snax-forge's codes and wording (its gen/accelerator.py's
    # _check_chain): gen.chain, a chain in unit order whose last unit's output alone is outer;
    # gen.span, a unit of span > 1 reads from a link
    for g in acc.groups:
        names = [u.name for u in g.units]
        hops = [(k.from_.split('.')[0], k.to.split('.')[0]) for k in g.links]
        chain = sorted(hops) == sorted(zip(names, names[1:]))
        for k, u in enumerate(g.units):
            outer_out = [p for p, d in dirs_of(u).items()
                         if d == 'out' and f'{u.name}.{p}' not in linked]
            chain = chain and bool(outer_out) == (k == len(g.units) - 1)
        if not chain:
            raise CfgTargetError(node.file, node.where('groups'),
                f"gen.chain: accelerator {acc.name}: group {g.name}'s links {hops} over its "
                f'units {names}: a group is one chain (no fork or join)')
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


def _check_shape(node: _Node, acc: Accelerator, u: Unit):
    """A unit's ports against its datapath: their number, lanes and types."""
    dirs = dirs_of(u)
    ins = [u.ports[p] for p in u.ports if dirs[p] == 'in' and p != SEED]  # the seed: _unit
    outs = [u.ports[p] for p in u.ports if dirs[p] == 'out']
    facts = CATALOGUE[u.datapath]
    plain = facts.nb_inputs(u.slot_params) == 3
    n_in = facts.nb_inputs(u.slot_params)
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
    if n_in == 1:  # one stream: the op at a's type, with the constant k
        a = (ins[0].width, ins[0].signed)
        if u.op_type != type_name(*a):
            raise CfgSlotError(node.file, node.where('groups'),
                f'unit {u.name}: opType {u.op_type}, but its one input is {type_name(*a)} (the op '
                'runs at it with k)')
        return
    a, b = ((p.width, p.signed) for p in ins[:2])
    t = result_type(a, b)
    if t is None:
        raise CfgTypeError(node.file, node.where('groups'),
            f'unit {u.name}: {type_name(*a)} with {type_name(*b)} has no integer result type '
            '(NumPy gives float64)')
    if u.op_type != type_name(*t):
        raise CfgSlotError(node.file, node.where('groups'),
            f'unit {u.name}: opType {u.op_type}, but its inputs\' result type is '
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
    its mover's num_channel (SnaxGroup has no FIFO slicer, so they must match: the streamer
    would refuse the beat's size mid-run), and each set's CSR counts."""
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
                ports = getattr(accelerator, key)
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
    shared mover), or None: SnaxGroup has no FIFO slicer, so they must match."""
    unit, _, name = entry.partition('.')
    u = accelerator.unit(unit)
    port = u.ports[name]
    if CATALOGUE[u.datapath].reduces and output:
        if channels != 1:
            return (f"{entry}: a fold's output is one 64-bit word per beat, but {mover} has "
                    f'num_channel {channels}')
        return None
    bits = port.lanes * port.width
    if bits % 64 != 0:
        return (f'{entry}: lanes {port.lanes} x {port.width} bits is not a whole number of '
                '64-bit channel words')
    if bits // 64 != channels:
        return (f'{entry}: lanes {port.lanes} x {port.width} bits is {bits // 64} 64-bit words '
                f'per beat, but {mover} has num_channel {channels}: SnaxGroup has no FIFO '
                'slicer, so they must match')
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
