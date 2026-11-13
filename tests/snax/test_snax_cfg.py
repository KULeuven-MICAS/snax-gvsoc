# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_cfg.py. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Reads sw/cfg/snitch_cluster.hjson and forge/'s fixtures, then broken copies
of forge/vecadd/'s cluster (its streamer file and accelerator.json inlined,
written as JSON into a temporary folder), broken accelerator.json files
beside it, hand-written dot 1 designs: two
accelerators vmul and vsum in two streamer sets, and dot_1_enc, the two as
one accelerator dot of two groups; then the sets' refusals and the slot form
before sets (snax_streamer_cfg), read as one set. snax_cluster's copy in
sw/cfg/snax_forge/ is never read.
"""

import copy
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "snax"))
import hjson  # noqa: E402
import snax_cfg  # noqa: E402
from snax_cfg import (Accelerator, Csr, Description, Group, Link, MoverUser, Port,  # noqa: E402
                      PortMux, SharedMover, Unit)

CFG = ROOT / "sw" / "cfg"
FORGE = ROOT / "forge"
# forge/vecadd/'s cluster file, the snax_hjson target's default
CLUSTER = FORGE / "vecadd" / "snax_forge.hjson"

# The streamer of forge/vecadd/ and vecmul/
STREAMER = {
    "data_reader_params": {
        "spatial_bounds": [[4], [4]],
        "temporal_dim": [1, 1],
        "num_channel": [4, 4],
        "fifo_depth": [8, 8],
    },
    "data_writer_params": {
        "spatial_bounds": [[4]],
        "temporal_dim": [1],
        "num_channel": [4],
        "fifo_depth": [8],
    },
}


def group_csrs(base: int, between: int = 0) -> list:
    """A group's own CSRs from offset base, with between unit CSRs after JOBS."""
    return [Csr("START", "rw", base, 1), Csr("JOBS", "rw", base + 1, 32),
            Csr("STATUS", "ro", base + 2 + between, 2),
            Csr("BUSY_COUNTER", "ro", base + 3 + between, 32)]


def simd(name: str, op: str, dtype: str = "int64", brm: str = None) -> Unit:
    return Unit(name, brm or "simd", "SimdLanes",
                {p: Port(p, dtype, 4, "out" if p == "out" else "in") for p in ("a", "b", "out")},
                dtype, {"op": op}, 0, 1, [])


def fold(name: str, base: int, in_dtype: str = "int64", lanes: int = 1) -> Unit:
    return Unit(name, "accumulate", "TreeAccumulate",
                {"a": Port("in", in_dtype, lanes, "in"), "out": Port("out", "int64", 1, "out")}, None,
                {"op": "add"},
                1, 1, [Csr("JOB_BEATS", "rw", base + 2, 32)])


def description(design: str, *accelerators: Accelerator) -> Description:
    """accelerator.json of a design of forge/: its design point and tag, its accelerators."""
    return Description(f"out/design/{design}/design_point.json", f"snax_forge_{design}",
                       list(accelerators))


def accelerator(design: str, unit: Unit, between: int = 0) -> Description:
    """A design's accelerator.json: one accelerator acc of one group of one unit, from
    forge/."""
    ins = [k for k in unit.ports if k != "out"]
    return description(design, Accelerator("acc", [f"acc.{k}" for k in ins], ["acc.out"],
                                           [Group("acc", group_csrs(0, between), [unit], [])]))


# forge/vecadd/'s accelerator.json, parsed
VECADD = accelerator("vecadd", simd("acc", "add"))

MISA_RV32IMA = (1 << 30) | (1 << 12) | (1 << 8) | (1 << 0)


def inline(folder: Path, ref: dict):
    """The file a {$ref: "<file>"} names, parsed."""
    return json.loads(json.dumps(hjson.loads((folder / ref["$ref"]).read_text())))


def cluster():
    """CLUSTER, parsed, with its set's streamer file and accelerator.json in place of their
    $refs, so that a copy reads on its own."""
    d = hjson.loads(CLUSTER.read_text())
    slot = d["snax_forge_core_template"]["snax_acc_cfg"][0]
    for s in slot["snax_streamer_sets"]:
        s["snax_streamer_cfg"] = inline(CLUSTER.parent, s["snax_streamer_cfg"])
    slot["snax_datapath_cfg"] = inline(CLUSTER.parent, slot["snax_datapath_cfg"])
    return json.loads(json.dumps(d))


class SwCfg(unittest.TestCase):
    """snax_cluster's plain cluster in sw/cfg/."""

    def test_snitch(self):
        cfg = snax_cfg.load(CFG / "snitch_cluster.hjson")
        self.assertEqual(cfg.name, "snitch_cluster")
        self.assertEqual(len(cfg.cores), 9)
        self.assertEqual([core.xdma for core in cfg.cores], [False] * 8 + [True])
        self.assertTrue(all(core.accelerators == [] for core in cfg.cores))
        self.assertEqual(cfg.cores[0].misa, (1 << 30) | sum(1 << (ord(c) - ord("a"))
                                                             for c in "imafd"))


