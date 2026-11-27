# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_cfg.py. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Reads sw/cfg/snitch_cluster.hjson and forge/'s fixtures, then broken copies
of forge/vecadd_v1/'s cluster (its streamer file and accelerator.json inlined,
written as JSON into a temporary folder), broken accelerator.json files
beside it, hand-written dot 1 designs: two
accelerators vmul and vsum in two streamer sets, and dot_v1_1, the two as
one accelerator dot of two groups; bicg_v3's one group of two chains on a
forked input; then the sets' refusals and the slot form before sets
(snax_streamer_cfg), read as one set. snax_cluster's copy in
sw/cfg/snax_forge/ is never read.
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "snax"))
import hjson  # noqa: E402
import snax_cfg  # noqa: E402
from snax_cfg import (Accelerator, Csr, Description, ForkLink, Group, Link,  # noqa: E402
                      MoverUser, Port, PortMux, SharedMover, Unit)

CFG = ROOT / "sw" / "cfg"
FORGE = ROOT / "forge"
# forge/vecadd_v1/'s cluster file, the snax_hjson target's default
CLUSTER = FORGE / "vecadd_v1" / "snax_forge.hjson"

# The streamer of forge/vecadd_v1/ and vecmul/
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


# forge/vecadd_v1/'s accelerator.json, parsed
VECADD = accelerator("vecadd_v1", simd("acc", "add"))

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
        rowsum_v2_padded, rowsum_v2 under the padded_rows layout, whose design is rowsum_v2)."""
        cfg = snax_cfg.load(FORGE / folder / "snax_forge.hjson")
        self.assertEqual(cfg.name, "snax_forge_cluster")
        self.assertTrue(cfg.tcdm.sparse_interconnect)
        (slot,) = cfg.cores[0].accelerators
        design = json.loads((FORGE / folder / "manifest.json").read_text())["design"]
        self.assertEqual(slot.name, f"snax_forge_{design}")
        return slot

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
             "ports": {k: {"port": p.port, "dir": p.dir, "dtype": p.dtype, "lanes": p.lanes,
                           **({"d_out": p.d_out} if p.d_out > 1 else {}),
                           **({"d_in": p.d_in} if p.d_in > 1 else {}),
                           **({"broadcast": True} if p.broadcast else {}),
                           **({"hold": True} if p.hold else {}),
                           **({"carry": True} if p.carry else {})}
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
        d = {"name": a.name,
             "inputs": [x if isinstance(x, str) else list(x) for x in a.inputs],
             "outputs": list(a.outputs),
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
DOT1 = description("dot_v1", VMUL, VSUM)
VMUL_STREAMER = streamer([4, 4], [4])
VSUM_STREAMER = streamer([4], [1])
# dot_v1_1: the same two groups in one accelerator dot, one set; readers vmul.a,
# vmul.b, vsum.a, writers vmul.out, vsum.out
DOT = description("dot_v1_1", Accelerator("dot", ["vmul.a", "vmul.b", "vsum.a"],
                                           ["vmul.out", "vsum.out"], VMUL.groups + VSUM.groups))
DOT_STREAMER = streamer([4, 4, 4], [4, 1])
# dot 1 with share_ports on tmp0: vmul and vsum on one set whose movers they
# share, per role the k-th widest port of each group on mover k: reader0 vmul.a / vsum.a,
# reader1 vmul.b, writer0 vmul.out / vsum.out (1 of its 4 channels, so masked); PORT_MUX_SEL
# at offset 9, after vsum's window
DOT_SHARED = description("dot_v1_2", Accelerator(
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
DOT4 = description("dot_v4", Accelerator(
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
    """forge/vecadd_v1/'s cluster file in folder with its slot set for acc and sets, each
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
    """dot_v1_1 in folder (DOT, DOT_STREAMER): one set; its cluster file."""
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

    def test_the_old_datapath_block_is_refused(self):
        for key in ("unit", "control", "config", "wait", "fields"):
            self.acc = acc_json(VECADD)
            self.acc[key] = "x"
            self.fails(snax_cfg.CfgTypeError, f"snax_datapath_cfg.{key}",
                       "accelerator.json replaced")

    def test_csr_fields(self):
        del self.acc["accelerators"][0]["groups"][0]["csrs"][2]["width"]
        self.fails(snax_cfg.CfgKeyError, "groups[0].csrs[2].width", "every CSR has a width")
        self.acc = acc_json(VECADD)
        self.acc["accelerators"][0]["groups"][0]["csrs"][3]["width"] = 33
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[3].width", "must be 1 to 32 bits")
        self.acc = acc_json(VECADD)
        self.acc["accelerators"][0]["groups"][0]["csrs"][0]["access"] = "wo"
        self.fails(snax_cfg.CfgTypeError, "groups[0].csrs[0].access", "rw or ro")

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
        """opType holds the inputs' result type: int64 itself here (int64 inputs), never
        narrower; a wider one comes from the kernel's casts."""
        self.unit()["opType"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups",
                   "opType int32 does not hold its inputs' result type int64")
        self.unit()["opType"] = "uint64"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups",
                   "opType uint64 does not hold its inputs' result type int64")
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

    def test_one_stream_widened(self):
        """gesummv's literal scale at int8: a at int8 times k from its CSR at int32, the op at
        int32 (an opType that holds a's type); one narrower than a is refused."""
        scale = snax_cfg.Unit(
            "acc", "simd", "SimdLanes",
            {"a": snax_cfg.Port("a", "int8", 8, "in"),
             "out": snax_cfg.Port("out", "int32", 8, "out")},
            "int32", {"op": "mul"}, 0, 1, [Csr("K", "rw", 2, 32, "k")], scalars={"k": "int32"})
        self.acc = acc_json(accelerator("gesummv_v1_1", scale, between=1))
        self.streamer, self.rw = streamer([1], [4]), 3
        (unit,) = self.load().description.groups[0].units
        self.assertEqual((unit.op_type, unit.ports["a"].dtype, unit.scalars),
                         ("int32", "int8", {"k": "int32"}))
        self.unit()["opType"] = "int8"
        self.unit()["ports"]["a"]["dtype"] = "int32"
        self.unit()["ports"]["out"]["dtype"] = "int8"
        self.unit()["scalars"] = {"k": "int8"}
        self.unit()["csrs"][0]["width"] = 8
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups",
                   "opType int8 does not hold its one input's type int32")

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
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k2",
                   "k2 is axpby's and axpbypcz's, not add's")
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

    def test_axpbypcz(self):
        """axpbypcz: three inputs (gray's: uint8 at an opType uint16 that holds them), d baked,
        a power of two, each k baked, from its CSR (K3 here) or unset; lo is requant's."""
        u8 = {p: snax_cfg.Port(p, "uint8", 8, "out" if p == "out" else "in")
              for p in ("a", "b", "c", "out")}
        gray = snax_cfg.Unit("acc", "simd", "SimdLanes", u8, "uint16",
                             {"op": "axpbypcz", "k1": 77, "k2": 150, "d": 256}, 0, 1,
                             [Csr("K3", "rw", 2, 16, "k3")], scalars={"k3": "uint16"})
        self.acc = acc_json(accelerator("gray_v1", gray, between=1))
        self.streamer, self.rw = streamer([1, 1, 1], [1]), 3
        (unit,) = self.load().description.groups[0].units
        self.assertEqual((unit.params, unit.scalars),
                         ({"op": "axpbypcz", "k1": 77, "k2": 150, "d": 256}, {"k3": "uint16"}))
        self.unit()["params"]["d"] = 6
        self.fails(snax_cfg.CfgTypeError, "units[0].params.d",
                   "6: not a power of two; the unit divides by shifting")
        del self.unit()["params"]["d"]
        self.fails(snax_cfg.CfgKeyError, "units[0].params.d", "missing: axpbypcz takes d, baked in "
                   "params")
        self.unit()["params"]["d"] = 256
        self.unit()["params"]["lo"] = 0
        self.fails(snax_cfg.CfgTypeError, "units[0].params.lo", "lo is requant's, not axpbypcz's")
        del self.unit()["params"]["lo"]
        self.unit()["params"]["k1"] = 2 ** 16
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k1", "does not fit the opType uint16")
        self.unit()["params"]["k1"] = 77
        del self.unit()["ports"]["c"]
        self.acc["accelerators"][0]["inputs"] = ["acc.a", "acc.b"]
        self.streamer = streamer([1, 1], [1])
        self.fails(snax_cfg.CfgTargetError, "snax_datapath_cfg.accelerators[0].inputs",
                   "2 inputs and 1 outputs; SimdLanes takes 3 and 1")

    def test_requant_and_threshold(self):
        """requant takes d, lo and hi, all baked (a CSR holds none of them); threshold k, baked or
        from its CSR, and hi; each one input at an opType that holds it."""
        one = {"a": snax_cfg.Port("a", "int32", 8, "in"),
               "out": snax_cfg.Port("out", "int8", 8, "out")}
        requant = snax_cfg.Unit("acc", "simd", "SimdLanes", one, "int32",
                                {"op": "requant", "d": 1024, "lo": 0, "hi": 127}, 0, 1, [])
        self.acc = acc_json(accelerator("requant_v1", requant))
        self.streamer, self.rw = streamer([4], [1]), 2
        (unit,) = self.load().description.groups[0].units
        self.assertEqual(unit.params, {"op": "requant", "d": 1024, "lo": 0, "hi": 127})
        del self.unit()["params"]["lo"]
        self.fails(snax_cfg.CfgKeyError, "units[0].params.lo", "missing: requant takes lo, baked "
                   "in params")
        self.unit()["params"]["lo"] = 0
        self.unit()["params"]["k"] = 3
        self.fails(snax_cfg.CfgTypeError, "units[0].params.k", "k is threshold's, not requant's")
        del self.unit()["params"]["k"]
        del self.unit()["params"]["hi"]
        self.unit()["scalars"] = {"hi": "int32"}
        self.fails(snax_cfg.CfgTypeError, "units[0].scalars.hi",
                   "not a slot of SimdLanes a CSR holds (k, k1, k2, k3)")
        u8 = {"a": snax_cfg.Port("a", "uint8", 8, "in"),
              "out": snax_cfg.Port("out", "uint8", 8, "out")}
        threshold = snax_cfg.Unit("acc", "simd", "SimdLanes", u8, "int16",
                                  {"op": "threshold", "hi": 255}, 0, 1,
                                  [Csr("K", "rw", 2, 16, "k")], scalars={"k": "int16"})
        self.acc = acc_json(accelerator("threshold_v1", threshold, between=1))
        self.streamer, self.rw = streamer([1], [1]), 3
        (unit,) = self.load().description.groups[0].units
        self.assertEqual((unit.params, unit.scalars), ({"op": "threshold", "hi": 255},
                                                       {"k": "int16"}))
        del self.unit()["params"]["hi"]
        self.fails(snax_cfg.CfgKeyError, "units[0].params.hi", "missing: threshold takes hi")
        self.unit()["params"]["hi"] = 255
        self.unit()["opType"] = "int8"
        self.unit()["scalars"] = {"k": "int8"}
        self.unit()["csrs"][0]["width"] = 8
        self.unit()["params"]["hi"] = 127
        self.unit()["ports"]["a"]["dtype"] = "int16"
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].groups",
                   "opType int8 does not hold its one input's type int16")

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

    def test_a_sliced_input(self):
        """A fold's a at int16, 2 lanes, sliced 2 (d_in 2) from one word on the reader's
        one channel; a d_in that does not empty a word, one not 2, 4 or 8, d_in on an output,
        and no d_in at all (32 bits a beat), refused."""
        self.acc = acc_json(accelerator("vsum_slice", fold("acc", 0, "int16", 2), between=1))
        self.streamer = streamer([1], [1])
        self.rw = 3
        a = self.unit()["ports"]["a"]
        a["d_in"] = 2
        self.assertEqual(self.load().description.groups[0].units[0].ports["a"].d_in, 2)
        a["d_in"] = 4
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[0]",
                   "d_in 4 pops of 2 x 16 bits are 128 bits, not one 64-bit word")
        a["d_in"] = 3
        self.fails(snax_cfg.CfgTypeError, "units[0].ports.a.d_in",
                   "an input's pops per word, 2, 4 or 8")
        del a["d_in"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.accelerators[0].inputs[0]",
                   "not a whole number of 64-bit channel words")
        self.unit()["ports"]["out"]["d_in"] = 2
        self.fails(snax_cfg.CfgTypeError, "units[0].ports.out.d_in", "an input's pops per word")

    def test_fold(self):
        """vsum_v1_1_1's accelerator: a fold's output one word, whatever its lanes' type."""
        self.acc = acc_json(accelerator("vsum_v1_1_1", fold("acc", 0, "int32", 4), between=1))
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

    def link(self, **kw):
        self.acc["accelerators"][0]["groups"][0]["links"][0].update(kw)

    def test_a_packed_output(self):
        """sum.out at int32 packed two to a word (d_out 2) on the writer's one channel;
        d_out on an input, a d_out that does not fill a word, or one not 2, 4 or 8, refused."""
        out = self.acc["accelerators"][0]["groups"][0]["units"][1]["ports"]["out"]
        out.update(dtype="int32", d_out=2)
        (group,) = self.load().description.groups
        self.assertEqual(group.units[1].ports["out"].d_out, 2)
        out.update(dtype="int64")
        self.fails(snax_cfg.CfgSlotError, "d_out 2 results of 64 bits are 128 bits")
        out.update(dtype="int32", d_out=3)
        self.fails(snax_cfg.CfgTypeError, "an output's results per word, 2, 4 or 8")
        del out["d_out"]
        self.acc["accelerators"][0]["groups"][0]["units"][0]["ports"]["a"]["d_out"] = 2
        self.fails(snax_cfg.CfgTypeError, "an output's results per word")

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

    def test_gen_link_sliced_or_packed(self):
        """A linked port carries no d_in or d_out above 1: it has no slicer or packer."""
        units = self.acc["accelerators"][0]["groups"][0]["units"]
        units[1]["ports"]["a"].update(dtype="int32", d_in=2)
        units[0]["ports"]["out"]["dtype"] = "int32"
        self.fails(snax_cfg.CfgSlotError, "gen.link: group dot's link out_partial: sum.a has "
                   "d_in 2 and d_out 1; a linked port has no slicer or packer")
        del units[1]["ports"]["a"]["d_in"]
        units[0]["ports"]["out"]["d_out"] = 2
        self.fails(snax_cfg.CfgSlotError, "mac.out has d_in 1 and d_out 2")

    def test_gen_link_port(self):
        links = self.acc["accelerators"][0]["groups"][0]["links"]
        links.append(dict(links[0], name="again", depth=1))
        self.fails(snax_cfg.CfgSlotError, "gen.link_port:")

    def test_gen_chain(self):
        """The link mac -> sum over the units in the order sum, mac: not a chain in unit order,
        snax-forge's gen.chain in its words."""
        self.acc["accelerators"][0]["groups"][0]["units"].reverse()
        self.fails(snax_cfg.CfgTargetError,
                   "gen.chain: accelerator dot: group dot's links [('mac', 'sum')] over its units "
                   "['sum', 'mac']: a group is a chain, or chains a fork joins (fork_read)")

    def test_a_datapath_is_the_registrys(self):
        self.acc["accelerators"][0]["groups"][0]["units"][0]["datapath"] = "LinkBuffer"
        self.fails(snax_cfg.CfgTargetError, "not a datapath SnaxGroup models")

    def test_timing_is_the_datapaths(self):
        self.acc["accelerators"][0]["groups"][0]["units"][1]["timing"]["span"] = 4
        self.fails(snax_cfg.CfgTargetError, "gen.timing:")


