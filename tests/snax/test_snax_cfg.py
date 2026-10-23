# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_cfg.py. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Reads the three cluster files of sw/cfg/ and forge/'s fixtures, then
broken copies of snax_alu_cluster.hjson (written as JSON into a temporary
folder) and a cluster file with its slot's streamer and datapath in an
accelerator file.
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "snax"))
import hjson  # noqa: E402
import snax_cfg  # noqa: E402

CFG = ROOT / "sw" / "cfg"
FORGE = ROOT / "forge"

# snax_alu_streamer_template of both snax_alu files, as the hjson has it
SNAX_ALU_STREAMER = {
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
    "snax_library_name": "snax-alu",
}

MISA_RV32IMA = (1 << 30) | (1 << 12) | (1 << 8) | (1 << 0)


def sparse():
    """snax_alu_cluster.hjson, parsed, $refs not resolved."""
    return hjson.loads((CFG / "snax_alu_cluster.hjson").read_text())


class SwCfg(unittest.TestCase):
    """The three cluster files of sw/cfg/."""

    def check_snax_alu(self, cfg):
        self.assertEqual(cfg.name, "snax_alu_cluster")
        self.assertEqual(cfg.boot_addr, 0x1000)
        self.assertEqual(cfg.base, 0x1000_0000)
        self.assertEqual((cfg.tcdm.size, cfg.tcdm.banks, cfg.tcdm.bank_width),
                         (128 * 1024, 32, 8))
        self.assertEqual((cfg.periph_size, cfg.zero_mem_size), (64 * 1024, 64 * 1024))
        self.assertEqual(cfg.dma, snax_cfg.Dma(512, 3, 3))
        self.assertEqual(cfg.dram, snax_cfg.Dram(0x8000_0000, 0x8000_0000))
        self.assertEqual(len(cfg.hives), 1)
        compute, dma = cfg.cores
        self.assertEqual((compute.isa, compute.xdma, compute.num_int_outstanding_loads),
                         ("rv32ima", False, 1))
        self.assertEqual((dma.isa, dma.xdma, dma.accelerators), ("rv32ima", True, []))
        self.assertEqual(compute.misa, MISA_RV32IMA)
        (slot,) = compute.accelerators
        self.assertEqual(slot.name, "snax_alu")
        self.assertEqual((slot.tcdm_ports, slot.num_rw_csr, slot.num_ro_csr), (12, 3, 2))
        self.assertEqual(slot.streamer, SNAX_ALU_STREAMER)
        self.assertIsNone(slot.datapath)
        return slot

    def test_old(self):
        cfg = snax_cfg.load(CFG / "snax_alu_cluster_old.hjson")
        slot = self.check_snax_alu(cfg)
        self.assertFalse(cfg.tcdm.sparse_interconnect)
        self.assertEqual((slot.narrow_tcdm_ports, slot.wide_tcdm_ports, slot.sparse_config),
                         (12, 0, None))

    def test_sparse(self):
        cfg = snax_cfg.load(CFG / "snax_alu_cluster.hjson")
        slot = self.check_snax_alu(cfg)
        self.assertTrue(cfg.tcdm.sparse_interconnect)
        self.assertEqual((slot.narrow_tcdm_ports, slot.wide_tcdm_ports, slot.sparse_config),
                         (None, None, [[12, 1]]))

    def test_snitch(self):
        cfg = snax_cfg.load(CFG / "snitch_cluster.hjson")
        self.assertEqual(cfg.name, "snitch_cluster")
        self.assertEqual(len(cfg.cores), 9)
        self.assertEqual([core.xdma for core in cfg.cores], [False] * 8 + [True])
        self.assertTrue(all(core.accelerators == [] for core in cfg.cores))
        self.assertEqual(cfg.cores[0].misa, (1 << 30) | sum(1 << (ord(c) - ord("a"))
                                                             for c in "imafd"))


