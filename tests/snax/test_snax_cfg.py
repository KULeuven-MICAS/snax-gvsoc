# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_cfg.py. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Reads sw/cfg/snitch_cluster.hjson and forge/'s fixtures, then broken copies
of forge/vecadd/'s cluster (its streamer file and accelerator.json inlined,
written as JSON into a temporary folder), broken accelerator.json files
beside it, and a hand-written two-group accelerator (dot 1, snax-forge C§17's
table: groups mul and sum). snax_cluster's copy in sw/cfg/snax_forge/ is never
read (snax-forge D126).
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
from snax_cfg import Accelerator, Csr, Group, Link, Port, Unit  # noqa: E402

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
    return [Csr("START", "rw", base, 32), Csr("JOBS", "rw", base + 1, 32),
            Csr("STATUS", "ro", base + 2 + between), Csr("COUNTER", "ro", base + 3 + between)]


def elementwise(name: str, op: str, dtype: str = "int64", brm: str = None) -> Unit:
    return Unit(name, brm or f"elementwise_{op}", "ElementwiseLanes",
                {p: Port(p, dtype, 4, "out" if p == "out" else "in") for p in ("a", "b", "out")},
                dtype, {"op": op}, 0, 1, [])


def fold(name: str, base: int, in_dtype: str = "int64", lanes: int = 1) -> Unit:
    return Unit(name, "accumulate", "TreeAccumulate",
                {"a": Port("in", in_dtype, lanes, "in"), "out": Port("out", "int64", 1, "out")}, None,
                {"op": "add"},
                1, 1, [Csr("JOB_BEATS", "rw", base + 2, 32)])


def accelerator(design: str, unit: Unit, between: int = 0) -> Accelerator:
    """A design's accelerator of one group of one unit, named acc, from forge/."""
    ins = [k for k in unit.ports if k != "out"]
    return Accelerator("acc", f"out/design/{design}/design_point.json", "snax_forge",
                       [f"acc.{k}" for k in ins], ["acc.out"],
                       [Group("acc", group_csrs(0, between), [unit], [])])


# forge/vecadd/'s accelerator.json, parsed
VECADD = accelerator("vecadd", elementwise("acc", "add"))

MISA_RV32IMA = (1 << 30) | (1 << 12) | (1 << 8) | (1 << 0)