# matvec_acc_v1's sum: a TreeAccumulate over 4 lanes with a seed port,
# one int64 lane read once per job, its one accelerator's readers sum.a and sum.seed
def seeded(datapath: str = "TreeAccumulate", seed: Port = Port("seed", "int64", 1, "in"),
           lanes: int = 4, span: int = 1, name: str = "acc") -> Unit:
    return Unit(name, "accumulate", datapath,
                {"a": Port("in", "int64", lanes, "in"), "seed": seed,
                 "out": Port("out", "int64", 1, "out")}, None,
                {"op": "add"} if datapath == "TreeAccumulate" else {}, 1, 1,
                [Csr("JOB_BEATS", "rw", 2, 32)], span)


SEEDED_STREAMER = streamer([4, 1], [1])


def seeded_mac(lanes: int = 4, dtype: str = "int64", out: str = "int64",
               b: Port = None) -> Unit:
    """A Mac (accumulate) of ``lanes`` lanes seeded from its output's container: a, b, then
    the seed of the output's lanes and dtype."""
    return Unit("acc", "mac", "Mac", {"a": Port("a", dtype, lanes, "in"),
                                      "b": b or Port("b", dtype, lanes, "in"),
                                      "seed": Port("seed", out, lanes, "in"),
                                      "out": Port("out", out, lanes, "out")}, out,
                {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)])


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

    def test_the_seed_port_is_checked(self):
        cases = [
            (Port("seed", "int64", 2, "in"), "gen.seed: 2 lanes, a seed has its output's 1"),
            (Port("seed", "int32", 1, "in"), "gen.seed: int32, a seed is its output's int64"),
        ]
        for port, text in cases:
            e = self.refused(acc_json(accelerator("matvec_acc_v1", seeded(seed=port), between=1)),
                             text)
            self.assertIn("ports.seed", e.path)
        mac = Unit("acc", "mac", "Mac", {"a": Port("a", "int64", 4, "in"),
                                          "b": Port("b", "int64", 4, "in"),
                                          "seed": Port("seed", "int64", 1, "in"),
                                          "out": Port("out", "int64", 4, "out")}, "int64",
                   {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 2, 32)])
        self.refused(acc_json(accelerator("mac_seed", mac, between=1)),
                     "gen.seed: 1 lanes, a seed has its output's 4", streamer([4, 4, 1], [4]))
        simd_seed = replace(simd("acc", "add"), ports={**simd("acc", "add").ports,
                                                        "seed": Port("seed", "int64", 4, "in")})
        self.refused(acc_json(accelerator("simd_seed", simd_seed)),
                     "gen.seed: SimdLanes takes no seed (TreeAccumulate, SerialAccumulate and "
                     "Mac do)", streamer([4, 4, 4], [4]))
        first = acc_json(accelerator("matvec_acc_v1", seeded(), between=1))
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
                     "streamer: a unit with span > 1 reads from a link")