class Fixtures(unittest.TestCase):
    """forge/'s cluster files: snax_alu_cluster.hjson renamed snax_forge_cluster, its slot
    snax_forge set for the design."""

    def slot(self, design):
        cfg = snax_cfg.load(FORGE / design / "snax_forge.hjson")
        self.assertEqual(cfg.name, "snax_forge_cluster")
        self.assertTrue(cfg.tcdm.sparse_interconnect)
        (slot,) = cfg.cores[0].accelerators
        self.assertEqual(slot.name, "snax_forge")
        return slot

    def test_vecadd_vecmul(self):
        for design, op in (("vecadd", 0), ("vecmul", 2)):
            slot = self.slot(design)
            self.assertEqual((slot.tcdm_ports, slot.sparse_config, slot.num_rw_csr),
                             (12, [[12, 1]], 2))
            self.assertEqual(slot.streamer, {k: v for k, v in SNAX_ALU_STREAMER.items()
                                             if k != "snax_library_name"})
            self.assertEqual(slot.datapath, snax_cfg.Datapath(
                "SnaxUnit", ["a", "b"], ["out"], 4, 64, op, True, "counted", "lockstep", 0, 1,
                ["count"], ["loopCount"]))

    def test_vsum(self):
        slot = self.slot("vsum")
        self.assertEqual((slot.tcdm_ports, slot.sparse_config, slot.num_rw_csr), (2, [[2, 1]], 3))
        self.assertEqual(slot.datapath, snax_cfg.Datapath(
            "SnaxUnit", ["a"], ["out"], 1, 64, 0, True, "counted", "pipelined", 1, 1,
            ["count", "rate"], ["loopCount", "len"]))


class Misa(unittest.TestCase):
    def test_strings(self):
        self.assertEqual(snax_cfg.misa("rv32ima"), MISA_RV32IMA)
        self.assertEqual(snax_cfg.misa("RV32G"), snax_cfg.misa("rv32imafd"))
        self.assertEqual(snax_cfg.misa("rv64i"), (2 << 62) | (1 << 8))
        for bad in ("rv16i", "x86", "rv32i2p0"):
            with self.assertRaises(ValueError):
                snax_cfg.misa(bad)