def cluster():
    """CLUSTER, parsed, with its slot's streamer file and accelerator.json in place of their
    $refs, so that a copy reads on its own."""
    d = hjson.loads(CLUSTER.read_text())
    slot = d["snax_forge_core_template"]["snax_acc_cfg"][0]
    for key in ("snax_streamer_cfg", "snax_datapath_cfg"):
        slot[key] = json.loads(json.dumps(hjson.loads((CLUSTER.parent / slot[key]["$ref"])
                                                      .read_text())))
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
    snax_forge set for the design, its accelerator.json read."""

    def slot(self, design):
        cfg = snax_cfg.load(FORGE / design / "snax_forge.hjson")
        self.assertEqual(cfg.name, "snax_forge_cluster")
        self.assertTrue(cfg.tcdm.sparse_interconnect)
        (slot,) = cfg.cores[0].accelerators
        self.assertEqual(slot.name, "snax_forge")
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
        compute, dma = cfg.cores
        self.assertEqual((compute.isa, compute.xdma, compute.num_int_outstanding_loads),
                         ("rv32ima", False, 1))
        self.assertEqual((dma.isa, dma.xdma, dma.accelerators), ("rv32ima", True, []))
        self.assertEqual(compute.misa, MISA_RV32IMA)
        slot = self.slot("vecadd")
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (12, 2, 2))
        self.assertEqual((slot.narrow_tcdm_ports, slot.wide_tcdm_ports, slot.sparse_config),
                         (None, None, [[12, 1]]))
        self.assertEqual(slot.streamer, STREAMER)
        self.assertEqual(slot.accelerator, VECADD)

    def test_vecmul(self):
        slot = self.slot("vecmul")
        self.assertEqual(slot.streamer, STREAMER)
        self.assertEqual(slot.accelerator,
                         accelerator("vecmul", elementwise("acc", "mul")))

    def test_vsum_tree_i32(self):
        """A fold: JOB_BEATS between JOBS and STATUS, int32 lanes into an int64 sum."""
        slot = self.slot("vsum_tree_i32")
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (3, 3, 2))
        self.assertEqual(slot.accelerator,
                         accelerator("vsum_tree_i32", fold("acc", 0, "int32", 4), between=1))
        self.assertEqual([c.name for c in slot.accelerator.csrs],
                         ["START", "JOBS", "JOB_BEATS", "STATUS", "COUNTER"])
        self.assertEqual(slot.accelerator.groups[0].rw, ["START", "JOBS", "JOB_BEATS"])

    def test_every_fixture_reads(self):
        for folder in sorted(p for p in FORGE.iterdir() if p.is_dir()):
            with self.subTest(folder.name):
                slot = self.slot(folder.name)
                self.assertEqual(slot.accelerator.design_point,
                                 f"out/design/{folder.name}/design_point.json")
                # STATUS and COUNTER per group
                self.assertEqual(slot.num_ro_csr, 2 * len(slot.accelerator.groups))


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

    def test_parse(self):
        self.fails(snax_cfg.CfgParseError, "{ cluster: ", "")
        self.fails(snax_cfg.CfgParseError, "[1, 2]", "", "must be an object")
        with self.assertRaises(snax_cfg.CfgParseError):
            snax_cfg.load(self.dir / "none.hjson")

    def test_ref_missing_key(self):
        d = cluster()
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/no_such_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_acc_cfg[0].snax_streamer_cfg",
                   "no 'no_such_template'")

    def test_ref_missing_file(self):
        d = cluster()
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "acc.hjson#/snax_streamer_cfg"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")

    def test_ref_malformed(self):
        d = cluster()
        d["streamer_template"] = self.slot(d)["snax_streamer_cfg"]
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/streamer_template", "x": 1}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "is not")
        # A key without #/ is a whole file's name: no such file
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "must start with /")

    def test_ref_cycle(self):
        d = cluster()
        d["loop"] = {"a": {"$ref": "#/loop"}}
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/loop"}
        self.fails(snax_cfg.CfgRefError, d, "loop", "refers to itself")

    def test_missing_key(self):
        d = cluster()
        del d["cluster"]["tcdm"]["banks"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.tcdm.banks", "missing")
        d = cluster()
        del self.slot(d)["snax_num_rw_csr"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.hives[0].cores[0].snax_acc_cfg[0]"
                   ".snax_num_rw_csr", "missing")

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
        d["cluster"]["hives"][0]["cores"][1] = "dma"
        self.fails(snax_cfg.CfgTypeError, d, "cluster.hives[0].cores[1]", "an object")

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
        self.slot(d)["snax_streamer_cfg"]["data_reader_writer_params"] = {
            "spatial_bounds": [[4]], "temporal_dim": [1], "num_channel": [4], "fifo_depth": [8]}
        self.fails(snax_cfg.CfgTargetError, d, "snax_streamer_cfg.data_reader_writer_params",
                   "not modelled")


def acc_json(acc: Accelerator) -> dict:
    """An Accelerator as accelerator.json writes it (snax-forge's gen/accelerator.py)."""
    def csr(c):
        d = {"name": c.name, "access": c.access, "offset": c.offset}
        if c.width is not None:
            d["width"] = c.width
        return d

    def unit(u):
        d = {"name": u.name, "brm": u.brm, "datapath": u.datapath,
             "ports": {k: {"port": p.port, "dir": p.dir,
                           "dtype": p.dtype, "lanes": p.lanes}
                       for k, p in u.ports.items()}}
        if u.op_type is not None:
            d["opType"] = u.op_type
        d.update({"params": dict(u.params),
                  "timing": {"latency": u.latency, "ii": u.ii, "span": u.span},
                  "csrs": [csr(c) for c in u.csrs]})
        return d

    def link(k):
        return {"name": k.name, "from": k.from_, "to": k.to, "depth": k.depth}

    return {"name": acc.name, "design_point": acc.design_point, "tag": acc.tag,
            "inputs": list(acc.inputs), "outputs": list(acc.outputs),
            "groups": [{"name": g.name, "csrs": [csr(c) for c in g.csrs],
                        "units": [unit(u) for u in g.units],
                        "links": [link(k) for k in g.links]}
                       for g in acc.groups]}


# dot 1 (snax-forge C§17's table): accelerator dot, group mul (an ElementwiseLanes unit:
# START 0, JOBS 1, STATUS 2, COUNTER 3) and group sum (a TreeAccumulate unit: START 4,
# JOBS 5, JOB_BEATS 6, STATUS 7, COUNTER 8); readers mul.a, mul.b, sum.a, writers mul.out,
# sum.out
DOT = Accelerator(
    "dot", "out/design/dot/design_point.json", "snax_forge",
    ["mul.a", "mul.b", "sum.a"], ["mul.out", "sum.out"],
    [Group("mul", group_csrs(0), [elementwise("mul", "mul")], []),
     Group("sum", group_csrs(4, 1), [fold("sum", 4, lanes=4)], [])])
DOT_STREAMER = {
    "data_reader_params": {"spatial_bounds": [[4], [4], [4]], "temporal_dim": [1, 1, 1],
                           "num_channel": [4, 4, 4], "fifo_depth": [8, 8, 8]},
    "data_writer_params": {"spatial_bounds": [[4], [1]], "temporal_dim": [1, 1],
                           "num_channel": [4, 1], "fifo_depth": [8, 8]},
}


# dot 4 (snax-forge C§17's block): one group dot, a Mac unit (JOB_BEATS at 2) wired into a
# TreeAccumulate unit of fixed T 1 by the link out_partial; readers mac.a, mac.b, writer sum.out
DOT4 = Accelerator(
    "dot", "out/design/dot_4/design_point.json", "snax_forge", ["mac.a", "mac.b"], ["sum.out"],
    [Group("dot", group_csrs(0, 1), [
        Unit("mac", "mac", "Mac", {p: Port(p, "int64", 4, "out" if p == "out" else "in")
                                   for p in ("a", "b", "out")}, "int64",
             {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)], 1),
        Unit("sum", "accumulate", "TreeAccumulate",
             {"a": Port("in", "int64", 4, "in"), "out": Port("out", "int64", 1, "out")}, None,
             {"op": "add", "T": 1}, 1, 1, [], 1),
    ], [Link("out_partial", "mac.out", "sum.a", 0)])])