class Broadcast(unittest.TestCase):
    """A broadcast: an input of a lane-wise datapath (SimdLanes, Mac) whose reader moves one
    lane, given to all of them: the port keeps its unit's lanes, its words per beat and d_in count
    one lane. mvt's half 2: a Mac of 8 int8 lanes, b (y2) broadcast through a slicer of 8 pops
    a word, seeded from x2 at int32 (4 channels), the output 4 channels."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        b = Port("b", "int8", 8, "in", d_in=8, broadcast=True)
        self.desc = accelerator("mac_bcast", seeded_mac(8, "int8", "int32", b), between=1)
        self.streamer = streamer([1, 1, 4], [4])

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, acc, rw=3):
        path = write_design(self.dir, acc, self.streamer, rw, 2)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot.description

    def fails(self, acc, kind, text, rw=3):
        with self.assertRaises(kind) as ctx:
            self.load(acc, rw)
        self.assertIn(text, str(ctx.exception))

    def test_a_linked_port_is_none(self):
        """vmul -> vadd (two SimdLanes, 4 lanes of int64): vadd's a on the link is not a
        broadcast; it takes its lanes from the link (gen.link)."""
        group = Group("chain", group_csrs(0), [simd("vmul", "mul"), simd("vadd", "add")],
                      [Link("prod", "vmul.out", "vadd.a", 0)])
        acc = acc_json(description("chain", Accelerator(
            "chain", ["vmul.a", "vmul.b", "vadd.b"], ["vadd.out"], [group])))
        self.streamer = streamer([4, 4, 4], [4])
        self.load(acc, 2)
        acc["accelerators"][0]["groups"][0]["units"][1]["ports"]["a"]["broadcast"] = True
        self.fails(acc, snax_cfg.CfgSlotError, "gen.link: group chain's link prod: vadd.a is a "
                   "broadcast; a linked port takes its lanes from the link", 2)

    def test_refused(self):
        """A broadcast on an output, on one lane, on a fold that sums its lanes, or on a
        seed."""
        acc = acc_json(self.desc)
        ports = acc["accelerators"][0]["groups"][0]["units"][0]["ports"]
        ports["out"]["broadcast"] = True
        self.fails(acc, snax_cfg.CfgTypeError, "an input of 2 lanes or more takes a broadcast")
        ports["out"]["broadcast"] = False
        ports["seed"]["broadcast"] = True
        self.fails(acc, snax_cfg.CfgTargetError, "gen.seed: a seed is not a broadcast")
        tree = acc_json(accelerator("vsum_v1_1", fold("acc", 0, "int64", 4), between=1))
        tree["accelerators"][0]["groups"][0]["units"][0]["ports"]["a"]["broadcast"] = True
        self.streamer = streamer([1], [1])
        self.fails(tree, snax_cfg.CfgTargetError, "gen.broadcast: TreeAccumulate sums its lanes")
        one = acc_json(accelerator("vecadd_v1", replace(simd("acc", "add"), ports={
            p: Port(p, "int64", 1, "out" if p == "out" else "in") for p in ("a", "b", "out")})))
        one["accelerators"][0]["groups"][0]["units"][0]["ports"]["b"]["broadcast"] = True
        self.fails(one, snax_cfg.CfgTypeError, "an input of 2 lanes or more takes a broadcast")


# bicg_v3, one pass over A: one group of two chains, mul -> buffer of depth 1 -> sum
# (q) and mac (s), A's reader forked to mul.a and mac.a, r broadcast to the Mac's 32 int8 lanes
# through a slicer of 8 pops, q packed two int32 results to a word; CSRs START 0, JOBS_SUM 1,
# JOBS_MAC 2, sum's JOB_BEATS 3, mac's 4, STATUS 5, BUSY_COUNTER 6 (snax-forge's generator's)
BICG3 = description("bicg_v3", Accelerator(
    "bicg_types", [["mul.a", "mac.a"], "mul.b", "mac.b"], ["sum.out", "mac.out"],
    [Group("bicg_types", [Csr("START", "rw", 0, 1), Csr("JOBS_SUM", "rw", 1, 32),
                          Csr("JOBS_MAC", "rw", 2, 32), Csr("STATUS", "ro", 5, 2),
                          Csr("BUSY_COUNTER", "ro", 6, 32)], [
        Unit("mul", "simd", "SimdLanes", {"a": Port("a", "int8", 32, "in"),
                                          "b": Port("b", "int8", 32, "in"),
                                          "out": Port("out", "int32", 32, "out")}, "int32",
             {"op": "mul"}, 0, 1, []),
        Unit("sum", "accumulate", "TreeAccumulate",
             {"a": Port("in", "int32", 32, "in"), "out": Port("out", "int32", 1, "out", d_out=2)},
             None, {"op": "add"}, 1, 1, [Csr("JOB_BEATS", "rw", 3, 32)]),
        Unit("mac", "mac", "Mac", {"a": Port("a", "int8", 32, "in"),
                                   "b": Port("b", "int8", 32, "in", d_in=8, broadcast=True),
                                   "out": Port("out", "int32", 32, "out")}, "int32",
             {"accumulate": True, "regOut": False}, 1, 1, [Csr("JOB_BEATS", "rw", 4, 32)]),
    ], [Link("q_prod", "mul.out", "sum.a", 1)])]))
BICG3_STREAMER = streamer([4, 4, 1], [1, 16])


class Fork(unittest.TestCase):
    """bicg_v3: a forked input is one entry of inputs, a list whose first port takes the
    reader; a JOBS_<SINK> per chain; each of snax-forge's fork checks (gen.fork, gen.group,
    gen.outer, gen.chain, gen.share) refuses its case in its words."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.acc = acc_json(BICG3)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, rw=5):
        path = write_design(self.dir, self.acc, BICG3_STREAMER, rw, 2)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot.description

    def fails(self, kind, text, rw=5):
        with self.assertRaises(kind) as ctx:
            self.load(rw)
        self.assertIn(text, ctx.exception.why)
        return ctx.exception

    def group(self):
        return self.acc["accelerators"][0]["groups"][0]

    def test_an_entry_is_a_port_or_a_list_of_ports(self):
        self.acc["accelerators"][0]["inputs"][0] = ["mul.a", 3]
        self.fails(snax_cfg.CfgTypeError, "each a string or a fork's list of strings")
        self.acc["accelerators"][0]["inputs"][0] = ["mul.a", "mac.x"]
        self.fails(snax_cfg.CfgSlotError, "'mac.x' names no port of accelerator bicg_types")
        self.acc["accelerators"][0]["inputs"][0] = ["mul.a", "mul.a"]
        self.fails(snax_cfg.CfgSlotError, "'mul.a' twice")

    def test_gen_fork(self):
        """Ports unlike (A's int8 lanes and r's broadcast), and a fork of one port."""
        self.acc["accelerators"][0]["inputs"] = [["mul.a", "mac.b"], "mul.b", "mac.a"]
        self.fails(snax_cfg.CfgSlotError, "gen.fork: accelerator bicg_types: the fork ['mul.a', "
                   "'mac.b']: its ports differ in dtype, lanes, d_in or broadcast; one reader's "
                   "beat is the same for all")
        self.acc["accelerators"][0]["inputs"] = [["mul.a"], "mul.b", "mac.a", "mac.b"]
        self.fails(snax_cfg.CfgSlotError, "gen.fork: accelerator bicg_types: the fork ['mul.a']: "
                   "a fork gives one reader to two or more outer input ports of its units")
        self.acc["accelerators"][0]["inputs"] = [["mul.a", "mac.a", "sum.a"], "mul.b", "mac.b"]
        self.fails(snax_cfg.CfgSlotError, "two or more outer input ports of its units (['mul.a', "
                   "'mul.b', 'mac.a', 'mac.b'])")

    def test_a_jobs_per_chain(self):
        """JOBS_<SINK> per chain in its sinks' order; one JOBS for two chains, or JOBS_<SINK>
        for one, refused."""
        csrs = self.group()["csrs"]
        csrs[1]["name"], csrs[2]["name"] = "JOBS_MAC", "JOBS_SUM"
        self.fails(snax_cfg.CfgSlotError, "group bicg_types's JOBS CSRs ['JOBS_MAC', 'JOBS_SUM']: "
                   "its chains [['mul', 'sum'], ['mac']] take ['JOBS_SUM', 'JOBS_MAC'], one per "
                   "chain in the order of their sinks")
        self.acc = acc_json(BICG3)
        csrs = self.group()["csrs"]
        del csrs[2]
        csrs[1]["name"] = "JOBS"
        for c in [*csrs[2:], *(x for u in self.group()["units"] for x in u["csrs"])]:
            c["offset"] -= 1
        self.fails(snax_cfg.CfgSlotError, "take ['JOBS_SUM', 'JOBS_MAC']", rw=4)
        dot4 = acc_json(DOT4)
        dot4["accelerators"][0]["groups"][0]["csrs"][1]["name"] = "JOBS_SUM"
        self.acc = dot4
        with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
            snax_cfg.load(write_design(self.dir, self.acc, DOT4_STREAMER, 3, 2))
        self.assertIn("a group's own CSRs are START, JOBS (rw), STATUS, BUSY_COUNTER (ro), in "
                      "that order, with several chains a JOBS_<SINK> per chain in place of JOBS",
                      ctx.exception.why)

    def test_gen_share(self):
        """A fork and shared movers in one accelerator."""
        acc = self.acc["accelerators"][0]
        acc["movers"] = []
        acc["port_mux"] = {"groups": ["bicg_types"],
                           "csr": {"name": "PORT_MUX_SEL", "access": "rw", "offset": 7,
                                   "width": 1}}
        self.fails(snax_cfg.CfgSlotError, "gen.share: accelerator bicg_types: a fork and shared "
                   "movers in one accelerator; share_ports or fork_read, not both", rw=6)


