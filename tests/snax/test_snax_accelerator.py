# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_accelerator.py: the sets' CSR layout and the slot's CSR limit,
and the composite built from accelerator.json: one group (forge/vecadd_v1/), dot 1's two
accelerators in two streamer sets (test_snax_cfg's DOT1), dot_v1_1's two groups in one
(test_snax_cfg.dot_cluster), the two sharing its movers (DOT_SHARED), a
linked group (dot 4, DOT4), a seeded Mac with a broadcast input (mvt's half 2) and a group of
two chains on a forked input (bicg_v3, BICG3).
Run from snax-gvsoc after `make build` (the composite imports GVSoC's Python from
install/):

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Skipped where install/ has no GVSoC.
"""

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "install"
sys.path[:0] = [str(ROOT / "snax"), str(INSTALL / "python"), str(INSTALL / "bin"),
                str(INSTALL / "generators")]
try:
    import snax_accelerator  # noqa: E402
    from snax_accelerator import SNAX_ACC_CSR_LAST, SNAX_CSR_FIRST  # noqa: E402
    from snax_cfg import CfgTargetError, Csr  # noqa: E402
    from snax_streamer import nb_csrs  # noqa: E402
except ImportError:
    snax_accelerator = None
sys.path.insert(0, str(Path(__file__).resolve().parent))
import snax_cfg  # noqa: E402
from test_snax_cfg import (BICG3, BICG3_STREAMER, BICG4, BICG4_STREAMER, CLUSTER,  # noqa: E402
                           DOT1, DOT4, DOT4_STREAMER, SEEDED_STREAMER, STREAMER, VECADD,
                           VMUL_STREAMER, VSUM_STREAMER, Port, Unit, acc_json, accelerator,
                           dot1_cluster, dot_cluster, dot_shared_cluster, seeded, seeded_mac,
                           streamer, write_design)


def slot_of(description, *streamers):
    """A slot of description, a set per accelerator with its streamer (STREAMER for one)."""
    streamers = streamers or (STREAMER,)
    return SimpleNamespace(
        name="snax_forge", at="cores[0].snax_acc_cfg[0]", description=description,
        sets=[SimpleNamespace(name=a.name, streamer=st)
              for a, st in zip(description.accelerators, streamers)])


def with_unit_csrs(desc, k):
    """desc with k more R/W CSRs in its last accelerator's last unit (the offsets of STATUS and
    BUSY_COUNTER moved past them)."""
    *before, acc = desc.accelerators
    *groups, group = acc.groups
    base = group.csrs[0].offset
    rw = len(group.window) - 2
    unit = replace(group.units[-1], csrs=[*group.units[-1].csrs,
                                          *(Csr(f"F{i}", "rw", base + rw + i, 32)
                                            for i in range(k))])
    own = [*group.csrs[:2], replace(group.csrs[2], offset=base + rw + k),
           replace(group.csrs[3], offset=base + rw + k + 1)]
    group = replace(group, csrs=own, units=[*group.units[:-1], unit])
    return replace(desc, accelerators=[*before, replace(acc, groups=[*groups, group])])


def mappings(acc):
    """The CSR mux's windows, (first CSR, CSRs), in CSR order."""
    maps = acc.components["csr_mux"].get_property("mappings").values()
    return sorted((m["base"] // 4, m["size"] // 4) for m in maps)


@unittest.skipIf(snax_accelerator is None, "no GVSoC in install/ (run make build first)")
class Csrs(unittest.TestCase):
    """Per set its streamer's CSRs then its accelerator's, packed from 960;
    the last CSR over all sets may be at most SNAX_ACC_CSR_LAST, 0x5FD: 0x5FE and 0x5FF are
    snax_cluster's task-queue CSRs, not the accelerator's."""

    def unit_csrs_for_last(self, last):
        # dot 1's 1000 CSRs (960-999), then k more in vsum
        return last - 999

    def test_a_last_csr_on_0x5fe_is_refused(self):
        desc = with_unit_csrs(DOT1, self.unit_csrs_for_last(0x5FE))
        with self.assertRaises(CfgTargetError) as ctx:
            snax_accelerator.SnaxAccelerator.for_slot(
                slot_of(desc, VMUL_STREAMER, VSUM_STREAMER), 131072)
        self.assertIn(f"the accelerator's last CSR {0x5FE} is past {0x5FD}", ctx.exception.why)
        self.assertIn(f"(sets vmul 960-981, vsum 982-{0x5FE})", ctx.exception.why)


@unittest.skipIf(snax_accelerator is None, "no GVSoC in install/ (run make build first)")
class Built(unittest.TestCase):
    """The composite's components and their properties, built on GVSoC's build path."""

    def build(self, path):
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot, 131072, path)
        return cls(None, "snax_acc0")

    def test_vecadd(self):
        """One group of one unit: shell and unit (snax_acc0/unit), the streamer streamer_acc."""
        acc = self.build(CLUSTER)
        self.assertEqual(sorted(acc.components), ["csr_mux", "shell", "streamer_acc", "unit"])
        first = SNAX_CSR_FIRST + nb_csrs(STREAMER)
        self.assertEqual(acc.components["streamer_acc"].properties["csr_base"], 960)
        self.assertEqual(acc.components["shell"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS"], "widths": [1, 32],
                          "busy_counter_width": 32})
        group = acc.components["unit"].properties
        (unit,) = group["units"]
        self.assertEqual((group["links"], group["csr_base"]), ([], first))
        self.assertEqual((unit["datapath"], unit["inputs"], unit["output"], unit["op"],
                          unit["lanes"], unit["latency"], unit["ii"], unit["span"], unit["t"]),
                         ("SimdLanes", ["acc_a", "acc_b"], "acc_out", "add", 4, 0, 1, 1,
                          1))
        self.assertEqual(unit["k"], "")  # two streams: no constant
        self.assertEqual(mappings(acc), [(960, 18), (978, 0x600 - 978)])
        self.assertEqual(acc.tcdm_port_names[:2], ["streamer_acc.reader0.lane0",
                                                   "streamer_acc.reader0.lane1"])

    def test_axpy_k1_from_its_csr(self):
        """axpy: the shell's R/W CSRs START, JOBS, K1 (32 bits), sent with each start; the unit
        at op axpby, k1 read from its CSR (one word), nothing baked."""
        acc = self.build(CLUSTER.parent.parent / "axpy_v1" / "snax_forge.hjson")
        shell = acc.components["shell"].properties
        self.assertEqual((shell["csrs"], shell["widths"]), (["START", "JOBS", "K1"], [1, 32, 32]))
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual((unit["datapath"], unit["inputs"], unit["op"], unit["k"], unit["k1"],
                          unit["k2"], unit["scalars"], unit["in_widths"], unit["op_width"]),
                         ("SimdLanes", ["acc_a", "acc_b"], "axpby", "", "", "", [["k1", 1]],
                          [32, 32], 32))
        with tempfile.TemporaryDirectory() as tmp:
            baked = self.build(write_design(Path(tmp), acc_json(accelerator("axpy_v1_1", Unit(
                "acc", "simd", "SimdLanes",
                {p: Port(p, "int32", 4, "out" if p == "out" else "in") for p in ("a", "b", "out")},
                "int32", {"op": "axpby", "k1": 3}, 0, 1, []))), streamer([2, 2], [2]), 2, 2))
        (unit,) = baked.components["unit"].properties["units"]
        self.assertEqual((unit["k1"], unit["scalars"]), ("3", []))
        self.assertEqual(baked.components["shell"].properties["csrs"], ["START", "JOBS"])

    def test_gray_three_inputs(self):
        """gray's SimdLanes at axpbypcz: three inputs, k1 and k2 and d baked (decimal), k3 read
        from its CSR (one word), the slots the op has none of empty."""
        with tempfile.TemporaryDirectory() as tmp:
            acc = self.build(write_design(Path(tmp), acc_json(accelerator("gray_v1", Unit(
                "acc", "simd", "SimdLanes",
                {p: Port(p, "uint8", 8, "out" if p == "out" else "in")
                 for p in ("a", "b", "c", "out")},
                "uint16", {"op": "axpbypcz", "k1": 77, "k2": 150, "d": 256}, 0, 1,
                [Csr("K3", "rw", 2, 16, "k3")], scalars={"k3": "uint16"}), between=1)),
                streamer([1, 1, 1], [1]), 3, 2))
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual(
            (unit["inputs"], unit["op"], *(unit[s] for s in ("k", "k1", "k2", "k3", "d", "lo",
                                                              "hi")), unit["scalars"]),
            (["acc_a", "acc_b", "acc_c"], "axpbypcz", "", "77", "150", "", "256", "", "",
             [["k3", 1]]))

    def test_relu_one_stream(self):
        """relu: SimdLanes with one input, op max, its constant k "0" passed to SnaxGroup."""
        unit = Unit("acc", "simd", "SimdLanes",
                    {p: Port(p, "int32", 4, "out" if p == "out" else "in") for p in ("a", "out")},
                    "int32", {"op": "max", "k": 0}, 0, 1, [])
        with tempfile.TemporaryDirectory() as tmp:
            acc = self.build(write_design(Path(tmp), acc_json(accelerator("relu_v1", unit)),
                                          streamer([2], [2]), 2, 2))
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual((unit["datapath"], unit["inputs"], unit["output"], unit["op"], unit["k"],
                          unit["in_widths"], unit["op_width"], unit["lanes"]),
                         ("SimdLanes", ["acc_a"], "acc_out", "max", "0", [32], 32, 4))

    def test_dot_1_two_sets(self):
        """dot 1: a streamer per set at its base, a shell per accelerator after it."""
        with tempfile.TemporaryDirectory() as tmp:
            acc = self.build(dot1_cluster(Path(tmp)))
        self.assertEqual(sorted(acc.components),
                         ["csr_mux", "shell_vmul", "shell_vsum", "streamer_vmul",
                          "streamer_vsum", "unit_vmul", "unit_vsum"])
        self.assertEqual([acc.components[n].properties["csr_base"]
                          for n in ("streamer_vmul", "shell_vmul", "unit_vmul",
                                    "streamer_vsum", "shell_vsum", "unit_vsum")],
                         [960, 978, 978, 982, 995, 995])
        self.assertEqual(acc.components["shell_vsum"].properties["csrs"],
                         ["START", "JOBS", "JOB_BEATS"])
        # The windows: vmul's streamer, its shell up to vsum's streamer, vsum's streamer, its
        # shell to the last SNAX CSR
        self.assertEqual(mappings(acc), [(960, 18), (978, 4), (982, 13), (995, 0x600 - 995)])
        # The TCDM ports set after set: vmul's 12, then vsum's 5
        self.assertEqual(acc.nb_tcdm_ports, 17)
        self.assertEqual((acc.tcdm_port_names[11], acc.tcdm_port_names[12],
                          acc.tcdm_port_names[16]),
                         ("streamer_vmul.writer0.lane3", "streamer_vsum.reader0.lane0",
                          "streamer_vsum.writer0.lane0"))
        (total,) = acc.components["unit_vsum"].properties["units"]
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["t"]),
                         ("TreeAccumulate", ["vsum_a"], "vsum_out", 0))

    def test_dot_1_enc_one_set(self):
        """dot_v1_1: one streamer, a shell per group at its window, a group per unit, named
        after them."""
        with tempfile.TemporaryDirectory() as tmp:
            path = dot_cluster(Path(tmp))
            (slot,) = snax_cfg.load(path).cores[0].accelerators
            acc = self.build(path)
        self.assertEqual(sorted(acc.components), ["csr_mux", "shell_vmul", "shell_vsum",
                                                  "streamer_dot", "unit_vmul", "unit_vsum"])
        first = SNAX_CSR_FIRST + nb_csrs(slot.sets[0].streamer)
        self.assertEqual(first, 988)
        self.assertEqual(acc.components["shell_vmul"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS"], "widths": [1, 32],
                          "busy_counter_width": 32})
        self.assertEqual(acc.components["shell_vsum"].properties,
                         {"csr_base": first + 4, "csrs": ["START", "JOBS", "JOB_BEATS"],
                          "widths": [1, 32, 32], "busy_counter_width": 32})
        (mul,), (total,) = (acc.components[n].properties["units"]
                            for n in ("unit_vmul", "unit_vsum"))
        self.assertEqual((mul["datapath"], mul["inputs"], mul["op"], mul["t"]),
                         ("SimdLanes", ["vmul_a", "vmul_b"], "mul", 1))
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["op"],
                          total["lanes"], total["latency"], total["t"]),
                         ("TreeAccumulate", ["vsum_a"], "vsum_out", "add", 4, 1, 0))
        self.assertEqual(acc.components["unit_vsum"].properties["csr_base"], first + 4)
        self.assertEqual(mappings(acc), [(960, 28), (988, 4), (992, 0x600 - 992)])
        self.assertEqual(snax_accelerator.component_names(slot.description),
                         ({"vmul": "shell_vmul", "vsum": "shell_vsum"},
                          {"vmul": "unit_vmul", "vsum": "unit_vsum"}))

    def test_dot_1_shared(self):
        """dot 1 shared: one streamer of three movers, the mux port_mux_dot between them and the
        groups' ports, PORT_MUX_SEL after vsum's window to the last SNAX CSR."""
        with tempfile.TemporaryDirectory() as tmp:
            path = dot_shared_cluster(Path(tmp))
            (slot,) = snax_cfg.load(path).cores[0].accelerators
            acc = self.build(path)
        self.assertEqual(sorted(acc.components),
                         ["csr_mux", "port_mux_dot", "shell_vmul", "shell_vsum", "streamer_dot",
                          "unit_vmul", "unit_vsum"])
        # The streamer: 5 + 5 + 6 CSRs (writer0's ENABLED_CHANNEL), start, busy, counter
        self.assertEqual(nb_csrs(slot.sets[0].streamer), 19)
        first = SNAX_CSR_FIRST + 19
        self.assertEqual(acc.components["port_mux_dot"].properties, {
            "csr_base": first + 9, "sel_width": 1, "groups": ["vmul", "vsum"],
            "movers": [{"name": "reader0", "is_reader": True, "num_channel": 4},
                       {"name": "reader1", "is_reader": True, "num_channel": 4},
                       {"name": "writer0", "is_reader": False, "num_channel": 4}],
            "users": [{"name": "vmul.a", "group": 0, "mover": 0, "num_channel": 4},
                      {"name": "vsum.a", "group": 1, "mover": 0, "num_channel": 4},
                      {"name": "vmul.b", "group": 0, "mover": 1, "num_channel": 4},
                      {"name": "vmul.out", "group": 0, "mover": 2, "num_channel": 4},
                      {"name": "vsum.out", "group": 1, "mover": 2, "num_channel": 1}]})
        # vsum's window ends at PORT_MUX_SEL, which goes to the mux, up to the last SNAX CSR
        self.assertEqual(mappings(acc), [(960, 19), (first, 4), (first + 4, 5),
                                         (first + 9, 0x600 - first - 9)])
        self.assertEqual((acc.nb_tcdm_ports, acc.tcdm_port_names[8], acc.tcdm_port_names[11]),
                         (12, "streamer_dot.writer0.lane0", "streamer_dot.writer0.lane3"))
        binds = {(m.name, mi, s.name, si) for m, mi, s, si, *_ in acc.bindings}
        self.assertLessEqual({
            ("unit_vmul", "vmul_a", "port_mux_dot", "port_0"),
            ("unit_vsum", "vsum_a", "port_mux_dot", "port_1"),
            ("unit_vmul", "vmul_b", "port_mux_dot", "port_2"),
            ("unit_vmul", "vmul_out", "port_mux_dot", "port_3"),
            ("unit_vsum", "vsum_out", "port_mux_dot", "port_4"),
            ("port_mux_dot", "mover_0", "streamer_dot", "reader_0"),
            ("port_mux_dot", "mover_1", "streamer_dot", "reader_1"),
            ("port_mux_dot", "mover_2", "streamer_dot", "writer_0"),
            ("streamer_dot", "busy", "port_mux_dot", "busy"),
        }, binds)
        # No group port reaches the streamer past the mux
        self.assertFalse([b for b in binds if b[2] == "streamer_dot" and b[0] != "port_mux_dot"
                          and b[3].startswith(("reader", "writer"))])

    def test_dot4_one_linked_group(self):
        """dot 4: one shell and one group_dot over its window (START, JOBS, the MAC's
        JOB_BEATS, STATUS, BUSY_COUNTER), the MAC's outer inputs and the sum's outer output, the
        wire between them; the sum's T fixed at 1 (params.T), the MAC's from the start."""
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(DOT4, DOT4_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        self.assertEqual(sorted(acc.components), ["csr_mux", "group_dot", "shell_dot",
                                                  "streamer_dot"])
        first = SNAX_CSR_FIRST + nb_csrs(DOT4_STREAMER)
        self.assertEqual(acc.components["shell_dot"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS", "JOB_BEATS"],
                          "widths": [1, 32, 32], "busy_counter_width": 32})
        group = acc.components["group_dot"].properties
        mac, total = group["units"]
        self.assertEqual((group["links"], group["csr_base"]),
                         ([{"from": "mac", "to": "sum", "to_input": 0, "depth": 0}], first))
        self.assertEqual((mac["datapath"], mac["inputs"], mac["output"], mac["accumulate"],
                          mac["reg_out"], mac["latency"], mac["t"], mac["op_width"]),
                         ("Mac", ["mac_a", "mac_b"], "", True, False, 1, 0, 64))
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["span"],
                          total["t"]), ("TreeAccumulate", [""], "sum_out", 1, 1))
        self.assertEqual((mac["seed"], total["seed"]), (-1, -1))
        self.assertEqual(snax_accelerator.component_names(DOT4), ({"dot": "shell_dot"},
                                                               {"dot": "group_dot"}))
        # The window: five CSRs, the last at first + 4
        self.assertEqual(len(DOT4.csrs), 5)

    def test_a_seeded_fold(self):
        """matvec_acc_v1's sum: its inputs a and its seed, both outer, the seed's
        index 1 (SnaxGroup's seed: the last input, one element in one word)."""
        desc = accelerator("matvec_acc_v1", seeded(), between=1)
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(desc, SEEDED_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual((unit["datapath"], unit["inputs"], unit["seed"], unit["in_widths"],
                          unit["lanes"], unit["output"]),
                         ("TreeAccumulate", ["acc_a", "acc_seed"], 1, [64, 64], 4, "acc_out"))

    def test_a_seeded_mac_with_a_broadcast(self):
        """mvt's half 2: a Mac of 8 int8 lanes, b broadcast through a slicer of 8 pops, its
        seed of the output's 8 int32 lanes the last input."""
        b = Port("b", "int8", 8, "in", d_in=8, broadcast=True)
        desc = accelerator("mac_bcast", seeded_mac(8, "int8", "int32", b), between=1)
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(desc, streamer([1, 1, 4], [4])),
                                                        131072)
        acc = cls(None, "snax_acc0")
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual((unit["datapath"], unit["inputs"], unit["seed"], unit["in_widths"],
                          unit["lanes"], unit["d_in"], unit["broadcast"]),
                         ("Mac", ["acc_a", "acc_b", "acc_seed"], 2, [8, 8, 32], 8, [1, 8, 1],
                          [False, True, False]))

    def test_a_forked_input(self):
        """bicg_v3: A's reader, the streamer's reader 0, on mul_a, which mac's a takes
        too; r's on mac_b, p's on mul_b; each sink its own output; the shell's JOBS_SUM and
        JOBS_MAC after START."""
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(BICG3, BICG3_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        self.assertEqual(sorted(acc.components), ["csr_mux", "group_bicg_types",
                                                  "shell_bicg_types", "streamer_bicg_types"])
        first = SNAX_CSR_FIRST + nb_csrs(BICG3_STREAMER)
        self.assertEqual(acc.components["shell_bicg_types"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS_SUM", "JOBS_MAC",
                                                      "JOB_BEATS", "JOB_BEATS"],
                          "widths": [1, 32, 32, 32, 32], "busy_counter_width": 32})
        group = acc.components["group_bicg_types"].properties
        mul, total, mac = group["units"]
        self.assertEqual([(u["inputs"], u["output"]) for u in (mul, total, mac)],
                         [(["mul_a", "mul_b"], ""), ([""], "sum_out"),
                          (["mul_a", "mac_b"], "mac_out")])
        self.assertEqual((mac["d_in"], mac["broadcast"], total["d_out"]),
                         ([1, 8], [False, True], 2))
        self.assertEqual(group["links"], [{"from": "mul", "to": "sum", "to_input": 0,
                                           "depth": 1}])

    def test_a_bank_a_hold_and_a_carry(self):
        """bicg_v4_1: the Mac's rows and r held, the sum's seed carried;
        the shell's CARRY, JOB_BEATS and ROWS after the JOBS, in CSR order."""
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(BICG4, BICG4_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        shell = acc.components["shell_bicg_types"].properties
        self.assertEqual((shell["csrs"], shell["widths"]),
                         (["START", "JOBS_SUM", "JOBS_MAC", "CARRY", "JOB_BEATS", "ROWS"],
                          [1, 32, 32, 32, 32, 4]))
        mul, total, mac = acc.components["group_bicg_types"].properties["units"]
        self.assertEqual([(u["rows"], u["hold"], u["carry"]) for u in (mul, total, mac)],
                         [(1, [False, False], False), (1, [False, False], True),
                          (8, [False, True], False)])
        self.assertEqual((total["inputs"], total["seed"], total["t"]), (["", "sum_seed"], 1, 8))


    def test_a_held_link_and_a_fork_link(self):
        """forge/atax_v4: sum's t over a held link into mac's b (its buffer of one lane), A
        forked to mul.a and through a buffer of 4 to mac.a, which is fed ("", no slicer of its
        own); fork_links only on such a group."""
        cfg = snax_cfg.load(Path(__file__).resolve().parents[2] / "forge" / "atax_v4" /
                            "snax_forge.hjson")
        (slot,) = cfg.cores[0].accelerators
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot, 131072)
        group = cls(None, "snax_acc0").components["group_atax"].properties
        mul, total, mac = group["units"]
        self.assertEqual([(u["inputs"], u["d_in"]) for u in (mul, total, mac)],
                         [(["mul_a", "mul_b"], [2, 2]), ([""], [1]), (["", ""], [1, 1])])
        self.assertEqual((mac["broadcast"], mac["hold"], mac["rows"]),
                         ([False, True], [False, True], 2))
        self.assertEqual(group["links"], [
            {"from": "mul", "to": "sum", "to_input": 0, "depth": 1},
            {"from": "sum", "to": "mac", "to_input": 1, "depth": 1, "hold": True}])
        self.assertEqual(group["fork_links"], [{"fork": "mul_a", "to": "mac", "to_input": 0,
                                                "depth": 4}])
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(BICG4, BICG4_STREAMER), 131072)
        self.assertNotIn("fork_links",
                         cls(None, "snax_acc0").components["group_bicg_types"].properties)


if __name__ == "__main__":
    unittest.main()