DOT4_STREAMER = {
    "data_reader_params": {"spatial_bounds": [[4], [4]], "temporal_dim": [1, 1],
                           "num_channel": [4, 4], "fifo_depth": [8, 8]},
    "data_writer_params": {"spatial_bounds": [[1]], "temporal_dim": [1], "num_channel": [1],
                           "fifo_depth": [8]},
}


def write_design(folder: Path, acc: dict, streamer: dict, rw: int, ro: int) -> Path:
    """forge/vecadd/'s cluster file in folder with its slot set for streamer and acc (the
    streamer file and accelerator.json beside it, as snax-forge writes them); its path."""
    d = hjson.loads(CLUSTER.read_text())
    slot = d["snax_forge_core_template"]["snax_acc_cfg"][0]
    ports = snax_cfg.streamer_channels(streamer)
    slot.update(snax_tcdm_ports=ports, sparse_interconnect_config=[[ports, 1]],
                snax_num_rw_csr=rw, snax_num_ro_csr=ro,
                snax_streamer_cfg={"$ref": "snax_forge_streamer.hjson"},
                snax_datapath_cfg={"$ref": "accelerator.json"})
    (folder / "snax_forge_streamer.hjson").write_text(json.dumps(streamer))
    (folder / "accelerator.json").write_text(json.dumps(acc))
    path = folder / "snax_forge.hjson"
    path.write_text(json.dumps(d))
    return path