# bicg_v4_1, snax-forge's generator's at 64 x 64, W 4, R 8 in two strips: q's
# sum (T 8) seeded from q, carried (CARRY), s's Mac a bank of 8 rows (ROWS 4 bits) with r held
# and broadcast through a slicer of 8 pops; CSRs START 0, JOBS_SUM 1, JOBS_MAC 2, CARRY 3, the
# Mac's JOB_BEATS 4 and ROWS 5, STATUS 6, BUSY_COUNTER 7
BICG4 = description("bicg_v4_1", Accelerator(
    "bicg_types", [["mul.a", "mac.a"], "mul.b", "sum.seed", "mac.b"], ["sum.out", "mac.out"],
    [Group("bicg_types", [Csr("START", "rw", 0, 1), Csr("JOBS_SUM", "rw", 1, 32),
                          Csr("JOBS_MAC", "rw", 2, 32), Csr("STATUS", "ro", 6, 2),
                          Csr("BUSY_COUNTER", "ro", 7, 32)], [
        Unit("mul", "simd", "SimdLanes", {"a": Port("a", "int8", 4, "in", d_in=2),
                                          "b": Port("b", "int8", 4, "in", d_in=2),
                                          "out": Port("out", "int32", 4, "out")}, "int32",
             {"op": "mul"}, 0, 1, []),
        Unit("sum", "accumulate", "TreeAccumulate",
             {"a": Port("in", "int32", 4, "in"),
              "seed": Port("seed", "int32", 1, "in", d_in=2, carry=True),
              "out": Port("out", "int32", 1, "out", d_out=2)},
             None, {"op": "add", "T": 8}, 1, 1, [Csr("CARRY", "rw", 3, 32)]),
        Unit("mac", "mac", "Mac", {"a": Port("a", "int8", 4, "in", d_in=2),
                                   "b": Port("b", "int8", 4, "in", d_in=8, broadcast=True,
                                             hold=True),
                                   "out": Port("out", "int32", 4, "out")}, "int32",
             {"accumulate": True, "regOut": False, "rows": 8}, 1, 1,
             [Csr("JOB_BEATS", "rw", 4, 32), Csr("ROWS", "rw", 5, 4)]),
    ], [Link("q_prod", "mul.out", "sum.a", 1)])]))