class Fixtures(unittest.TestCase):
    """forge/'s cluster files: snax-forge's base cluster renamed snax_forge_cluster, its slot
    snax_forge_<design> set for the design, a streamer set per accelerator, its
    accelerator.json read."""

    def slot(self, folder):
        """The folder's slot, named after its design (the manifest's: the folder's name but for
        rowsum_2_padded, rowsum_2 under the padded_rows layout, whose design is rowsum_2)."""
        cfg = snax_cfg.load(FORGE / folder / "snax_forge.hjson")
        self.assertEqual(cfg.name, "snax_forge_cluster")
        self.assertTrue(cfg.tcdm.sparse_interconnect)
        (slot,) = cfg.cores[0].accelerators
        design = json.loads((FORGE / folder / "manifest.json").read_text())["design"]
        self.assertEqual(slot.name, f"snax_forge_{design}")
        return slot

    def test_vecadd_cluster(self):
        """forge/vecadd/: the snax_hjson target's default."""
        cfg = snax_cfg.load(CLUSTER)
        self.assertEqual(cfg.boot_addr, 0x1000)
        self.assertEqual(cfg.base, 0x1000_0000)
        self.assertEqual((cfg.tcdm.size, cfg.tcdm.banks, cfg.tcdm.bank_width),
                         (128 * 1024, 32, 8))
        self.assertEqual((cfg.periph_size, cfg.zero_mem_size), (64 * 1024, 64 * 1024))
        self.assertEqual(cfg.dma, snax_cfg.Dma(512, 3, 3))
        self.assertEqual(cfg.dram, snax_cfg.Dram(0x8000_0000, 0x8000_0000))
        (core,) = cfg.cores  # one core, the slot and the DMA
        self.assertEqual((core.isa, core.xdma, core.num_int_outstanding_loads),
                         ("rv32ima", True, 1))
        self.assertEqual(core.misa, MISA_RV32IMA)
        slot = self.slot("vecadd")
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (12, 2, 2))
        self.assertEqual((slot.narrow_tcdm_ports, slot.wide_tcdm_ports, slot.sparse_config),
                         (None, None, [[12, 1]]))
        (one,) = slot.sets
        self.assertEqual((one.name, one.streamer, one.num_rw_csr, one.num_ro_csr, one.at),
                         ("acc", STREAMER, 2, 2, "snax_streamer_sets[0]"))
        self.assertEqual(slot.description, VECADD)

    def test_vecmul(self):
        slot = self.slot("vecmul")
        self.assertEqual(slot.sets[0].streamer, STREAMER)
        self.assertEqual(slot.description,
                         accelerator("vecmul", simd("acc", "mul")))

    def test_relu(self):
        """One stream: SimdLanes with one input a, params op max and k 0, opType int32, a's;
        a reader and a writer of two channels each."""
        slot = self.slot("relu")
        unit = Unit("acc", "simd", "SimdLanes",
                    {p: Port(p, "int32", 4, "out" if p == "out" else "in") for p in ("a", "out")},
                    "int32", {"op": "max", "k": 0}, 0, 1, [])
        self.assertEqual(slot.description, accelerator("relu", unit))
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (4, 2, 2))

    def test_axpy(self):
        """axpby with k1 read from its CSR: scalars {k1: int32}, the R/W CSR K1 (pin k1, 32
        bits) after JOBS, so STATUS and BUSY_COUNTER one later; 3 R/W CSRs."""
        slot = self.slot("axpy")
        unit = Unit("acc", "simd", "SimdLanes",
                    {p: Port(p, "int32", 4, "out" if p == "out" else "in") for p in ("a", "b", "out")},
                    "int32", {"op": "axpby"}, 0, 1, [Csr("K1", "rw", 2, 32, "k1")],
                    scalars={"k1": "int32"})
        self.assertEqual(slot.description, accelerator("axpy", unit, between=1))
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (6, 3, 2))
        self.assertEqual(unit.slot_params, {"op": "axpby", "k1": None})

    def test_axpy_baked(self):
        """axpby with k1 baked at 3: params.k1, no scalar, no unit CSR."""
        slot = self.slot("axpy_baked")
        unit = Unit("acc", "simd", "SimdLanes",
                    {p: Port(p, "int32", 4, "out" if p == "out" else "in") for p in ("a", "b", "out")},
                    "int32", {"op": "axpby", "k1": 3}, 0, 1, [])
        self.assertEqual(slot.description, accelerator("axpy_baked", unit))
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (6, 2, 2))

    def test_vsum_tree_i32(self):
        """A fold: JOB_BEATS between JOBS and STATUS, int32 lanes into an int64 sum."""
        slot = self.slot("vsum_tree_i32")
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (3, 3, 2))
        self.assertEqual(slot.description,
                         accelerator("vsum_tree_i32", fold("acc", 0, "int32", 4), between=1))
        self.assertEqual([c.name for c in slot.description.csrs],
                         ["START", "JOBS", "JOB_BEATS", "STATUS", "BUSY_COUNTER"])
        self.assertEqual(slot.description.groups[0].rw, ["START", "JOBS", "JOB_BEATS"])
        # The widths: START a strobe, JOBS and JOB_BEATS job_width, BUSY_COUNTER busy_counter_width
        self.assertEqual(slot.description.groups[0].rw_widths, [1, 32, 32])
        self.assertEqual(slot.description.groups[0].busy_counter_width, 32)

    def test_every_fixture_reads(self):
        for folder in sorted(p for p in FORGE.iterdir() if p.is_dir()):
            with self.subTest(folder.name):
                slot = self.slot(folder.name)
                self.assertEqual(slot.description.design_point,
                                 f"out/design/{folder.name}/design_point.json")
                self.assertEqual(slot.description.tag, slot.name)
                # A set per accelerator, named after it; STATUS and BUSY_COUNTER per group
                self.assertEqual([x.name for x in slot.sets],
                                 [a.name for a in slot.description.accelerators])
                for x, a in zip(slot.sets, slot.description.accelerators):
                    self.assertEqual(x.num_ro_csr, 2 * len(a.groups))


class Misa(unittest.TestCase):
    def test_strings(self):
        self.assertEqual(snax_cfg.misa("rv32ima"), MISA_RV32IMA)
        self.assertEqual(snax_cfg.misa("RV32G"), snax_cfg.misa("rv32imafd"))
        self.assertEqual(snax_cfg.misa("rv64i"), (2 << 62) | (1 << 8))
        for bad in ("rv16i", "x86", "rv32i2p0"):
            with self.assertRaises(ValueError):
                snax_cfg.misa(bad)


