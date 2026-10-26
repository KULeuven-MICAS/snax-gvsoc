#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_cluster's cluster hjson, read for a SNAX-GVSoC target.

    load(path) -> ClusterCfg

The hjson is the contract: snax_cluster's clustergen and snaxgen read the
same file. A design is three files: the cluster file, named after its base
platform (snax_forge.hjson), the streamer file and the accelerator file, named
after its slot (snax_forge_streamer.hjson, the streamer template, and
snax_forge_acc.hjson, the datapath block). The cluster's snax_acc_cfg entry
(the slot) keeps the slot keys; its snax_streamer_cfg and snax_datapath_cfg
are $refs to the other two, each the whole file.

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
it) and snax_datapath_cfg (the datapath block, optional; Datapath).

The datapath block: what the standard composite (snax_unit_acc.py) builds
the slot's unit and shell from, SnaxUnit's arguments by name:

    unit           the unit kind: SnaxUnit
    inputs         the unit's input ports in order, one per streamer reader
    outputs        its output ports in order, one per streamer writer
    lanes, op, control, wait, latency, ii
    in_widths, in_signed, out_widths, out_signed
                   each port's element type: its width (8, 16, 32 or 64)
                   and signedness, one per input and one per output; all
                   four or none
    data_width, signed
                   without the four: every port's width and signedness
                   (Datapath holds the four lists either way)
    config         the role of each configuration word (optional; [count])
    fields         the shell's configuration CSRs in order; start follows

An elementwise datapath's inputs need an integer result type (NumPy's
result_type): a signed type with uint64 has none (NumPy gives float64).

The slot's counts must agree with what its refs give: snax_tcdm_ports is the
streamer's num_channel summed over its movers, and the narrow and wide ports
or the sparse config's widths add up to it; with a datapath block,
snax_num_rw_csr is the shell's fields plus start, and snax_num_ro_csr 2
(busy and the counter).

Everything wrong is a SnaxCfgError naming the file and the key's path:
CfgParseError (not an hjson object), CfgRefError (a $ref that does not
resolve), CfgKeyError (a key missing), CfgTypeError (a value of the wrong
type), CfgSlotError (slot counts that disagree with the accelerator file);
a target refuses what it cannot model with CfgTargetError.
"""

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
# The read-only CSRs of a shell: busy and the counter
SHELL_RO_CSRS = 2
# A datapath port's element widths
ELEMENT_WIDTHS = (8, 16, 32, 64)
# A datapath port's type lists: all four or none (data_width and signed then)
TYPE_KEYS = ('in_widths', 'in_signed', 'out_widths', 'out_signed')


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
class Datapath:
    """A slot's datapath block; see the module doc."""

    unit: str
    inputs: list
    outputs: list
    lanes: int
    in_widths: list
    in_signed: list
    out_widths: list
    out_signed: list
    op: int
    control: str
    wait: str
    latency: int
    ii: int
    config: list
    fields: list


@dataclass(frozen=True)
class AccSlot:
    """One snax_acc_cfg entry of a core: the slot's keys, the streamer template as the hjson
    has it, and the datapath block when the slot has one (None otherwise)."""

    name: str
    tcdm_ports: int
    narrow_tcdm_ports: int
    wide_tcdm_ports: int
    sparse_config: list
    num_rw_csr: int
    num_ro_csr: int
    streamer: dict
    datapath: Datapath
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


def result_type(a: tuple, b: tuple):
    """NumPy's result type of two integer types (width, signed), as snax_unit.hpp's
    snax_unit_result_type; None past 64 bits (a signed type with uint64: NumPy's float64)."""
    if a[1] == b[1]:
        return max(a[0], b[0]), a[1]
    s, u = (a, b) if a[1] else (b, a)
    if s[0] > u[0]:
        return s
    return (2 * u[0], True) if 2 * u[0] <= 64 else None


def _typed_list(node: _Node, key, kind) -> list:
    """A list of integers or of booleans."""
    values = node.get(key, list)
    if not all(isinstance(v, kind) and (kind is bool or not isinstance(v, bool))
               for v in values):
        raise CfgTypeError(node.file, node.where(key),
            f'must be a list of {"booleans" if kind is bool else "integers"}, got {values!r}')
    return values