BICG4_STREAMER = streamer([1, 1, 1, 1], [1, 2])


class Bank(unittest.TestCase):
    """bicg_v4_1: a Mac's bank (rows, ROWS), its held input (hold) and a carried seed
    (carry, CARRY); each refused case in snax-forge's words (gen.args, gen.hold,
    gen.seed) or as a slot that disagrees (the CSRs)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.acc = acc_json(BICG4)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, rw=6):
        path = write_design(self.dir, self.acc, BICG4_STREAMER, rw, 2)
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        return slot.description

    def fails(self, kind, text, rw=6):
        with self.assertRaises(kind) as ctx:
            self.load(rw)
        self.assertIn(text, ctx.exception.why)

    def unit(self, name):
        units = self.acc["accelerators"][0]["groups"][0]["units"]
        return next(u for u in units if u["name"] == name)

    def test_gen_args(self):
        """rows on a fold that is not a Mac (a seeded one too), below 1."""
        self.unit("sum")["params"]["rows"] = 2
        self.unit("sum")["csrs"].append({"name": "ROWS", "access": "rw", "offset": 4, "width": 2})
        self.fails(snax_cfg.CfgSlotError, "a unit's own CSRs are ['ROWS', 'CARRY']")
        self.acc = acc_json(BICG4)
        self.unit("sum")["params"]["rows"] = 2
        self.unit("sum")["csrs"].insert(0, {"name": "ROWS", "access": "rw", "offset": 3,
                                            "width": 2})
        self.unit("sum")["csrs"][1]["offset"] = 4
        for u in ("mac",):
            for c in self.unit(u)["csrs"]:
                c["offset"] += 1
        self.acc["accelerators"][0]["groups"][0]["csrs"][3]["offset"] = 7
        self.acc["accelerators"][0]["groups"][0]["csrs"][4]["offset"] = 8
        self.fails(snax_cfg.CfgTargetError, "gen.args: rows 2; only an accumulating Mac has a "
                   "bank (set accumulate true, or rows 1)", rw=7)
        self.acc = acc_json(BICG4)
        self.unit("mac")["params"]["rows"] = 0
        self.fails(snax_cfg.CfgTargetError, "gen.args: rows 0; a bank has one row or more")

    def test_rows_csr(self):
        """ROWS is there exactly with a bank, after JOB_BEATS, of the bits of rows."""
        self.unit("mac")["csrs"][1]["width"] = 3
        self.fails(snax_cfg.CfgSlotError, "ROWS: width 3; a bank of 8 rows has ROWS of 4 bits")
        self.acc = acc_json(BICG4)
        csrs = self.unit("mac")["csrs"]
        csrs[0]["name"], csrs[1]["name"] = "ROWS", "JOB_BEATS"
        self.fails(snax_cfg.CfgSlotError, "a unit's own CSRs are ['JOB_BEATS', 'ROWS']")
        self.acc = acc_json(BICG4)
        del self.unit("mac")["params"]["rows"]
        del self.unit("mac")["ports"]["b"]["hold"]
        self.fails(snax_cfg.CfgSlotError, "a unit's own CSRs are ['JOB_BEATS']")

    def test_gen_hold(self):
        """A hold on a unit without a bank, on an input that is not a broadcast, on an
        output."""
        self.unit("mul")["ports"]["b"]["hold"] = True
        self.fails(snax_cfg.CfgTargetError, "gen.hold: port b is held for a bank row but is not "
                   "a broadcast input of a bank")
        self.acc = acc_json(BICG4)
        self.unit("mac")["ports"]["a"]["hold"] = True
        self.fails(snax_cfg.CfgTargetError, "gen.hold: port a is held")
        self.acc = acc_json(BICG4)
        self.unit("mac")["ports"]["out"]["hold"] = True
        self.fails(snax_cfg.CfgTypeError, "an input is held or carried")

    def test_carry(self):
        """A carry on a port that is not a seed; CARRY as wide as JOBS, there exactly with a
        carried seed."""
        self.unit("mul")["ports"]["b"]["carry"] = True
        self.fails(snax_cfg.CfgSlotError, "a unit's own CSRs are ['CARRY']")
        self.acc = acc_json(BICG4)
        self.unit("sum")["csrs"][0]["width"] = 16
        self.fails(snax_cfg.CfgSlotError, "CARRY: width 16; it counts jobs, as JOBS (32 bits)")
        self.acc = acc_json(BICG4)
        del self.unit("sum")["ports"]["seed"]["carry"]
        self.fails(snax_cfg.CfgSlotError, "a unit's own CSRs are []")

    def test_carry_not_a_seed(self):
        """A carried port that is not the seed, its unit given CARRY: gen.seed."""
        self.unit("mul")["ports"]["b"]["carry"] = True
        self.unit("mul")["csrs"] = [{"name": "CARRY", "access": "rw", "offset": 3, "width": 32}]
        self.unit("sum")["csrs"] = [{"name": "CARRY", "access": "rw", "offset": 4, "width": 32}]
        for c in self.unit("mac")["csrs"]:
            c["offset"] += 1
        group = self.acc["accelerators"][0]["groups"][0]
        group["csrs"][3]["offset"], group["csrs"][4]["offset"] = 7, 8
        self.fails(snax_cfg.CfgTargetError, "gen.seed: a carried port is a fold's seed, its "
                   "unit's own output: carry only the seed", rw=7)

    def test_a_held_port_is_not_forked(self):
        """mac.a held and forked with mul.a, both one lane for all: gen.fork (a held input
        has a reader of its own)."""
        self.unit("mac")["ports"]["a"].update({"d_in": 8, "broadcast": True, "hold": True})
        self.unit("mul")["ports"]["a"].update({"d_in": 8, "broadcast": True})
        self.fails(snax_cfg.CfgSlotError, "gen.fork: accelerator bicg_types: the fork ['mul.a', "
                   "'mac.a']: a port is held for a bank row; a held input is read by its own "
                   "reader")


class Atax(unittest.TestCase):
    """forge/atax_v4: t held over a link into the bank's broadcast b (one lane at the link), A
    forked to mul.a and, through a buffer, to mac.a (fork_links); each refused case in
    snax-forge's words (gen.link, gen.link_port, gen.fork)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "atax_v4"
        shutil.copytree(FORGE / "atax_v4", self.dir)
        self.acc = json.loads((self.dir / "accelerator.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        (self.dir / "accelerator.json").write_text(json.dumps(self.acc))
        (slot,) = snax_cfg.load(self.dir / "snax_forge.hjson").cores[0].accelerators
        return slot.description

    def fails(self, kind, text):
        with self.assertRaises(kind) as ctx:
            self.load()
        self.assertIn(text, ctx.exception.why)

    def group(self):
        return self.acc["accelerators"][0]["groups"][0]

    def test_read(self):
        (acc,) = self.load().accelerators
        (group,) = acc.groups
        self.assertEqual(acc.forks, [["mul.a", "mac.a"]])
        self.assertEqual(group.fork_links, [ForkLink("A", "mac.a", 4)])
        self.assertEqual(group.links[1], Link("tmp1", "sum.out", "mac.b", 1))
        b = group.units[2].ports["b"]
        self.assertEqual((b.lanes, b.stream_lanes, b.broadcast, b.hold), (4, 1, True, True))

    def test_gen_link_held(self):
        """A held link: one lane at the producer, a buffer; a broadcast linked port held."""
        self.group()["units"][1]["ports"]["out"]["lanes"] = 4
        self.fails(snax_cfg.CfgSlotError, "gen.link: group atax's link tmp1: sum.out is 4 lanes "
                   "of int32, mac.b 1 of int32; both ends are the same")
        self.acc = json.loads((FORGE / "atax_v4" / "accelerator.json").read_text())
        self.group()["links"][1]["depth"] = 0
        self.fails(snax_cfg.CfgSlotError, "gen.link: group atax's link tmp1: depth 0 into mac.b, "
                   "held for a bank row; a held link is a buffer, depth 1 or more")
        self.acc = json.loads((FORGE / "atax_v4" / "accelerator.json").read_text())
        del self.group()["units"][2]["ports"]["b"]["hold"]
        self.fails(snax_cfg.CfgSlotError, "sum.out is 1 lanes of int32, mac.b 4 of int32")
        self.group()["units"][1]["ports"]["out"]["lanes"] = 4
        self.fails(snax_cfg.CfgSlotError, "mac.b is a broadcast; a linked port takes its lanes "
                   "from the link, so it is not one unless held for a bank row")

    def test_gen_link_fork(self):
        """A fork link to the fork's reader's port, to a port of no fork, of depth 0."""
        for to in ("mul.a", "mul.b"):
            self.acc = json.loads((FORGE / "atax_v4" / "accelerator.json").read_text())
            self.group()["fork_links"][0]["to"] = to
            with self.subTest(to=to):
                self.fails(snax_cfg.CfgSlotError, f"gen.link: group atax's fork link A goes to "
                           f"{to}; a fork's buffered branch goes to a forked port of the group, "
                           "not its reader's first")
        self.acc = json.loads((FORGE / "atax_v4" / "accelerator.json").read_text())
        self.group()["fork_links"][0]["depth"] = 0
        self.fails(snax_cfg.CfgSlotError, "gen.link: depth 0; a fork's branch is a buffer, depth "
                   "1 or more")

    def test_gen_fork_without_its_buffer(self):
        """mac.a forked with no fork link: mac is fed by a link, so not a chain's head."""
        del self.group()["fork_links"]
        self.fails(snax_cfg.CfgSlotError, "gen.fork: accelerator atax: the fork ['mul.a', "
                   "'mac.a']: mac.a's unit is fed by a link; a fork feeds the heads of chains")


class Dot1(unittest.TestCase):
    """dot 1: two accelerators vmul and vsum in two streamer
    sets; dot_v1_1, the two as one accelerator dot of two groups, one set."""

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
        self.assertEqual([x.at for x in self.load().sets],
                         ["snax_streamer_sets[0]", "snax_streamer_sets[1]"])
        self.slot()["snax_streamer_sets"][1]["snax_num_rw_csr"] = 2
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[1].snax_num_rw_csr",
                   "2, but accelerator vsum has 3 read-write CSRs")
        self.slot()["snax_streamer_sets"][1]["snax_num_rw_csr"] = 3
        self.slot()["snax_streamer_sets"][0]["snax_num_ro_csr"] = 4
        self.fails(snax_cfg.CfgSlotError, "snax_streamer_sets[0].snax_num_ro_csr",
                   "4, but accelerator vmul has 2 read-only CSRs")

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