class Broken(unittest.TestCase):
    """Copies of CLUSTER with one thing wrong, each a named error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value) if not isinstance(value, str) else value)
        return path

    def fails(self, error, value, path_part, why_part=""):
        with self.assertRaises(error) as ctx:
            snax_cfg.load(self.write("cluster.hjson", value))
        self.assertIn(path_part, ctx.exception.path)
        self.assertIn(why_part, ctx.exception.why)
        self.assertIsInstance(ctx.exception, snax_cfg.SnaxCfgError)
        return ctx.exception

    def slot(self, d):
        return d["snax_forge_core_template"]["snax_acc_cfg"][0]

    def set0(self, d):
        return self.slot(d)["snax_streamer_sets"][0]

    def test_parse(self):
        self.fails(snax_cfg.CfgParseError, "{ cluster: ", "")
        self.fails(snax_cfg.CfgParseError, "[1, 2]", "", "must be an object")
        with self.assertRaises(snax_cfg.CfgParseError):
            snax_cfg.load(self.dir / "none.hjson")

    def test_ref_missing_key(self):
        d = cluster()
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "#/no_such_template"}
        self.fails(snax_cfg.CfgRefError, d,
                   "snax_acc_cfg[0].snax_streamer_sets[0].snax_streamer_cfg",
                   "no 'no_such_template'")

    def test_ref_missing_file(self):
        d = cluster()
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "acc.hjson#/snax_streamer_cfg"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")

    def test_ref_malformed(self):
        d = cluster()
        d["streamer_template"] = self.set0(d)["snax_streamer_cfg"]
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "#/streamer_template", "x": 1}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "is not")
        # A key without #/ is a whole file's name: no such file
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "#streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "must start with /")

    def test_ref_cycle(self):
        d = cluster()
        d["loop"] = {"a": {"$ref": "#/loop"}}
        self.set0(d)["snax_streamer_cfg"] = {"$ref": "#/loop"}
        self.fails(snax_cfg.CfgRefError, d, "loop", "refers to itself")

    def test_missing_key(self):
        d = cluster()
        del d["cluster"]["tcdm"]["banks"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.tcdm.banks", "missing")
        d = cluster()
        del self.set0(d)["snax_num_rw_csr"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.hives[0].cores[0].snax_acc_cfg[0]"
                   ".snax_streamer_sets[0].snax_num_rw_csr", "missing")

    def test_wrong_type(self):
        d = cluster()
        d["cluster"]["tcdm"]["banks"] = "32"
        self.fails(snax_cfg.CfgTypeError, d, "cluster.tcdm.banks", "an integer")
        d = cluster()
        d["cluster"]["dma_data_width"] = True
        self.fails(snax_cfg.CfgTypeError, d, "cluster.dma_data_width", "an integer")
        d = cluster()
        d["cluster"]["tcdm"]["sparse_interconnect"] = 1
        self.fails(snax_cfg.CfgTypeError, d, "cluster.tcdm.sparse_interconnect", "a boolean")
        d = cluster()
        self.slot(d)["sparse_interconnect_config"] = [[12]]
        self.fails(snax_cfg.CfgTypeError, d, "sparse_interconnect_config[0]",
                   "[width, granularity]")
        d = cluster()
        d["cluster"]["hives"][0]["cores"][0] = "core"
        self.fails(snax_cfg.CfgTypeError, d, "cluster.hives[0].cores[0]", "an object")

    def test_slot_ports(self):
        d = cluster()
        self.slot(d)["snax_tcdm_ports"] = 8
        self.fails(snax_cfg.CfgSlotError, d, "snax_tcdm_ports", "12 channels")
        d = cluster()
        self.slot(d)["sparse_interconnect_config"] = [[8, 1], [8, 1]]
        self.fails(snax_cfg.CfgSlotError, d, "sparse_interconnect_config", "add up to 16")
        d = cluster()
        self.slot(d)["snax_narrow_tcdm_ports"] = 8
        self.slot(d)["snax_wide_tcdm_ports"] = 0
        self.fails(snax_cfg.CfgSlotError, d, "snax_narrow_tcdm_ports", "narrow 8 + wide 0")

    def test_reader_writer_refused(self):
        """snax_cluster's data_reader_writer_params: no mover of the model's streamer."""
        d = cluster()
        self.set0(d)["snax_streamer_cfg"]["data_reader_writer_params"] = {
            "spatial_bounds": [[4]], "temporal_dim": [1], "num_channel": [4], "fifo_depth": [8]}
        self.fails(snax_cfg.CfgTargetError, d,
                   "snax_streamer_sets[0].snax_streamer_cfg.data_reader_writer_params",
                   "not modelled")


def acc_json(desc: Description) -> dict:
    """A Description as accelerator.json writes it (snax-forge's gen/accelerator.py)."""
    def csr(c):
        d = {"name": c.name, "access": c.access, "offset": c.offset}
        if c.width is not None:
            d["width"] = c.width
        if c.pin is not None:
            d["pin"] = c.pin
        return d

    def unit(u):
        d = {"name": u.name, "brm": u.brm, "datapath": u.datapath,
             "ports": {k: {"port": p.port, "dir": p.dir,
                           "dtype": p.dtype, "lanes": p.lanes}
                       for k, p in u.ports.items()}}
        if u.op_type is not None:
            d["opType"] = u.op_type
        d["params"] = dict(u.params)
        if u.scalars:
            d["scalars"] = dict(u.scalars)
        d.update({"timing": {"latency": u.latency, "ii": u.ii, "span": u.span},
                  "csrs": [csr(c) for c in u.csrs]})
        return d

    def link(k):
        return {"name": k.name, "from": k.from_, "to": k.to, "depth": k.depth}

    def acc(a):
        d = {"name": a.name, "inputs": list(a.inputs), "outputs": list(a.outputs),
             "groups": [{"name": g.name, "csrs": [csr(c) for c in g.csrs],
                         "units": [unit(u) for u in g.units],
                         "links": [link(k) for k in g.links]}
                        for g in a.groups]}
        if a.port_mux is not None:
            d["movers"] = [{"name": m.name, "role": m.role, "num_channel": m.num_channel,
                            "masked": m.masked,
                            "users": [{"group": u.group, "port": u.port,
                                       "num_channel": u.num_channel} for u in m.users]}
                           for m in a.movers]
            d["port_mux"] = {"groups": list(a.port_mux.groups), "csr": csr(a.port_mux.csr)}
        return d

    return {"design_point": desc.design_point, "tag": desc.tag,
            "accelerators": [acc(a) for a in desc.accelerators]}


def streamer(readers: list, writers: list) -> dict:
    """A streamer template of one-loop movers, each of its num_channel (spatial bounds the
    same, FIFOs 8 deep)."""
    def movers(channels):
        n = len(channels)
        return {"spatial_bounds": [[c] for c in channels], "temporal_dim": [1] * n,
                "num_channel": list(channels), "fifo_depth": [8] * n}
    return {"data_reader_params": movers(readers), "data_writer_params": movers(writers)}


# dot 1: the units vmul (an SimdLanes mul) and vsum (a
# TreeAccumulate over 4 lanes, with JOB_BEATS), each an accelerator of one group, in two
# streamer sets: vmul's CSRs START 0, JOBS 1, STATUS 2, BUSY_COUNTER 3, vsum's START 4, JOBS 5,
# JOB_BEATS 6, STATUS 7, BUSY_COUNTER 8 (the offsets run over both accelerators)
VMUL = Accelerator("vmul", ["vmul.a", "vmul.b"], ["vmul.out"],
                   [Group("vmul", group_csrs(0), [simd("vmul", "mul")], [])])
VSUM = Accelerator("vsum", ["vsum.a"], ["vsum.out"],
                   [Group("vsum", group_csrs(4, 1), [fold("vsum", 4, lanes=4)], [])])
DOT1 = description("dot_1", VMUL, VSUM)
VMUL_STREAMER = streamer([4, 4], [4])
VSUM_STREAMER = streamer([4], [1])
# dot_1_enc: the same two groups in one accelerator dot, one set; readers vmul.a,
# vmul.b, vsum.a, writers vmul.out, vsum.out
DOT = description("dot_1_enc", Accelerator("dot", ["vmul.a", "vmul.b", "vsum.a"],
                                           ["vmul.out", "vsum.out"], VMUL.groups + VSUM.groups))
DOT_STREAMER = streamer([4, 4, 4], [4, 1])
# dot 1 with share_ports on tmp0: vmul and vsum on one set whose movers they
# share, per role the k-th widest port of each group on mover k: reader0 vmul.a / vsum.a,
# reader1 vmul.b, writer0 vmul.out / vsum.out (1 of its 4 channels, so masked); PORT_MUX_SEL
# at offset 9, after vsum's window
DOT_SHARED = description("dot_1_shared", Accelerator(
    "dot", ["vmul.a", "vmul.b", "vsum.a"], ["vmul.out", "vsum.out"], VMUL.groups + VSUM.groups,
    [SharedMover("reader0", "read", 4, False, [MoverUser("vmul", "vmul.a", 4),
                                                MoverUser("vsum", "vsum.a", 4)]),
     SharedMover("reader1", "read", 4, False, [MoverUser("vmul", "vmul.b", 4)]),
     SharedMover("writer0", "write", 4, True, [MoverUser("vmul", "vmul.out", 4),
                                                MoverUser("vsum", "vsum.out", 1)])],
    PortMux(["vmul", "vsum"], Csr("PORT_MUX_SEL", "rw", 9, 1))))
DOT_SHARED_STREAMER = streamer([4, 4], [4])
DOT_SHARED_STREAMER["data_writer_params"]["configurable_channel"] = [True]


# dot 4: one group dot, a Mac unit (JOB_BEATS at 2) wired into a
# TreeAccumulate unit of fixed T 1 by the link out_partial; readers mac.a, mac.b, writer sum.out
DOT4 = description("dot_4", Accelerator(
    "dot", ["mac.a", "mac.b"], ["sum.out"],
    [Group("dot", group_csrs(0, 1), [
        Unit("mac", "mac", "Mac", {p: Port(p, "int64", 4, "out" if p == "out" else "in")
                                   for p in ("a", "b", "out")}, "int64",
             {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)], 1),
        Unit("sum", "accumulate", "TreeAccumulate",
             {"a": Port("in", "int64", 4, "in"), "out": Port("out", "int64", 1, "out")}, None,
             {"op": "add", "T": 1}, 1, 1, [], 1),
    ], [Link("out_partial", "mac.out", "sum.a", 0)])]))
DOT4_STREAMER = streamer([4, 4], [1])