def _port_types(node: _Node, inputs: list, outputs: list) -> dict:
    """The four type lists: given, or data_width and signed for every port; checked."""
    given = [key for key in TYPE_KEYS if key in node.value]
    if not given:
        width, signed = node.get('data_width', int), node.get('signed', bool)
        types = {'in_widths': [width] * len(inputs), 'in_signed': [signed] * len(inputs),
                 'out_widths': [width] * len(outputs), 'out_signed': [signed] * len(outputs)}
        if width not in ELEMENT_WIDTHS:
            raise CfgTypeError(node.file, node.where('data_width'),
                f'{width}, must be 8, 16, 32 or 64')
        return types
    if len(given) != len(TYPE_KEYS):
        missing = next(key for key in TYPE_KEYS if key not in given)
        raise CfgKeyError(node.file, node.where(missing),
            f'missing: {", ".join(TYPE_KEYS)} go together (without them, data_width and signed '
            'give every port)')
    types = {key: _typed_list(node, key, bool if key.endswith('signed') else int)
             for key in TYPE_KEYS}
    for key in TYPE_KEYS:
        ports, what = (inputs, 'input') if key.startswith('in_') else (outputs, 'output')
        if len(types[key]) != len(ports):
            raise CfgSlotError(node.file, node.where(key),
                f'{len(types[key])} values, one per {what} ({len(ports)}: {ports})')
    for key in ('in_widths', 'out_widths'):
        for i, width in enumerate(types[key]):
            if width not in ELEMENT_WIDTHS:
                raise CfgTypeError(node.file, f'{node.where(key)}[{i}]',
                    f'{width}, must be 8, 16, 32 or 64')
    if len(inputs) == 2:
        a, b = zip(types['in_widths'], types['in_signed'])
        if result_type(a, b) is None:
            raise CfgTypeError(node.file, node.where('in_signed'),
                f'{type_name(*a)} with {type_name(*b)} has no integer result type (NumPy gives '
                'float64)')
    return types


def _datapath(node: _Node) -> Datapath:
    inputs, outputs = _names(node, 'inputs'), _names(node, 'outputs')
    return Datapath(
        unit=node.get('unit', str),
        inputs=inputs,
        outputs=outputs,
        lanes=node.get('lanes', int),
        **_port_types(node, inputs, outputs),
        op=node.get('op', int),
        control=node.get('control', str),
        wait=node.get('wait', str),
        latency=node.get('latency', int),
        ii=node.get('ii', int),
        config=_names(node, 'config', ['count']),
        fields=_names(node, 'fields'),
    )


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
    datapath = acc.node('snax_datapath_cfg', None)
    slot = AccSlot(
        name=acc.get('snax_acc_name', str),
        tcdm_ports=ports,
        narrow_tcdm_ports=acc.get('snax_narrow_tcdm_ports', int, None),
        wide_tcdm_ports=acc.get('snax_wide_tcdm_ports', int, None),
        sparse_config=sparse,
        num_rw_csr=acc.get('snax_num_rw_csr', int),
        num_ro_csr=acc.get('snax_num_ro_csr', int),
        streamer=streamer,
        datapath=None if datapath is None else _datapath(datapath),
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
    if slot.datapath is not None:
        fields = slot.datapath.fields
        if slot.streamer is None:
            fail('snax_streamer_cfg', 'missing: a datapath block needs the streamer it is fed by')
        for ports, mover in (('inputs', 'data_reader_params'), ('outputs', 'data_writer_params')):
            names = getattr(slot.datapath, ports)
            movers = len(slot.streamer.get(mover, {}).get('num_channel', []))
            if len(names) != movers:
                fail(f'snax_datapath_cfg.{ports}', f'{names}, but the streamer has {movers} '
                    f'{mover}: one port each, in order')
        if slot.num_rw_csr != len(fields) + 1:
            fail('snax_num_rw_csr', f'{slot.num_rw_csr}, but the datapath has '
                f'{len(fields)} shell fields {fields} and start')
        if slot.num_ro_csr != SHELL_RO_CSRS:
            fail('snax_num_ro_csr', f'{slot.num_ro_csr}, but a shell has {SHELL_RO_CSRS} '
                '(busy and the counter)')


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