class Broken(unittest.TestCase):
    """Copies of snax_alu_cluster.hjson with one thing wrong, each a named error."""

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
        return d["snax_alu_core_template"]["snax_acc_cfg"][0]

    def test_parse(self):
        self.fails(snax_cfg.CfgParseError, "{ cluster: ", "")
        self.fails(snax_cfg.CfgParseError, "[1, 2]", "", "must be an object")
        with self.assertRaises(snax_cfg.CfgParseError):
            snax_cfg.load(self.dir / "none.hjson")

    def test_ref_missing_key(self):
        d = sparse()
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/no_such_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_acc_cfg[0].snax_streamer_cfg",
                   "no 'no_such_template'")

    def test_ref_missing_file(self):
        d = sparse()
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "acc.hjson#/snax_streamer_cfg"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")

    def test_ref_malformed(self):
        d = sparse()
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/snax_alu_streamer_template", "x": 1}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "is not")
        # A key without #/ is a whole file's name: no such file
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "snax_alu_streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "no file")
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#snax_alu_streamer_template"}
        self.fails(snax_cfg.CfgRefError, d, "snax_streamer_cfg", "must start with /")

    def test_ref_cycle(self):
        d = sparse()
        d["loop"] = {"a": {"$ref": "#/loop"}}
        self.slot(d)["snax_streamer_cfg"] = {"$ref": "#/loop"}
        self.fails(snax_cfg.CfgRefError, d, "loop", "refers to itself")

    def test_missing_key(self):
        d = sparse()
        del d["cluster"]["tcdm"]["banks"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.tcdm.banks", "missing")
        d = sparse()
        del self.slot(d)["snax_num_rw_csr"]
        self.fails(snax_cfg.CfgKeyError, d, "cluster.hives[0].cores[0].snax_acc_cfg[0]"
                   ".snax_num_rw_csr", "missing")

    def test_wrong_type(self):
        d = sparse()
        d["cluster"]["tcdm"]["banks"] = "32"
        self.fails(snax_cfg.CfgTypeError, d, "cluster.tcdm.banks", "an integer")
        d = sparse()
        d["cluster"]["dma_data_width"] = True
        self.fails(snax_cfg.CfgTypeError, d, "cluster.dma_data_width", "an integer")
        d = sparse()
        d["cluster"]["tcdm"]["sparse_interconnect"] = 1
        self.fails(snax_cfg.CfgTypeError, d, "cluster.tcdm.sparse_interconnect", "a boolean")
        d = sparse()
        self.slot(d)["sparse_interconnect_config"] = [[12]]
        self.fails(snax_cfg.CfgTypeError, d, "sparse_interconnect_config[0]",
                   "[width, granularity]")
        d = sparse()
        d["cluster"]["hives"][0]["cores"][1] = "dma"
        self.fails(snax_cfg.CfgTypeError, d, "cluster.hives[0].cores[1]", "an object")

    def test_slot_ports(self):
        d = sparse()
        self.slot(d)["snax_tcdm_ports"] = 8
        self.fails(snax_cfg.CfgSlotError, d, "snax_tcdm_ports", "12 channels")
        d = sparse()
        self.slot(d)["sparse_interconnect_config"] = [[8, 1], [8, 1]]
        self.fails(snax_cfg.CfgSlotError, d, "sparse_interconnect_config", "add up to 16")
        d = sparse()
        self.slot(d)["snax_narrow_tcdm_ports"] = 8
        self.slot(d)["snax_wide_tcdm_ports"] = 0
        self.fails(snax_cfg.CfgSlotError, d, "snax_narrow_tcdm_ports", "narrow 8 + wide 0")

    def test_reader_writer_refused(self):
        """snax_cluster's data_reader_writer_params: no mover of the model's streamer."""
        d = sparse()
        d["snax_alu_streamer_template"]["data_reader_writer_params"] = {
            "spatial_bounds": [[4]], "temporal_dim": [1], "num_channel": [4], "fifo_depth": [8]}
        self.fails(snax_cfg.CfgTargetError, d, "snax_streamer_cfg.data_reader_writer_params",
                   "not modelled")


class AccFile(unittest.TestCase):
    """A slot's streamer and datapath in an accelerator file next to the cluster file."""

    DATAPATH = {"unit": "SnaxUnit", "inputs": ["a", "b"], "outputs": ["out"], "lanes": 4,
                "data_width": 64, "op": 0, "signed": True, "control": "counted",
                "wait": "lockstep", "latency": 0, "ii": 1, "fields": ["loopCount"]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cluster = sparse()
        slot = self.cluster["snax_alu_core_template"]["snax_acc_cfg"][0]
        slot["snax_streamer_cfg"] = {"$ref": "acc/snax_alu_acc.hjson#/snax_streamer_cfg"}
        slot["snax_datapath_cfg"] = {"$ref": "acc/snax_alu_acc.hjson#/datapath"}
        slot["snax_num_rw_csr"] = 2
        # The accelerator file's own ref resolves in that file
        self.acc = {"template": copy.deepcopy(SNAX_ALU_STREAMER),
                    "snax_streamer_cfg": {"$ref": "#/template"},
                    "datapath": copy.deepcopy(self.DATAPATH)}

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        (self.dir / "acc").mkdir(exist_ok=True)
        (self.dir / "acc" / "snax_alu_acc.hjson").write_text(json.dumps(self.acc))
        (self.dir / "snax_alu.hjson").write_text(json.dumps(self.cluster))
        return snax_cfg.load(self.dir / "snax_alu.hjson")

    def test_resolved(self):
        (slot,) = self.load().cores[0].accelerators
        self.assertEqual(slot.streamer, SNAX_ALU_STREAMER)
        self.assertEqual(slot.datapath, snax_cfg.Datapath(**self.DATAPATH, config=["count"]))

    def fails(self, error, path_part, why_part=""):
        with self.assertRaises(error) as ctx:
            self.load()
        self.assertIn(path_part, ctx.exception.path)
        self.assertIn(why_part, ctx.exception.why)

    def test_datapath_ports(self):
        self.acc["datapath"]["inputs"] = ["a"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.inputs", "2 data_reader_params")
        self.acc["datapath"]["inputs"] = ["a", "b"]
        self.acc["datapath"]["outputs"] = ["out", "out2"]
        self.fails(snax_cfg.CfgSlotError, "snax_datapath_cfg.outputs", "1 data_writer_params")

    def test_datapath_keys(self):
        del self.acc["datapath"]["wait"]
        self.fails(snax_cfg.CfgKeyError, "snax_datapath_cfg.wait", "missing")
        self.acc["datapath"]["wait"] = "lockstep"
        self.acc["datapath"]["signed"] = "yes"
        self.fails(snax_cfg.CfgTypeError, "snax_datapath_cfg.signed", "a boolean")
        self.acc["datapath"]["signed"] = True
        self.acc["datapath"]["fields"] = ["loopCount", 3]
        self.fails(snax_cfg.CfgTypeError, "snax_datapath_cfg.fields", "list of strings")

    def test_rw_csrs(self):
        self.acc["datapath"]["fields"] = ["loopCount", "len"]
        with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
            self.load()
        self.assertIn("snax_num_rw_csr", ctx.exception.path)
        self.assertIn("2 shell fields", ctx.exception.why)

    def test_ro_csrs(self):
        self.cluster["snax_alu_core_template"]["snax_acc_cfg"][0]["snax_num_ro_csr"] = 3
        with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
            self.load()
        self.assertIn("snax_num_ro_csr", ctx.exception.path)

    def test_channels(self):
        self.acc["template"]["data_writer_params"]["num_channel"] = [2]
        with self.assertRaises(snax_cfg.CfgSlotError) as ctx:
            self.load()
        self.assertIn("10 channels", ctx.exception.why)

    def test_whole_files(self):
        """snax-forge's writer: the streamer file and the accelerator file, each the whole
        file, with or without a trailing #."""
        slot = self.cluster["snax_alu_core_template"]["snax_acc_cfg"][0]
        slot["snax_streamer_cfg"] = {"$ref": "acc/snax_alu_streamer.hjson"}
        slot["snax_datapath_cfg"] = {"$ref": "acc/snax_alu_acc.hjson#"}
        (self.dir / "acc").mkdir(exist_ok=True)
        (self.dir / "acc" / "snax_alu_streamer.hjson").write_text(json.dumps(SNAX_ALU_STREAMER))
        self.acc = self.DATAPATH
        (slot_cfg,) = self.load().cores[0].accelerators
        self.assertEqual(slot_cfg.streamer, SNAX_ALU_STREAMER)
        self.assertEqual(slot_cfg.datapath, snax_cfg.Datapath(**self.DATAPATH, config=["count"]))

    def test_bad_whole_file_refs(self):
        slot = self.cluster["snax_alu_core_template"]["snax_acc_cfg"][0]
        for ref, why in (("acc/none.hjson", "no file"), ("#", "is not"), ("", "is not")):
            slot["snax_datapath_cfg"] = {"$ref": ref}
            with self.assertRaises(snax_cfg.CfgRefError) as ctx:
                self.load()
            self.assertIn(why, ctx.exception.why)

    def test_bad_pointer(self):
        self.cluster["snax_alu_core_template"]["snax_acc_cfg"][0]["snax_datapath_cfg"] = \
            {"$ref": "acc/snax_alu_acc.hjson#/no_datapath"}
        with self.assertRaises(snax_cfg.CfgRefError) as ctx:
            self.load()
        self.assertIn("snax_alu_acc.hjson", ctx.exception.why)


if __name__ == "__main__":
    unittest.main()