def write_sets(folder: Path, acc: dict, sets: list) -> Path:
    """forge/vecadd/'s cluster file in folder with its slot set for acc and sets, each
    (name, streamer, rw, ro): a streamer file per set and accelerator.json beside it, as
    snax-forge writes them; its path."""
    d = hjson.loads(CLUSTER.read_text())
    slot = d["snax_forge_core_template"]["snax_acc_cfg"][0]
    ports = sum(snax_cfg.streamer_channels(st) for _, st, _, _ in sets)
    entries = []
    for name, st, rw, ro in sets:
        (folder / f"streamer_{name}.hjson").write_text(json.dumps(st))
        entries.append({"name": name, "snax_streamer_cfg": {"$ref": f"streamer_{name}.hjson"},
                        "snax_num_rw_csr": rw, "snax_num_ro_csr": ro})
    slot.update(snax_tcdm_ports=ports, sparse_interconnect_config=[[ports, 1]],
                snax_streamer_sets=entries, snax_datapath_cfg={"$ref": "accelerator.json"})
    (folder / "accelerator.json").write_text(json.dumps(acc))
    path = folder / "snax_forge.hjson"
    path.write_text(json.dumps(d))
    return path


def write_design(folder: Path, acc: dict, streamer: dict, rw: int, ro: int) -> Path:
    """write_sets with one set, named after acc's one accelerator."""
    return write_sets(folder, acc, [(acc["accelerators"][0]["name"], streamer, rw, ro)])


def dot_cluster(folder: Path) -> Path:
    """dot_1_enc in folder (DOT, DOT_STREAMER): one set; its cluster file."""
    return write_design(folder, acc_json(DOT), DOT_STREAMER, 5, 4)


def dot_shared_cluster(folder: Path) -> Path:
    """dot 1 shared in folder (DOT_SHARED, DOT_SHARED_STREAMER): one set; its cluster file."""
    return write_design(folder, acc_json(DOT_SHARED), DOT_SHARED_STREAMER, 6, 4)


def dot1_cluster(folder: Path) -> Path:
    """dot 1 in folder (DOT1): the sets vmul and vsum; its cluster file."""
    return write_sets(folder, acc_json(DOT1), [("vmul", VMUL_STREAMER, 2, 2),
                                               ("vsum", VSUM_STREAMER, 3, 2)])


