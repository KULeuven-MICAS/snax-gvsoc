#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_cluster's cluster hjson, read for a SNAX-GVSoC target.

    load(path) -> ClusterCfg

The hjson is the contract: snax_cluster's clustergen and snaxgen read the
same file. A design is three files: the cluster file, named after its base
platform (snax_forge.hjson), the streamer file, named after its slot
(snax_forge_streamer.hjson, the streamer template), and accelerator.json,
the accelerator's one description (snax-forge C§17, D145). The cluster's
snax_acc_cfg entry (the slot) keeps the slot keys; its snax_streamer_cfg and
snax_datapath_cfg are $refs to the other two, each the whole file.

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

A slot (AccSlot): snax_acc_name, snax_tcdm_ports, snax_narrow_tcdm_ports and
snax_wide_tcdm_ports or sparse_interconnect_config, snax_num_rw_csr,
snax_num_ro_csr, snax_streamer_cfg (the streamer template, as the hjson has
it) and snax_datapath_cfg (accelerator.json, optional; Accelerator).

accelerator.json (snax-forge C§17), what the standard composite
(snax_unit_acc.py) builds the slot's shells and units from:

    name, design_point, tag   Accelerator.name (the header's <ACC>), ...
    inputs, outputs           the outer ports, "<unit>.<port>", in the
                              streamer's reader and writer order
    groups[]                  Group: name, csrs (START, JOBS, STATUS,
                              COUNTER), units, links
    groups[].units[]          Unit: name, brm, datapath (a unit datapath of
                              snax_datapath.hpp's registry: ElementwiseLanes,
                              TreeAccumulate, Mac, SerialAccumulate), ports
                              (per BRM port: port, the datapath's; dir, in or
                              out; dtype, NumPy's name; lanes), opType (ElementwiseLanes and Mac),
                              params (op: ElementwiseLanes' and
                              TreeAccumulate's, add; accumulate, regOut: Mac's;
                              T: a fold's rate fixed at design time), timing
                              (latency, ii, span: 1 when missing), csrs (its
                              R/W ones: JOB_BEATS, a fold's without T)
    groups[].links[]          Link: name, from (an out port, "<unit>.<port>"),
                              to (an in port), depth (0 a wire, >= 1 a buffer)
    a CSR                     Csr: name, access (rw, ro), offset (from the
                              accelerator's first CSR), width (rw only), pin

Per group the CSRs in CSR order are START, JOBS, its units' R/W CSRs, STATUS,
COUNTER, and the offsets over all groups in that order are contiguous from 0:
they are read, never computed (a group's window starts at its START).

The slot's counts must agree with what its refs give: each mover's
spatial_bounds multiply to its num_channel (snax_cluster's StreamerParam);
snax_tcdm_ports is the streamer's num_channel summed over its movers, and the
narrow and wide ports or the sparse config's widths add up to it; with
accelerator.json, inputs and outputs are the streamer's readers and writers
in number; they are exactly the ports on no link, group by group, unit by
unit in port order (gen.outer), each link goes from an out port to an in port
of its group's units with the same dtype and lanes (gen.link), no port is on
two links (gen.link_port) and a group's links connect its units (gen.group),
the codes snax-forge's reader gives; each outer port's words per beat
(lanes * its dtype's bits / 64) are its mover's num_channel (a fold's
one-lane output: 1), since SnaxGroup has no FIFO slicer; snax_num_rw_csr and
snax_num_ro_csr are the file's R/W and R/O CSRs. An ElementwiseLanes unit's
opType is its inputs' NumPy result type (snax_types.hpp's
snax_unit_result_type: a signed type with uint64 has none), a Mac's that of a
and b.

Everything wrong is a SnaxCfgError naming the file and the key's path:
CfgParseError (not an hjson object), CfgRefError (a $ref that does not
resolve), CfgKeyError (a key missing), CfgTypeError (a value of the wrong
type), CfgSlotError (slot counts or CSRs that disagree with the files); a
target refuses what it cannot model with CfgTargetError (a datapath not in
the registry, a TreeAccumulate op other than add, a unit CSR other than a
fold's JOB_BEATS, a latency or span other than its datapath's, and SnaxGroup's
shape with snax-forge's codes and wording: gen.chain, a group whose links are
not a chain in unit order with the last unit's output the only outer one;
gen.span, a unit of span > 1 fed by the streamer). The datapath block before accelerator.json
(<slot>_acc.hjson: unit, control, config, wait, fields) is refused at its key.
"""

import math
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
    """A unit datapath's facts (snax-forge's catalogue, D147, D149), each from its params
    (accelerator.json's unit params: accumulate, regOut) where it depends on them."""

    nb_inputs: object           # params -> its input ports
    is_fold: object             # params -> a result every T firings (a JOB_BEATS CSR or params.T)
    latency: object             # params -> its latency
    serial: bool = False        # span = lanes (it reads a beat's lanes one a cycle), else 1
    reduces: bool = False       # its output is one lane, one 64-bit word (the lanes summed)
    typed: bool = False         # it runs its op at an opType, its inputs' result type
    needs_op: bool = False      # params.op is given
    only_op: str = None         # the one op it computes


def _accumulates(params: dict) -> bool:
    return bool(params.get('accumulate', True))


# The unit datapaths SnaxGroup models, one entry each: snax_datapath.hpp's registry but
# LinkBuffer, a link's. A new datapath is an entry here and one in the registry.
CATALOGUE = {
    'ElementwiseLanes': Datapath(nb_inputs=lambda p: 2, is_fold=lambda p: False,
                                 latency=lambda p: 0, typed=True, needs_op=True),
    'TreeAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                               latency=lambda p: 1, reduces=True, needs_op=True, only_op='add'),
    'Mac': Datapath(nb_inputs=lambda p: 2 if _accumulates(p) else 3, is_fold=_accumulates,
                    latency=lambda p: int(_accumulates(p) or bool(p.get('regOut', False))),
                    typed=True),
    'SerialAccumulate': Datapath(nb_inputs=lambda p: 1, is_fold=lambda p: True,
                                 latency=lambda p: 1, serial=True, reduces=True),
}
# A group's own CSRs: START and JOBS, read-write, first; STATUS and COUNTER,
# read-only, last (C§17)
GROUP_RW = ('START', 'JOBS')
GROUP_RO = ('STATUS', 'COUNTER')
# The unit CSRs modelled: a fold's JOB_BEATS
UNIT_RW = ('JOB_BEATS',)
# The op names (snax_types.hpp's snax_unit_op_names)
OPS = ('add', 'sub', 'mul', 'and', 'or', 'xor', 'min', 'max')
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
    (rw only) and a scalar's datapath pin (None)."""

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
    type (ElementwiseLanes; None for a fold), params, timing and its R/W CSRs."""

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

    @property
    def op(self) -> str:
        """The op its lanes compute: params.op (a fold's add)."""
        return self.params['op']


@dataclass(frozen=True)
class Link:
    """A link of a group (C§17): from an out port to an in port, each "<unit>.<port>"; depth
    0 a wire, >= 1 a buffer of that many beats."""

    name: str
    from_: str
    to: str
    depth: int


@dataclass(frozen=True)
class Group:
    """A group: its own CSRs (START, JOBS, STATUS, COUNTER), its units and links."""

    name: str
    csrs: list
    units: list
    links: list

    @property
    def window(self) -> list:
        """Its CSRs in CSR order: START, JOBS, its units' R/W CSRs, STATUS, COUNTER."""
        own = {c.name: c for c in self.csrs}
        return ([own[n] for n in GROUP_RW] + [c for u in self.units for c in u.csrs]
                + [own[n] for n in GROUP_RO])

    @property
    def rw(self) -> list:
        """Its read-write CSRs' names in CSR order: START, JOBS, the units'."""
        return [c.name for c in self.window if c.access == 'rw']


@dataclass(frozen=True)
class Accelerator:
    """accelerator.json; see the module doc."""

    name: str
    design_point: str
    tag: str
    inputs: list
    outputs: list
    groups: list

    @property
    def csrs(self) -> list:
        """Every CSR in CSR order."""
        return [c for g in self.groups for c in g.window]

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
class AccSlot:
    """One snax_acc_cfg entry of a core: the slot's keys, the streamer template as the hjson
    has it, and its accelerator.json when the slot has one (None otherwise)."""

    name: str
    tcdm_ports: int
    narrow_tcdm_ports: int
    wide_tcdm_ports: int
    sparse_config: list
    num_rw_csr: int
    num_ro_csr: int
    streamer: dict
    accelerator: Accelerator
    at: str


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


def result_type(a: tuple, b: tuple):
    """NumPy's result type of two integer types (width, signed), as snax_types.hpp's
    snax_unit_result_type; None past 64 bits (a signed type with uint64: NumPy's float64)."""
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
    if access == 'rw' and width is None:
        raise CfgKeyError(node.file, node.where('width'), 'missing: a read-write CSR has a width')
    if access == 'ro' and width is not None:
        raise CfgTypeError(node.file, node.where('width'), 'a read-only CSR has no width')
    if width is not None and not 1 <= width <= 32:
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
    if op is not None and op not in OPS:
        raise CfgTypeError(node.file, params.where('op'), f'{op!r}, not an op ({", ".join(OPS)})')
    if facts.only_op is not None and op != facts.only_op:
        raise CfgTargetError(node.file, params.where('op'),
            f'{op!r}: {datapath} {facts.only_op}s; a fold of another op is not modelled')
    for key in ('accumulate', 'regOut'):
        params.get(key, bool, None)
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
    csrs = [_csr(c) for c in node.nodes('csrs')]
    for i, c in enumerate(csrs):
        if c.name not in UNIT_RW or c.access != 'rw':
            raise CfgTargetError(node.file, f'{node.where("csrs")}[{i}]',
                f'{c.name} ({c.access}): the unit CSRs modelled are {", ".join(UNIT_RW)} (rw)')
    fold = facts.is_fold(params.value)
    if (fold and t is None) != ('JOB_BEATS' in [c.name for c in csrs]):
        raise CfgSlotError(node.file, node.where('csrs'),
            f'{[c.name for c in csrs]}: a fold without params.T has JOB_BEATS, any other unit '
            'none')
    unit_ports = {key: _port(ports.node(key)) for key in ports.value}
    lanes = next(iter(unit_ports.values())).lanes
    want = (facts.latency(params.value), lanes if facts.serial else 1)
    if (latency, ii, span) != (*want[:1], 1, want[1]):
        raise CfgTargetError(node.file, node.where('timing'),
            f'gen.timing: latency {latency}, ii {ii}, span {span}; {datapath} here is latency '
            f'{want[0]}, ii 1, span {want[1]}')
    return Unit(name=node.get('name', str), brm=node.get('brm', str), datapath=datapath,
                ports=unit_ports, op_type=op_type, params=dict(params.value), latency=latency,
                ii=ii, csrs=csrs, span=span)


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
            f'{[c.name for c in csrs]}: a group\'s own CSRs are START, JOBS (rw), STATUS, COUNTER '
            '(ro), in that order')
    return Group(name=node.get('name', str), csrs=csrs, units=units, links=links)


def _accelerator(node: _Node) -> Accelerator:
    """accelerator.json, checked on its own (the slot's checks: _check_slot)."""
    for key in OLD_DATAPATH_KEYS:
        if key in node.value:
            raise CfgTypeError(node.file, node.where(key), 'a key of the datapath block, which '
                'accelerator.json replaced (snax-forge C§17, D145): regenerate the design point')
    acc = Accelerator(
        name=node.get('name', str),
        design_point=node.get('design_point', str),
        tag=node.get('tag', str),
        inputs=_names(node, 'inputs'),
        outputs=_names(node, 'outputs'),
        groups=[_group(g) for g in node.nodes('groups')],
    )
    if not acc.groups:
        raise CfgTypeError(node.file, node.where('groups'), 'no group')

    # The offsets in CSR order, contiguous from 0: read, never computed
    for i, csr in enumerate(acc.csrs):
        if csr.offset != i:
            group = next(g.name for g in acc.groups if csr in g.window)
            raise CfgSlotError(node.file, node.where('groups'),
                f'group {group}\'s {csr.name} has offset {csr.offset}, but is CSR {i} in CSR '
                'order (per group START, JOBS, the units\' R/W CSRs, STATUS, COUNTER): the '
                'offsets must be contiguous from 0')

    # The outer ports: each names a port of a unit, once; unit names are unique
    units = {}
    for g in acc.groups:
        for u in g.units:
            if u.name in units:
                raise CfgSlotError(node.file, node.where('groups'), f'unit {u.name!r} twice')
            units[u.name] = u
    seen = set()
    for key in ('inputs', 'outputs'):
        for i, entry in enumerate(getattr(acc, key)):
            unit, _, port = entry.partition('.')
            if unit not in units or port not in units[unit].ports:
                raise CfgSlotError(node.file, f'{node.where(key)}[{i}]',
                    f'{entry!r} names no port of a unit ({", ".join(units)})')
            if entry in seen:
                raise CfgSlotError(node.file, f'{node.where(key)}[{i}]', f'{entry!r} twice')
            seen.add(entry)
    _check_links(node, acc)
    for u in units.values():
        _check_shape(node, acc, u)
    return acc


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
                f'units {names}: a group is a chain until tier A (fork and join)')
        for u in g.units:
            outer_in = [p for p, d in dirs_of(u).items()
                        if d == 'in' and f'{u.name}.{p}' not in linked]
            if u.span > 1 and outer_in:
                raise CfgTargetError(node.file, node.where('inputs'),
                    f'gen.span: accelerator {acc.name}: unit {u.name} (span {u.span}) reads '
                    f'{outer_in} from the streamer: a unit with span > 1 reads from a link until B2')


def _check_shape(node: _Node, acc: Accelerator, u: Unit):
    """A unit's ports against its datapath: their number, lanes and types."""
    dirs = dirs_of(u)
    ins = [u.ports[p] for p in u.ports if dirs[p] == 'in']
    outs = [u.ports[p] for p in u.ports if dirs[p] == 'out']
    facts = CATALOGUE[u.datapath]
    plain = facts.nb_inputs(u.params) == 3
    n_in = facts.nb_inputs(u.params)
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
    a, b = ((p.width, p.signed) for p in ins[:2])
    t = result_type(a, b)
    if t is None:
        raise CfgTypeError(node.file, node.where('groups'),
            f'unit {u.name}: {type_name(*a)} with {type_name(*b)} has no integer result type '
            '(NumPy gives float64)')
    if u.op_type != type_name(*t):
        raise CfgSlotError(node.file, node.where('groups'),
            f'unit {u.name}: opType {u.op_type}, but its inputs\' result type is '
            f'{type_name(*t)} (snax_unit_result_type)')


def _slot(acc: _Node) -> AccSlot:
    ports = acc.get('snax_tcdm_ports', int)
    sparse = acc.get('sparse_interconnect_config', list, None)
    if sparse is not None:
        for i, entry in enumerate(sparse):
            if not (isinstance(entry, list) and len(entry) == 2
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in entry)):
                raise CfgTypeError(acc.file, f'{acc.where("sparse_interconnect_config")}[{i}]',
                    f'must be [width, granularity], got {entry!r}')
    streamer = acc.get('snax_streamer_cfg', dict, None)
    accelerator = acc.node('snax_datapath_cfg', None)
    slot = AccSlot(
        name=acc.get('snax_acc_name', str),
        tcdm_ports=ports,
        narrow_tcdm_ports=acc.get('snax_narrow_tcdm_ports', int, None),
        wide_tcdm_ports=acc.get('snax_wide_tcdm_ports', int, None),
        sparse_config=sparse,
        num_rw_csr=acc.get('snax_num_rw_csr', int),
        num_ro_csr=acc.get('snax_num_ro_csr', int),
        streamer=streamer,
        accelerator=None if accelerator is None else _accelerator(accelerator),
        at=acc.at,
    )
    _check_slot(acc, slot)
    return slot


def _check_slot(acc: _Node, slot: AccSlot):
    """The slot's counts against its streamer, ports and datapath."""
    def fail(key, why):
        raise CfgSlotError(acc.file, acc.where(key), why)

    if slot.streamer is not None:
        for mover in UNMODELLED_MOVERS:
            if mover in slot.streamer:
                raise CfgTargetError(acc.file, acc.where(f'snax_streamer_cfg.{mover}'),
                    f'not modelled: the streamer has {", ".join(MOVERS)}')
        for mover in MOVERS:
            params = slot.streamer.get(mover, {})
            for i, (bounds, channels) in enumerate(zip(params.get('spatial_bounds', []),
                                                       params.get('num_channel', []))):
                why = spatial_mismatch(bounds, channels)
                if why is not None:
                    fail(f'snax_streamer_cfg.{mover}.spatial_bounds[{i}]', why)
        channels = streamer_channels(slot.streamer)
        if channels != slot.tcdm_ports:
            fail('snax_tcdm_ports', f'{slot.tcdm_ports}, but the streamer has {channels} '
                'channels (num_channel over its movers)')
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
    if slot.accelerator is not None:
        _check_accelerator(acc, slot)


def _check_accelerator(acc: _Node, slot: AccSlot):
    """accelerator.json against the slot: its outer ports against the streamer's movers, each
    port's words per beat against its mover's num_channel (SnaxGroup has no FIFO slicer, so
    they must match: the streamer would refuse the beat's size mid-run), and the CSR counts."""
    accelerator = slot.accelerator

    def fail(key, why):
        raise CfgSlotError(acc.file, acc.where(key), why)

    if slot.streamer is None:
        fail('snax_streamer_cfg', 'missing: accelerator.json needs the streamer it is fed by')
    for key, mover in (('inputs', 'data_reader_params'), ('outputs', 'data_writer_params')):
        names = getattr(accelerator, key)
        channels = slot.streamer.get(mover, {}).get('num_channel', [])
        if len(names) != len(channels):
            fail(f'snax_datapath_cfg.{key}', f'{names}, but the streamer has {len(channels)} '
                 f'{mover}: one port each, in order')
        for i, entry in enumerate(names):
            unit, _, name = entry.partition('.')
            u = accelerator.unit(unit)
            port = u.ports[name]
            if CATALOGUE[u.datapath].reduces and key == 'outputs':
                if channels[i] != 1:
                    fail(f'snax_datapath_cfg.{key}[{i}]', f"{entry}: a fold's output is one "
                         f'64-bit word per beat, but {mover}[{i}] has num_channel {channels[i]}')
                continue
            bits = port.lanes * port.width
            if bits % 64 != 0:
                fail(f'snax_datapath_cfg.{key}[{i}]', f'{entry}: lanes {port.lanes} x '
                     f'{port.width} bits is not a whole number of 64-bit channel words')
            if bits // 64 != channels[i]:
                fail(f'snax_datapath_cfg.{key}[{i}]', f'{entry}: lanes {port.lanes} x '
                     f'{port.width} bits is {bits // 64} 64-bit words per beat, but {mover}[{i}] '
                     f'has num_channel {channels[i]}: SnaxGroup has no FIFO slicer, so they must '
                     'match')
    if slot.num_rw_csr != accelerator.num_rw:
        fail('snax_num_rw_csr', f'{slot.num_rw_csr}, but accelerator.json has '
             f'{accelerator.num_rw} read-write CSRs')
    if slot.num_ro_csr != accelerator.num_ro:
        fail('snax_num_ro_csr', f'{slot.num_ro_csr}, but accelerator.json has '
             f'{accelerator.num_ro} read-only CSRs (STATUS and COUNTER per group)')


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