def dot_cluster(folder: Path) -> Path:
    """The two-group dot 1 design in folder (DOT, DOT_STREAMER); its cluster file."""
    return write_design(folder, acc_json(DOT), DOT_STREAMER, 5, 4)


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
        return self.acc["groups"][group]["units"][0]

    def test_resolved(self):
        self.assertEqual(self.load().accelerator, VECADD)
        self.assertEqual(acc_json(VECADD), json.loads((FORGE / "vecadd" / "accelerator.json")
                                                      .read_text()))

    def test_the_old_datapath_block_is_refused(self):
        for key in ("unit", "control", "config", "wait", "fields"):
            self.acc = acc_json(VECADD)
            self.acc[key] = "x"
            self.fails(snax_cfg.CfgTypeError, f"snax_datapath_cfg.{key}",
                       "accelerator.json replaced")

    def test_offsets_contiguous(self):
        self.acc["groups"][0]["csrs"][2]["offset"] = 3
        self.acc["groups"][0]["csrs"][3]["offset"] = 4
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.groups",
                   "STATUS has offset 3, but is CSR 2 in CSR order")

    def test_group_csrs_in_order(self):
        csrs = self.acc["groups"][0]["csrs"]
        csrs[0], csrs[1] = csrs[1], csrs[0]
        self.fails(snax_cfg.CfgSlotError, "groups[0].csrs", "START, JOBS (rw), STATUS, COUNTER")
        self.acc = acc_json(VECADD)
        del self.acc["groups"][0]["csrs"][3]
        self.fails(snax_cfg.CfgSlotError, "groups[0].csrs", "START, JOBS (rw), STATUS, COUNTER")

    def test_csr_fields(self):
        del self.acc["groups"][0]["csrs"][1]["width"]
        self.fails(snax_cfg.CfgKeyError, "groups[0].csrs[1].width", "a read-write CSR has a width")
        self.acc = acc_json(VECADD)
        self.acc["groups"][0]["csrs"][2]["width"] = 32
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[2].width", "a read-only CSR has no width")
        self.acc = acc_json(VECADD)
        self.acc["groups"][0]["csrs"][0]["access"] = "wo"
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[0].access", "rw or ro")

    def test_csr_counts(self):
        self.rw = 3
        self.fails(snax_cfg.CfgSlotError, "snax_num_rw_csr", "accelerator.json has 2 read-write")
        self.rw, self.ro = 2, 1
        self.fails(snax_cfg.CfgSlotError, "snax_num_ro_csr", "2 read-only")

    def test_datapath(self):
        self.unit()["datapath"] = "Gemm"
        self.fails(snax_cfg.CfgTargetError, "units[0].datapath", "not a datapath SnaxGroup models")

    def test_links_and_units(self):
        """A link has its four keys; a group's units are connected by its links (gen.group);
        a unit name is the accelerator's once."""
        self.acc["groups"][0]["links"] = [{"name": "l", "from": "acc.out", "to": "acc.a"}]
        self.fails(snax_cfg.CfgKeyError, "groups[0].links[0].depth", "missing")
        self.acc = acc_json(VECADD)
        self.acc["groups"][0]["units"].append(copy.deepcopy(self.unit()))
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.groups", "unit 'acc' twice")
        self.acc["groups"][0]["units"][1]["name"] = "acc2"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.groups", "gen.group")

    def test_ports_name_the_movers(self):
        self.acc["inputs"] = ["acc.a"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs", "gen.outer")
        self.acc["inputs"] = ["acc.a", "acc.c"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs[1]", "names no port")
        self.acc["inputs"] = ["acc.a", "acc.a"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs[1]", "twice")
        self.acc = acc_json(VECADD)
        self.streamer["data_reader_params"] = {k: v[:1] for k, v in
                                               STREAMER["data_reader_params"].items()}
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs", "1 data_reader_params")

    def test_words_per_beat(self):
        """int32 a at 4 lanes is 2 words: its reader must have num_channel 2."""
        self.unit()["ports"]["a"]["dtype"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs[0]",
                   "acc.a: lanes 4 x 32 bits is 2 64-bit words per beat, but data_reader_params[0] "
                   "has num_channel 4")
        self.streamer["data_reader_params"]["num_channel"][0] = 2
        self.streamer["data_reader_params"]["spatial_bounds"][0] = [2]
        self.load()  # int32 with int64: int64, as opType says
        self.unit()["ports"]["a"]["lanes"] = 3
        self.fails(snax_cfg.CfgTargetError, "snax_datapath_cfg.inputs", "one lane count")

    def test_op_type(self):
        self.unit()["opType"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.groups",
                   "opType int32, but its inputs' result type is int64")
        del self.unit()["opType"]
        self.fails(snax_cfg.CfgKeyError, "units[0].opType", "missing")
        self.acc = acc_json(VECADD)
        self.unit()["ports"]["b"]["dtype"] = "uint64"
        self.fails(snax_cfg.CfgTypeError, "snax_datapath_cfg.groups",
                   "int64 with uint64 has no integer result type")

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
        """ElementwiseLanes has no JOB_BEATS, TreeAccumulate one; other unit CSRs are not
        modelled."""
        self.unit()["csrs"] = [{"name": "JOB_BEATS", "access": "rw", "offset": 2, "width": 32}]
        self.acc["groups"][0]["csrs"][2]["offset"] = 3
        self.acc["groups"][0]["csrs"][3]["offset"] = 4
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
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.outputs[0]",
                   "a fold's output is one 64-bit word per beat, but data_writer_params[0] has "
                   "num_channel 2")
        self.streamer["data_writer_params"].update(spatial_bounds=[[1]], num_channel=[1])
        self.assertEqual(self.load().accelerator.groups[0].units[0].ports["a"].lanes, 4)
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
    """dot 4 (snax-forge C§17's block): one group of a Mac wired into a TreeAccumulate, read
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
        acc = self.load().accelerator
        self.assertEqual(acc, DOT4)
        (group,) = acc.groups
        self.assertEqual([u.span for u in group.units], [1, 1])
        self.assertEqual(group.units[1].params["T"], 1)
        self.assertEqual(group.links, [Link("out_partial", "mac.out", "sum.a", 0)])
        self.assertEqual(group.rw, ["START", "JOBS", "JOB_BEATS"])

    def link(self, **kw):
        self.acc["groups"][0]["links"][0].update(kw)

    def test_gen_link(self):
        self.link(to="mac.a")  # out to an in port, but mac.a is outer: also on inputs
        self.fails(snax_cfg.CfgSlotError, "gen.")
        self.acc = acc_json(DOT4)
        self.link(**{"from": "sum.a", "to": "mac.a"})  # in to in
        self.fails(snax_cfg.CfgSlotError, "gen.link:")
        self.acc = acc_json(DOT4)
        self.acc["groups"][0]["units"][1]["ports"]["a"]["lanes"] = 2  # lanes differ
        self.fails(snax_cfg.CfgSlotError, "gen.link:")
        self.acc = acc_json(DOT4)
        self.link(depth=-1)
        self.fails(snax_cfg.CfgSlotError, "gen.link:")

    def test_gen_link_port(self):
        links = self.acc["groups"][0]["links"]
        links.append(dict(links[0], name="again", depth=1))
        self.fails(snax_cfg.CfgSlotError, "gen.link_port:")

    def test_gen_outer(self):
        self.acc["inputs"] = ["mac.a", "mac.b", "sum.a"]
        self.fails(snax_cfg.CfgSlotError, "gen.outer:")
        self.acc = acc_json(DOT4)
        self.acc["inputs"] = ["mac.b", "mac.a"]
        self.fails(snax_cfg.CfgSlotError, "gen.outer:")

    def test_gen_group(self):
        self.acc["groups"][0]["links"] = []
        self.acc["inputs"] = ["mac.a", "mac.b", "sum.a"]
        self.acc["outputs"] = ["mac.out", "sum.out"]
        self.fails(snax_cfg.CfgSlotError, "gen.group:")

    def test_gen_chain(self):
        """The link mac -> sum over the units in the order sum, mac: not a chain in unit order,
        snax-forge's gen.chain in its words."""
        self.acc["groups"][0]["units"].reverse()
        self.fails(snax_cfg.CfgTargetError,
                   "gen.chain: accelerator dot: group dot's links [('mac', 'sum')] over its units "
                   "['sum', 'mac']: a group is a chain until tier A (fork and join)")

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
                      "a unit with span > 1 reads from a link until B2", ctx.exception.why)

    def test_a_datapath_is_the_registrys(self):
        self.acc["groups"][0]["units"][0]["datapath"] = "LinkBuffer"
        self.fails(snax_cfg.CfgTargetError, "not a datapath SnaxGroup models")

    def test_timing_is_the_datapaths(self):
        self.acc["groups"][0]["units"][1]["timing"]["span"] = 4
        self.fails(snax_cfg.CfgTargetError, "gen.timing:")


class TwoGroups(unittest.TestCase):
    """dot 1 as one accelerator of two groups (snax-forge D148, C§17's table)."""

    def test_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            (slot,) = snax_cfg.load(dot_cluster(Path(tmp))).cores[0].accelerators
        acc = slot.accelerator
        self.assertEqual(acc, DOT)
        self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports), (5, 4, 17))
        self.assertEqual([(c.name, c.offset) for c in acc.csrs],
                         [("START", 0), ("JOBS", 1), ("STATUS", 2), ("COUNTER", 3),
                          ("START", 4), ("JOBS", 5), ("JOB_BEATS", 6), ("STATUS", 7),
                          ("COUNTER", 8)])
        self.assertEqual([g.rw for g in acc.groups], [["START", "JOBS"],
                                                      ["START", "JOBS", "JOB_BEATS"]])
        self.assertEqual(acc.ports_of("sum", acc.inputs), [(2, "a")])
        self.assertEqual(acc.ports_of("sum", acc.outputs), [(1, "out")])

    def test_forge_dot_1(self):
        """forge/dot_1/, snax-forge's dot 1: the same accelerator, its design point named."""
        (slot,) = snax_cfg.load(FORGE / "dot_1" / "snax_forge.hjson").cores[0].accelerators
        self.assertEqual(slot.accelerator,
                         replace(DOT, design_point="out/design/dot_1/design_point.json"))
        self.assertEqual((slot.num_rw_csr, slot.num_ro_csr, slot.tcdm_ports), (5, 4, 17))


if __name__ == "__main__":
    unittest.main()