class AccJson(unittest.TestCase):
    """accelerator.json beside the cluster file: what it holds, and each thing wrong in it a
    named error at its key."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.acc = acc_json(VECADD)
        self.streamer = copy.deepcopy(STREAMER)
        self.rw, self.ro = 2, 2

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        path = write_design(self.dir, self.acc, self.streamer, self.rw, self.ro)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot

    def fails(self, error, path_part, why_part=""):
        with self.assertRaises(error) as ctx:
            self.load()
        self.assertIn(path_part, ctx.exception.path)
        self.assertIn(why_part, ctx.exception.why)
        return ctx.exception

    def unit(self, group=0):
        return self.acc["accelerators"][0]["groups"][group]["units"][0]

    def test_resolved(self):
        self.assertEqual(self.load().description, VECADD)
        self.assertEqual(acc_json(VECADD), json.loads((FORGE / "vecadd" / "accelerator.json")
                                                      .read_text()))

    def test_the_old_datapath_block_is_refused(self):
        for key in ("unit", "control", "config", "wait", "fields"):
            self.acc = acc_json(VECADD)
            self.acc[key] = "x"
            self.fails(snax_cfg.CfgTypeError, f"snax_datapath_cfg.{key}",
                       "accelerator.json replaced")

    def test_offsets_contiguous(self):
        self.acc["accelerators"][0]["groups"][0]["csrs"][2]["offset"] = 3
        self.acc["accelerators"][0]["groups"][0]["csrs"][3]["offset"] = 4
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators",
                   "STATUS has offset 3, but is CSR 2 in CSR order")

    def test_group_csrs_in_order(self):
        csrs = self.acc["accelerators"][0]["groups"][0]["csrs"]
        csrs[0], csrs[1] = csrs[1], csrs[0]
        self.fails(snax_cfg.CfgSlotError, "groups[0].csrs", "START, JOBS (rw), STATUS, BUSY_COUNTER")
        self.acc = acc_json(VECADD)
        del self.acc["accelerators"][0]["groups"][0]["csrs"][3]
        self.fails(snax_cfg.CfgSlotError, "groups[0].csrs", "START, JOBS (rw), STATUS, BUSY_COUNTER")

    def test_csr_fields(self):
        del self.acc["accelerators"][0]["groups"][0]["csrs"][2]["width"]
        self.fails(snax_cfg.CfgKeyError, "groups[0].csrs[2].width", "every CSR has a width")
        self.acc = acc_json(VECADD)
        self.acc["accelerators"][0]["groups"][0]["csrs"][3]["width"] = 33
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[3].width", "must be 1 to 32 bits")
        self.acc = acc_json(VECADD)
        self.acc["accelerators"][0]["groups"][0]["csrs"][0]["access"] = "wo"
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[0].access", "rw or ro")

    def test_csr_counts(self):
        self.rw = 3
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[0].snax_num_rw_csr",
                   "accelerator acc has 2 read-write")
        self.rw, self.ro = 2, 1
        self.fails(snax_cfg.CfgSlotError, "snax_num_ro_csr", "2 read-only")

    def test_datapath(self):
        self.unit()["datapath"] = "Gemm"
        self.fails(snax_cfg.CfgTargetError, "units[0].datapath", "not a datapath SnaxGroup models")

    def test_links_and_units(self):
        """A link has its four keys; a group's units are connected by its links (gen.group);
        a unit name is the accelerator's once."""
        self.acc["accelerators"][0]["groups"][0]["links"] = [
            {"name": "l", "from": "acc.out", "to": "acc.a"}]
        self.fails(snax_cfg.CfgKeyError, "groups[0].links[0].depth", "missing")
        self.acc = acc_json(VECADD)
        self.acc["accelerators"][0]["groups"][0]["units"].append(copy.deepcopy(self.unit()))
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators", "unit 'acc' twice")
        self.acc["accelerators"][0]["groups"][0]["units"][1]["name"] = "acc2"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups", "gen.group")

    def test_ports_name_the_movers(self):
        self.acc["accelerators"][0]["inputs"] = ["acc.a"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs",
                   "gen.outer")
        self.acc["accelerators"][0]["inputs"] = ["acc.a", "acc.c"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[1]",
                   "names no port")
        self.acc["accelerators"][0]["inputs"] = ["acc.a", "acc.a"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[1]", "twice")
        self.acc = acc_json(VECADD)
        self.streamer["data_reader_params"] = {k: v[:1] for k, v in
                                               STREAMER["data_reader_params"].items()}
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs",
                   "set acc's streamer has 1 data_reader_params")

    def test_words_per_beat(self):
        """int32 a at 4 lanes is 2 words: its reader must have num_channel 2."""
        self.unit()["ports"]["a"]["dtype"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[0]",
                   "acc.a: lanes 4 x 32 bits is 2 64-bit words per beat, but set acc's "
                   "data_reader_params[0] has num_channel 4")
        self.streamer["data_reader_params"]["num_channel"][0] = 2
        self.streamer["data_reader_params"]["spatial_bounds"][0] = [2]
        self.load()  # int32 with int64: int64, as opType says
        self.unit()["ports"]["a"]["lanes"] = 3
        self.fails(snax_cfg.CfgTargetError, "snax_datapath_cfg.accelerators[0].inputs",
                   "one lane count")

    def test_op_type(self):
        self.unit()["opType"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups",
                   "opType int32, but its inputs' result type is int64")
        del self.unit()["opType"]
        self.fails(snax_cfg.CfgKeyError, "units[0].opType", "missing")
        self.acc = acc_json(VECADD)
        self.unit()["ports"]["b"]["dtype"] = "uint64"
        self.fails(snax_cfg.CfgTypeError, "snax_datapath_cfg.accelerators[0].groups",
                   "int64 with uint64 has no integer result type")

    def test_k(self):
        """k, SimdLanes' constant at one stream: an int of its opType; with it the unit has one
        input; no other datapath has one."""
        self.unit()["params"]["k"] = 0
        self.fails(snax_cfg.CfgTargetError, "snax_datapath_cfg.accelerators[0].inputs",
                   "2 inputs and 1 outputs; SimdLanes takes 1 and 1")
        self.unit()["params"]["k"] = 2 ** 63
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k", "does not fit the opType int64")
        self.unit()["params"]["k"] = "0"
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k", "must be")
        self.acc = acc_json(VECADD)
        self.unit()["datapath"] = "TreeAccumulate"
        self.unit()["params"]["k"] = 0
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k", "a TreeAccumulate unit has no")

    def test_axpby_and_scalars(self):
        """axpby takes k1, baked or from its CSR; k1 and k2 are axpby's; a scalar is a SimdLanes
        slot not baked, at the opType, and its CSRs (K1, or K1_LO and K1_HI, pin k1) follow
        the JOB_BEATS."""
        self.unit()["params"]["op"] = "axpby"
        self.fails(snax_cfg.CfgKeyError, "units[0].params.k1", "missing: axpby takes k1")
        self.unit()["scalars"] = {"k1": "int64"}
        self.fails(snax_cfg.CfgSlotError, "units[0].csrs",
                   "the scalars {'k1': 'int64'} are the CSRs (name, width, pin) "
                   "[('K1_LO', 32, 'k1'), ('K1_HI', 32, 'k1')] after the JOB_BEATS")
        self.unit()["scalars"] = {"k1": "int32"}
        self.fails(snax_cfg.CfgTypeError, "units[0].scalars.k1", "a scalar is at the opType, int64")
        self.unit()["params"]["k1"] = 2
        self.unit()["scalars"] = {"k1": "int64"}
        self.fails(snax_cfg.CfgTypeError, "units[0].scalars.k1", "not a slot of SimdLanes")
        self.acc = acc_json(VECADD)
        self.unit()["params"]["k2"] = 2
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k2", "k2 is axpby's, not add's")
        self.acc = acc_json(VECADD)
        self.unit()["params"]["op"] = "axpby"
        self.unit()["params"]["k1"] = 2 ** 63
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k1", "does not fit the opType int64")
        self.acc = acc_json(VECADD)
        self.unit()["csrs"] = [{"name": "K1", "access": "rw", "offset": 2, "width": 32}]
        self.fails(snax_cfg.CfgTargetError, "units[0].csrs[0]", "K1 (rw): the unit CSRs modelled")
        self.acc = acc_json(VECADD)
        self.unit()["datapath"] = "TreeAccumulate"
        self.unit()["scalars"] = {"k": "int64"}
        self.fails(snax_cfg.CfgTypeError, "units[0].scalars.k", "not a slot of SimdLanes")

    def test_dtype_and_op(self):
        self.unit()["ports"]["out"]["dtype"] = "float64"
        self.fails(snax_cfg.CfgTypeError, "units[0].ports.out.dtype", "not a NumPy integer type")
        self.acc = acc_json(VECADD)
        self.unit()["params"]["op"] = "nand"
        self.fails(snax_cfg.CfgTypeError, "units[0].params.op", "not an op")
        del self.unit()["params"]["op"]
        self.fails(snax_cfg.CfgKeyError, "units[0].params.op", "needs an op")

    def test_port_dir(self):
        del self.unit()["ports"]["a"]["dir"]
        self.fails(snax_cfg.CfgKeyError, "units[0].ports.a.dir")
        self.acc = acc_json(VECADD)
        self.unit()["ports"]["a"]["dir"] = "inout"
        self.fails(snax_cfg.CfgTypeError, "units[0].ports.a.dir", "must be in or out")

    def test_unit_csrs(self):
        """SimdLanes has no JOB_BEATS, TreeAccumulate one; other unit CSRs are not
        modelled."""
        self.unit()["csrs"] = [{"name": "JOB_BEATS", "access": "rw", "offset": 2, "width": 32}]
        self.acc["accelerators"][0]["groups"][0]["csrs"][2]["offset"] = 3
        self.acc["accelerators"][0]["groups"][0]["csrs"][3]["offset"] = 4
        self.rw, self.ro = 3, 2
        self.fails(snax_cfg.CfgSlotError, "units[0].csrs", "any other unit none")
        self.unit()["csrs"][0]["name"] = "SCALE"
        self.fails(snax_cfg.CfgTargetError, "units[0].csrs[0]", "SCALE (rw)")

    def test_fold(self):
        """vsum_tree_i32's accelerator: a fold's output one word, whatever its lanes' type."""
        self.acc = acc_json(accelerator("vsum_tree_i32", fold("acc", 0, "int32", 4), between=1))
        self.streamer = {
            "data_reader_params": {"spatial_bounds": [[2]], "temporal_dim": [1],
                                   "num_channel": [2], "fifo_depth": [8]},
            "data_writer_params": {"spatial_bounds": [[2]], "temporal_dim": [1],
                                   "num_channel": [2], "fifo_depth": [8]}}
        self.rw = 3
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].outputs[0]",
                   "a fold's output is one 64-bit word per beat, but set acc's "
                   "data_writer_params[0] has num_channel 2")
        self.streamer["data_writer_params"].update(spatial_bounds=[[1]], num_channel=[1])
        self.assertEqual(self.load().description.groups[0].units[0].ports["a"].lanes, 4)
        self.unit()["opType"] = "int64"
        self.fails(snax_cfg.CfgTypeError, "units[0].opType", "a TreeAccumulate unit has none")
        del self.unit()["opType"]
        self.unit()["params"]["op"] = "max"
        self.fails(snax_cfg.CfgTargetError, "units[0].params.op", "TreeAccumulate adds")
        del self.unit()["params"]["op"]
        self.fails(snax_cfg.CfgKeyError, "units[0].params.op", "TreeAccumulate needs an op")
        self.unit()["params"]["op"] = "add"
        self.unit()["csrs"] = []
        self.fails(snax_cfg.CfgSlotError, "units[0].csrs", "a fold without params.T has JOB_BEATS")


