# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_accelerator.py: the sets' CSR layout and the slot's CSR limit,
and the composite built from accelerator.json: one group (forge/vecadd/), dot 1's two
accelerators in two streamer sets (test_snax_cfg's DOT1), dot_1_enc's two groups in one
(test_snax_cfg.dot_cluster) and a linked group (dot 4, DOT4).
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
from test_snax_cfg import (CLUSTER, DOT1, DOT4, DOT4_STREAMER, STREAMER,  # noqa: E402
                           VECADD, VMUL_STREAMER, VSUM_STREAMER, dot1_cluster, dot_cluster)


def slot_of(description, *streamers):
    """A slot of description, a set per accelerator with its streamer (STREAMER for one)."""
    streamers = streamers or (STREAMER,)
    return SimpleNamespace(
        name="snax_forge", at="cores[0].snax_acc_cfg[0]", description=description,
        sets=[SimpleNamespace(name=a.name, streamer=st)
              for a, st in zip(description.accelerators, streamers)])


def with_unit_csrs(desc, k):
    """desc with k more R/W CSRs in its last accelerator's last unit (the offsets of STATUS and
    COUNTER moved past them)."""
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
    """Per set its streamer's CSRs then its accelerator's, packed from 960 (snax-forge D157);
    the last CSR over all sets may be at most SNAX_ACC_CSR_LAST, 0x5FD: 0x5FE and 0x5FF are
    snax_cluster's task-queue CSRs, not the accelerator's."""

    def test_dot_1s_bases(self):
        """vmul: streamer 960-977, CSRs 978-981; vsum: streamer 982-994, CSRs 995-999."""
        layout = snax_accelerator.csr_layout(slot_of(DOT1, VMUL_STREAMER, VSUM_STREAMER))
        self.assertEqual([(r.name, r.first, r.own, r.end) for r in layout],
                         [("vmul", 960, 978, 982), ("vsum", 982, 995, 1000)])
        self.assertEqual([r.streamer_csrs for r in layout], [18, 13])
        vsum = layout[1]
        self.assertEqual([vsum.csr(c.offset) for c in vsum.accelerator.csrs],
                         [995, 996, 997, 998, 999])

    def test_one_set_is_as_before(self):
        """vecadd: the streamer's 18 CSRs, then START at 978."""
        (row,) = snax_accelerator.csr_layout(slot_of(VECADD))
        self.assertEqual((row.name, row.first, row.own, row.end), ("acc", 960, 978, 982))
        self.assertEqual(SNAX_CSR_FIRST + nb_csrs(STREAMER), 978)

    def unit_csrs_for_last(self, last):
        # dot 1's 1000 CSRs (960-999), then k more in vsum
        return last - 999

    def test_a_last_csr_on_0x5fd_is_taken(self):
        self.assertEqual(SNAX_ACC_CSR_LAST, 0x5FD)
        desc = with_unit_csrs(DOT1, self.unit_csrs_for_last(0x5FD))
        cls = snax_accelerator.SnaxAccelerator.for_slot(
            slot_of(desc, VMUL_STREAMER, VSUM_STREAMER), 131072)
        self.assertEqual(cls.nb_tcdm_ports, 17)
        self.assertEqual(cls.layout[-1].end - 1, 0x5FD)

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
                          "counter_width": 32})
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
        acc = self.build(CLUSTER.parent.parent / "axpy" / "snax_forge.hjson")
        shell = acc.components["shell"].properties
        self.assertEqual((shell["csrs"], shell["widths"]), (["START", "JOBS", "K1"], [1, 32, 32]))
        (unit,) = acc.components["unit"].properties["units"]
        self.assertEqual((unit["datapath"], unit["inputs"], unit["op"], unit["k"], unit["k1"],
                          unit["k2"], unit["scalars"], unit["in_widths"], unit["op_width"]),
                         ("SimdLanes", ["acc_a", "acc_b"], "axpby", "", "", "", [["k1", 1]],
                          [32, 32], 32))
        baked = self.build(CLUSTER.parent.parent / "axpy_baked" / "snax_forge.hjson")
        (unit,) = baked.components["unit"].properties["units"]
        self.assertEqual((unit["k1"], unit["scalars"]), ("3", []))
        self.assertEqual(baked.components["shell"].properties["csrs"], ["START", "JOBS"])

    def test_relu_one_stream(self):
        """relu: SimdLanes with one input, op max, its constant k "0" passed to SnaxGroup."""
        acc = self.build(CLUSTER.parent.parent / "relu" / "snax_forge.hjson")
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
        """dot_1_enc: one streamer, a shell per group at its window, a group per unit, named
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
                          "counter_width": 32})
        self.assertEqual(acc.components["shell_vsum"].properties,
                         {"csr_base": first + 4, "csrs": ["START", "JOBS", "JOB_BEATS"],
                          "widths": [1, 32, 32], "counter_width": 32})
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

    def test_dot4_one_linked_group(self):
        """dot 4: one shell and one group_dot over its window (START, JOBS, the MAC's
        JOB_BEATS, STATUS, COUNTER), the MAC's outer inputs and the sum's outer output, the
        wire between them; the sum's T fixed at 1 (params.T), the MAC's from the start."""
        cls = snax_accelerator.SnaxAccelerator.for_slot(slot_of(DOT4, DOT4_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        self.assertEqual(sorted(acc.components), ["csr_mux", "group_dot", "shell_dot",
                                                  "streamer_dot"])
        first = SNAX_CSR_FIRST + nb_csrs(DOT4_STREAMER)
        self.assertEqual(acc.components["shell_dot"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS", "JOB_BEATS"],
                          "widths": [1, 32, 32], "counter_width": 32})
        group = acc.components["group_dot"].properties
        mac, total = group["units"]
        self.assertEqual((group["links"], group["csr_base"]),
                         ([{"from": "mac", "to": "sum", "to_input": 0, "depth": 0}], first))
        self.assertEqual((mac["datapath"], mac["inputs"], mac["output"], mac["accumulate"],
                          mac["reg_out"], mac["latency"], mac["t"], mac["op_width"]),
                         ("Mac", ["mac_a", "mac_b"], "", True, False, 1, 0, 64))
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["span"],
                          total["t"]), ("TreeAccumulate", [""], "sum_out", 1, 1))
        self.assertEqual(snax_accelerator.component_names(DOT4), ({"dot": "shell_dot"},
                                                               {"dot": "group_dot"}))
        # The window: five CSRs, the last at first + 4
        self.assertEqual(len(DOT4.csrs), 5)


if __name__ == "__main__":
    unittest.main()