class LinkedGroup(unittest.TestCase):
    """dot 4: one group of a Mac wired into a TreeAccumulate, read
    as written; each of snax-forge's link checks refuses its case with its code."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.acc = acc_json(DOT4)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        path = write_design(self.dir, self.acc, DOT4_STREAMER, 3, 2)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot

    def fails(self, kind, text):
        with self.assertRaises(kind) as ctx:
            self.load()
        self.assertIn(text, ctx.exception.why)

    def test_dot4_reads_as_written(self):
        acc = self.load().description
        self.assertEqual(acc, DOT4)
        (group,) = acc.groups
        self.assertEqual([u.span for u in group.units], [1, 1])
        self.assertEqual(group.units[1].params["T"], 1)
        self.assertEqual(group.links, [Link("out_partial", "mac.out", "sum.a", 0)])
        self.assertEqual(group.rw, ["START", "JOBS", "JOB_BEATS"])

    def link(self, **kw):
        self.acc["accelerators"][0]["groups"][0]["links"][0].update(kw)

    def test_gen_link(self):
        self.link(to="mac.a")  # out to an in port, but mac.a is outer: also on inputs
        self.fails(snax_cfg.CfgSlotError, "gen.")
        self.acc = acc_json(DOT4)
        self.link(**{"from": "sum.a", "to": "mac.a"})  # in to in
        self.fails(snax_cfg.CfgSlotError, "gen.link:")
        self.acc = acc_json(DOT4)
        # lanes differ
        self.acc["accelerators"][0]["groups"][0]["units"][1]["ports"]["a"]["lanes"] = 2
        self.fails(snax_cfg.CfgSlotError, "gen.link:")
        self.acc = acc_json(DOT4)
        self.link(depth=-1)
        self.fails(snax_cfg.CfgSlotError, "gen.link:")

    def test_gen_link_port(self):
        links = self.acc["accelerators"][0]["groups"][0]["links"]
        links.append(dict(links[0], name="again", depth=1))
        self.fails(snax_cfg.CfgSlotError, "gen.link_port:")

    def test_gen_outer(self):
        self.acc["accelerators"][0]["inputs"] = ["mac.a", "mac.b", "sum.a"]
        self.fails(snax_cfg.CfgSlotError, "gen.outer:")
        self.acc = acc_json(DOT4)
        self.acc["accelerators"][0]["inputs"] = ["mac.b", "mac.a"]
        self.fails(snax_cfg.CfgSlotError, "gen.outer:")

    def test_gen_group(self):
        self.acc["accelerators"][0]["groups"][0]["links"] = []
        self.acc["accelerators"][0]["inputs"] = ["mac.a", "mac.b", "sum.a"]
        self.acc["accelerators"][0]["outputs"] = ["mac.out", "sum.out"]
        self.fails(snax_cfg.CfgSlotError, "gen.group:")

    def test_gen_chain(self):
        """The link mac -> sum over the units in the order sum, mac: not a chain in unit order,
        snax-forge's gen.chain in its words."""
        self.acc["accelerators"][0]["groups"][0]["units"].reverse()
        self.fails(snax_cfg.CfgTargetError,
                   "gen.chain: accelerator dot: group dot's links [('mac', 'sum')] over its units "
                   "['sum', 'mac']: a group is one chain (no fork or join)")

    def test_gen_span(self):
        """A SerialAccumulate of 4 lanes (span 4) fed by the streamer: snax-forge's gen.span in
        its words."""
        serial = Unit("acc", "accumulate", "SerialAccumulate",
                      {"a": Port("in", "int64", 4, "in"), "out": Port("out", "int64", 1, "out")},
                      None, {}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)], 4)
        streamer = {
            "data_reader_params": {"spatial_bounds": [[4]], "temporal_dim": [1],
                                   "num_channel": [4], "fifo_depth": [8]},
            "data_writer_params": {"spatial_bounds": [[1]], "temporal_dim": [1],
                                   "num_channel": [1], "fifo_depth": [8]},
        }
        acc = acc_json(accelerator("serial", serial, between=1))
        with self.assertRaises(snax_cfg.CfgTargetError) as ctx:
            snax_cfg.load(write_design(self.dir, acc, streamer, 3, 2))
        self.assertIn("gen.span: accelerator acc: unit acc (span 4) reads ['a'] from the streamer: "
                      "a unit with span > 1 reads from a link", ctx.exception.why)

    def test_a_datapath_is_the_registrys(self):
        self.acc["accelerators"][0]["groups"][0]["units"][0]["datapath"] = "LinkBuffer"
        self.fails(snax_cfg.CfgTargetError, "not a datapath SnaxGroup models")

    def test_timing_is_the_datapaths(self):
        self.acc["accelerators"][0]["groups"][0]["units"][1]["timing"]["span"] = 4
        self.fails(snax_cfg.CfgTargetError, "gen.timing:")


# matvec_seed's sum: a TreeAccumulate over 4 lanes with a seed port,
# one int64 lane read once per job, its one accelerator's readers sum.a and sum.seed
def seeded(datapath: str = "TreeAccumulate", seed: Port = Port("seed", "int64", 1, "in"),
           lanes: int = 4, span: int = 1, name: str = "acc") -> Unit:
    return Unit(name, "accumulate", datapath,
                {"a": Port("in", "int64", lanes, "in"), "seed": seed,
                 "out": Port("out", "int64", 1, "out")}, None,
                {"op": "add"} if datapath == "TreeAccumulate" else {}, 1, 1,
                [Csr("JOB_BEATS", "rw", 2, 32)], span)


SEEDED_STREAMER = streamer([4, 1], [1])


class Seed(unittest.TestCase):
    """A fold's seed port: read on TreeAccumulate and
    SerialAccumulate, one lane at the output's dtype, the last in port, from the streamer
    (also at span > 1); anything else is gen.seed at the port."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, acc, streamer=SEEDED_STREAMER):
        (slot,) = snax_cfg.load(write_design(self.dir, acc, streamer, 3, 2)).cores[0].accelerators
        return slot.description

    def refused(self, acc, text, streamer=SEEDED_STREAMER):
        with self.assertRaises(snax_cfg.CfgTargetError) as ctx:
            self.load(acc, streamer)
        self.assertIn(text, ctx.exception.why)
        return ctx.exception

    def test_a_seeded_fold_reads(self):
        desc = accelerator("matvec_seed", seeded(), between=1)
        got = self.load(acc_json(desc))
        self.assertEqual(got, desc)
        (unit,) = got.groups[0].units
        self.assertTrue(unit.seeded)
        self.assertEqual(got.accelerators[0].inputs, ["acc.a", "acc.seed"])
        self.assertFalse(fold("acc", 0).seeded)

    def test_the_seed_port_is_checked(self):
        cases = [
            (Port("seed", "int64", 2, "in"), "gen.seed: 2 lanes, a seed is 1"),
            (Port("seed", "int32", 1, "in"), "gen.seed: int32, a seed is its output's int64"),
        ]
        for port, text in cases:
            e = self.refused(acc_json(accelerator("matvec_seed", seeded(seed=port), between=1)),
                             text)
            self.assertIn("ports.seed", e.path)
        mac = Unit("acc", "mac", "Mac", {"a": Port("a", "int64", 4, "in"),
                                          "b": Port("b", "int64", 4, "in"),
                                          "seed": Port("seed", "int64", 1, "in"),
                                          "out": Port("out", "int64", 4, "out")}, "int64",
                   {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)])
        self.refused(acc_json(accelerator("mac_seed", mac, between=1)),
                     "gen.seed: Mac takes no seed (TreeAccumulate and SerialAccumulate do)",
                     streamer([4, 4, 1], [4]))
        first = acc_json(accelerator("matvec_seed", seeded(), between=1))
        ports = first["accelerators"][0]["groups"][0]["units"][0]["ports"]
        first["accelerators"][0]["groups"][0]["units"][0]["ports"] = {
            "seed": ports["seed"], "a": ports["a"], "out": ports["out"]}
        first["accelerators"][0]["inputs"] = ["acc.seed", "acc.a"]
        self.refused(first, "gen.seed: the last in port", streamer([1, 4], [1]))

    def test_a_serial_fold_takes_its_seed_from_the_streamer(self):
        """A SerialAccumulate of span 4 seeded: its a from a link (a Mac's), its seed from the
        streamer; with its a from the streamer it is gen.span still."""
        serial = replace(seeded("SerialAccumulate", span=4, name="sum"), csrs=[], params={"T": 1})
        mac = DOT4.accelerators[0].groups[0].units[0]
        desc = description("dot_seed", Accelerator(
            "dot", ["mac.a", "mac.b", "sum.seed"], ["sum.out"],
            [Group("dot", group_csrs(0, 1), [mac, serial],
                   [Link("out_partial", "mac.out", "sum.a", 0)])]))
        got = self.load(acc_json(desc), streamer([4, 4, 1], [1]))
        self.assertTrue(got.groups[0].units[1].seeded)
        alone = acc_json(accelerator("serial_seed", seeded("SerialAccumulate", span=4),
                                     between=1))
        self.refused(alone, "gen.span: accelerator acc: unit acc (span 4) reads ['a'] from the "
                     "streamer")


class Dot1(unittest.TestCase):
    """dot 1: two accelerators vmul and vsum in two streamer
    sets; dot_1_enc, the two as one accelerator dot of two groups, one set."""

    def test_dot_1_two_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            (slot,) = snax_cfg.load(dot1_cluster(Path(tmp))).cores[0].accelerators
        self.assertEqual(slot.description, DOT1)
        self.assertEqual([(x.name, x.streamer, x.num_rw_csr, x.num_ro_csr) for x in slot.sets],
                         [("vmul", VMUL_STREAMER, 2, 2), ("vsum", VSUM_STREAMER, 3, 2)])
        self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports), (5, 4, 17))
        # The offsets over both accelerators, as the shell sees them
        self.assertEqual([[(c.name, c.offset) for c in a.csrs] for a in DOT1.accelerators],
                         [[("START", 0), ("JOBS", 1), ("STATUS", 2), ("BUSY_COUNTER", 3)],
                          [("START", 4), ("JOBS", 5), ("JOB_BEATS", 6), ("STATUS", 7),
                           ("BUSY_COUNTER", 8)]])
        self.assertEqual(VSUM.ports_of("vsum", VSUM.inputs), [(0, "a")])

    def test_dot_1_enc_one_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            (slot,) = snax_cfg.load(dot_cluster(Path(tmp))).cores[0].accelerators
        acc = slot.description
        self.assertEqual(acc, DOT)
        self.assertEqual([x.name for x in slot.sets], ["dot"])
        self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports), (5, 4, 17))
        (dot,) = acc.accelerators
        self.assertEqual([g.rw for g in dot.groups], [["START", "JOBS"],
                                                      ["START", "JOBS", "JOB_BEATS"]])
        self.assertEqual(dot.ports_of("vsum", dot.inputs), [(2, "a")])
        self.assertEqual(dot.ports_of("vsum", dot.outputs), [(1, "out")])

    def test_forge(self):
        """forge/dot_1/ and dot_1_enc/, snax-forge's: the same, their design points named."""
        for design, want, sets in (("dot_1", DOT1, ["vmul", "vsum"]),
                                   ("dot_1_enc", DOT, ["dot"])):
            with self.subTest(design):
                (slot,) = snax_cfg.load(FORGE / design / "snax_forge.hjson").cores[0].accelerators
                self.assertEqual(slot.description, want)
                self.assertEqual([x.name for x in slot.sets], sets)
                self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports),
                                 (5, 4, 17))


class Shared(unittest.TestCase):
    """A set whose groups share its movers: movers and port_mux read, and
    each thing wrong in them a named error at its key."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.acc = acc_json(DOT_SHARED)
        self.streamer = copy.deepcopy(DOT_SHARED_STREAMER)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        path = write_design(self.dir, self.acc, self.streamer, 6, 4)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot

    def fails(self, path_part, why_part):
        with self.assertRaises(snax_cfg.SnaxCfgError) as ctx:
            self.load()
        self.assertIn(path_part, ctx.exception.path)
        self.assertIn(why_part, ctx.exception.why)

    def mover(self, k):
        return self.acc["accelerators"][0]["movers"][k]

    def test_dot_1_shared(self):
        slot = self.load()
        self.assertEqual(slot.description, DOT_SHARED)
        (dot,) = slot.description.accelerators
        # PORT_MUX_SEL last: 6 R/W (vmul's 2, vsum's 3, the select), 4 R/O
        self.assertEqual([c.name for c in dot.csrs][-2:], ["BUSY_COUNTER", "PORT_MUX_SEL"])
        self.assertEqual((dot.num_rw, dot.num_ro), (6, 4))
        # 12 channels where dot_1_enc has 17: the movers 4 + 4 + 4
        self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports), (6, 4, 12))
        self.assertEqual(snax_cfg.template_movers(DOT_SHARED_STREAMER)[-1],
                         {"name": "writer0", "is_reader": False, "num_channel": 4,
                          "configurable_channel": True})

    def test_movers_without_port_mux(self):
        del self.acc["accelerators"][0]["port_mux"]
        self.fails("accelerators[0].port_mux", "both movers and port_mux")

    def test_port_mux_misses_a_group(self):
        self.acc["accelerators"][0]["port_mux"]["groups"] = ["vmul"]
        self.fails("port_mux.groups", "each once")

    def test_port_mux_sel_is_rw(self):
        self.acc["accelerators"][0]["port_mux"]["csr"]["access"] = "ro"
        self.fails("port_mux.csr", "must be PORT_MUX_SEL (rw)")

    def test_port_mux_sel_offset_contiguous(self):
        self.acc["accelerators"][0]["port_mux"]["csr"]["offset"] = 10
        self.fails("accelerators", "the port mux's PORT_MUX_SEL has offset 10")

    def test_user_not_an_outer_port_of_its_role(self):
        self.mover(0)["users"][1]["port"] = "vsum.out"
        self.fails("movers[0].users[1]", "the ports reader0 can serve")

    def test_user_of_another_group(self):
        self.mover(1)["users"][0]["group"] = "vsum"
        self.fails("movers[1].users[0]", "is not a port of group vsum")

    def test_two_ports_of_one_group(self):
        self.mover(0)["users"][1] = {"group": "vmul", "port": "vmul.b", "num_channel": 4}
        self.fails("movers[0].users[1]", "a second port of group vmul")

    def test_narrow_user_on_an_unmasked_mover(self):
        self.mover(2)["masked"] = False
        self.fails("movers[2].users[1]", "not masked")

    def test_masked_against_the_template(self):
        del self.streamer["data_writer_params"]["configurable_channel"]
        self.fails("movers[2]", "masked True, but its configurable_channel is False")

    def test_movers_against_the_template(self):
        self.streamer = streamer([4, 4, 4], [4])
        self.fails("movers", "has the movers ['reader0', 'reader1', 'reader2', 'writer0']")

    def test_a_port_on_no_mover(self):
        self.mover(1)["users"] = []
        self.fails("accelerators[0].movers", "vmul.b is on no mover")

    def test_user_words_per_beat(self):
        self.mover(2)["users"][1]["num_channel"] = 2
        self.fails("movers[2].users[1]", "a fold's output is one 64-bit word")


class Sets(unittest.TestCase):
    """The streamer sets against accelerator.json: each mismatch refused at its key, with
    snax_cluster's rules on the sets (snaxgen's streamer_sets) beside."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        dot1_cluster(self.dir)
        self.d = json.loads((self.dir / "snax_forge.hjson").read_text())
        self.acc = acc_json(DOT1)

    def tearDown(self):
        self.tmp.cleanup()

    def slot(self):
        return self.d["snax_forge_core_template"]["snax_acc_cfg"][0]

    def load(self):
        (self.dir / "accelerator.json").write_text(json.dumps(self.acc))
        path = self.dir / "cluster.hjson"
        path.write_text(json.dumps(self.d))
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot

    def fails(self, error, path_part, why_part):
        with self.assertRaises(error) as ctx:
            self.load()
        self.assertIn(path_part, ctx.exception.path)
        self.assertIn(why_part, ctx.exception.why)

    def test_reads(self):
        self.assertEqual([x.at for x in self.load().sets],
                         ["snax_streamer_sets[0]", "snax_streamer_sets[1]"])

    def test_names_and_order_are_the_accelerators(self):
        sets = self.slot()["snax_streamer_sets"]
        sets.reverse()
        self.fails(snax_cfg.CfgSlotError, "snax_acc_cfg[0].snax_streamer_sets",
                   "the sets ['vsum', 'vmul'], but accelerator.json's accelerators are "
                   "['vmul', 'vsum']: one set per accelerator, named after it, in its order")
        sets.reverse()
        sets[1]["name"] = "total"
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets", "the sets ['vmul', 'total']")
        del sets[1]
        self.slot().update(snax_tcdm_ports=12, sparse_interconnect_config=[[12, 1]])
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets", "the sets ['vmul']")

    def test_counts_are_the_sets_groups(self):
        self.slot()["snax_streamer_sets"][1]["snax_num_rw_csr"] = 2
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[1].snax_num_rw_csr",
                   "2, but accelerator vsum has 3 read-write CSRs")
        self.slot()["snax_streamer_sets"][1]["snax_num_rw_csr"] = 3
        self.slot()["snax_streamer_sets"][0]["snax_num_ro_csr"] = 4
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[0].snax_num_ro_csr",
                   "4, but accelerator vmul has 2 read-only CSRs")

    def test_ports_are_the_sets_movers(self):
        """vsum.a moved into vmul: vmul has 3 inputs for its set's 2 readers."""
        vmul, vsum = self.acc["accelerators"]
        vmul["inputs"].append("vsum.a")
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[2]",
                   "names no port of accelerator vmul's units")
        vmul["inputs"].pop()
        (self.dir / "streamer_vsum.hjson").write_text(json.dumps(streamer([4], [4])))
        self.slot()["snax_tcdm_ports"] = 20
        self.slot()["sparse_interconnect_config"] = [[20, 1]]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[1].outputs[0]",
                   "a fold's output is one 64-bit word per beat, but set vsum's "
                   "data_writer_params[0] has num_channel 4")
        (self.dir / "streamer_vsum.hjson").write_text(json.dumps(streamer([4, 4], [1])))
        self.slot()["snax_tcdm_ports"] = 21
        self.slot()["sparse_interconnect_config"] = [[21, 1]]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[1].inputs",
                   "['vsum.a'], but set vsum's streamer has 2 data_reader_params")

    def test_channels_over_all_sets(self):
        self.slot()["snax_tcdm_ports"] = 12
        self.fails(snax_cfg.CfgSlotError, "snax_tcdm_ports", "12, but the streamers have 17 "
                   "channels (num_channel over their movers, set by set {'vmul': 12, 'vsum': 5})")
        self.slot()["snax_tcdm_ports"] = 17
        self.slot()["sparse_interconnect_config"] = [[12, 1]]
        self.fails(snax_cfg.CfgSlotError, "sparse_interconnect_config",
                   "widths add up to 12, not snax_tcdm_ports 17")
        self.slot()["sparse_interconnect_config"] = [[12, 1], [5, 1]]
        self.assertEqual(self.load().sparse_config, [[12, 1], [5, 1]])

    def test_snaxgens_rules(self):
        """Both forms, no set, no csr manager off, a name twice or not an identifier."""
        slot = self.slot()
        slot["snax_streamer_cfg"] = {"$ref": "streamer_vmul.hjson"}
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets", "both snax_streamer_cfg and "
                   "snax_streamer_sets; give one")
        del slot["snax_streamer_cfg"]
        sets = slot["snax_streamer_sets"]
        slot["snax_streamer_sets"] = []
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets", "no set")
        slot["snax_streamer_sets"] = sets
        slot["snax_disable_csr_manager"] = False
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets", "snax_disable_csr_manager")
        slot["snax_disable_csr_manager"] = True
        sets[1]["name"] = "vmul"
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[1].name", "set 'vmul' twice")
        sets[1]["name"] = "v-sum"
        self.fails(snax_cfg.CfgTypeError, "snax_streamer_sets[1].name", "not a C identifier")

    def test_the_form_before_d157_is_refused(self):
        """accelerator.json with one accelerator's keys at the top."""
        flat = self.acc["accelerators"][0]
        self.acc = {"design_point": "x", "tag": "y", **flat}
        self.fails(snax_cfg.CfgTypeError, "snax_datapath_cfg.name",
                   "before streamer sets")

    def test_names_once(self):
        self.acc["accelerators"][1]["groups"][0]["name"] = "vmul"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators",
                   "group 'vmul' twice")
        self.acc = acc_json(DOT1)
        self.acc["accelerators"][1]["name"] = "vmul"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators",
                   "accelerator 'vmul' twice")

    def test_offsets_run_over_the_accelerators(self):
        """vsum's from 0, as if it were alone: refused, the shell sees them contiguous."""
        for g in self.acc["accelerators"][1]["groups"]:
            for c in g["csrs"] + [c for u in g["units"] for c in u["csrs"]]:
                c["offset"] -= 4
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators",
                   "group vsum's START has offset 0, but is CSR 4 in CSR order")


class OldForm(unittest.TestCase):
    """A slot with snax_streamer_cfg and its own CSR counts in place of snax_streamer_sets is
    one set named after the slot, as snaxgen reads it."""

    def write(self, folder, acc, rw=2, ro=2):
        d = hjson.loads(CLUSTER.read_text())
        slot = d["snax_forge_core_template"]["snax_acc_cfg"][0]
        del slot["snax_streamer_sets"]
        slot.update(snax_streamer_cfg=STREAMER, snax_num_rw_csr=rw, snax_num_ro_csr=ro)
        (folder / "accelerator.json").write_text(json.dumps(acc))
        path = folder / "snax_forge.hjson"
        path.write_text(json.dumps(d))
        return path

    def test_one_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            (slot,) = snax_cfg.load(self.write(Path(tmp), acc_json(VECADD))).cores[0].accelerators
        (one,) = slot.sets
        self.assertEqual((one.name, one.streamer, one.num_rw_csr, one.num_ro_csr, one.at),
                         ("snax_forge_vecadd", STREAMER, 2, 2, ""))
        self.assertEqual(slot.description, VECADD)

    def test_its_counts_and_one_accelerator(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
                snax_cfg.load(self.write(Path(tmp), acc_json(VECADD), rw=3))
            self.assertEqual(ctx.exception.path,
                             "cluster.hives[0].cores[0].snax_acc_cfg[0].snax_num_rw_csr")
            with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
                snax_cfg.load(self.write(Path(tmp), acc_json(DOT1)))
            self.assertIn("one streamer, but accelerator.json has the accelerators "
                          "['vmul', 'vsum']: give snax_streamer_sets", ctx.exception.why)


if __name__ == "__main__":
    unittest.main()
