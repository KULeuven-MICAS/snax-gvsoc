# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_unit_acc.py: the slot's CSR limit, and the composite built
from accelerator.json, one group (forge/vecadd/), two (dot 1, test_snax_cfg's DOT) and a
linked group (dot 4, test_snax_cfg's DOT4).
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
    import snax_unit_acc  # noqa: E402
    from snax_acc import SNAX_ACC_CSR_LAST, SNAX_CSR_FIRST  # noqa: E402
    from snax_cfg import CfgTargetError, Csr  # noqa: E402
    from snax_streamer import nb_csrs  # noqa: E402
except ImportError:
    snax_unit_acc = None
sys.path.insert(0, str(Path(__file__).resolve().parent))
import snax_cfg  # noqa: E402
from test_snax_cfg import CLUSTER, DOT4, DOT4_STREAMER, STREAMER, VECADD, dot_cluster  # noqa: E402


def slot_of(accelerator, streamer=STREAMER):
    return SimpleNamespace(name="snax_forge", at="cores[0].snax_acc_cfg[0]", streamer=streamer,
                           accelerator=accelerator)


def with_unit_csrs(k):
    """VECADD with k more R/W CSRs (the offsets of STATUS and COUNTER moved past them)."""
    group = VECADD.groups[0]
    unit = replace(group.units[0], csrs=[Csr(f"F{i}", "rw", 2 + i, 32) for i in range(k)])
    own = [*group.csrs[:2], replace(group.csrs[2], offset=2 + k),
           replace(group.csrs[3], offset=3 + k)]
    return replace(VECADD, groups=[replace(group, csrs=own, units=[unit])])


@unittest.skipIf(snax_unit_acc is None, "no GVSoC in install/ (run make build first)")
class Csrs(unittest.TestCase):
    """The accelerator's last CSR may be at most SNAX_ACC_CSR_LAST, 0x5FD: 0x5FE and 0x5FF
    are snax_cluster's task-queue CSRs, not the accelerator's."""

    def unit_csrs_for_last(self, last):
        # streamer CSRs, then START, JOBS, the unit's, STATUS and COUNTER
        return last - SNAX_CSR_FIRST - nb_csrs(STREAMER) - 4 + 1

    def test_a_last_csr_on_0x5fd_is_taken(self):
        self.assertEqual(SNAX_ACC_CSR_LAST, 0x5FD)
        acc = with_unit_csrs(self.unit_csrs_for_last(0x5FD))
        cls = snax_unit_acc.SnaxUnitAcc.for_slot(slot_of(acc), 131072)
        self.assertEqual(cls.nb_tcdm_ports, 12)

    def test_a_last_csr_on_0x5fe_is_refused(self):
        acc = with_unit_csrs(self.unit_csrs_for_last(0x5FE))
        with self.assertRaises(CfgTargetError) as ctx:
            snax_unit_acc.SnaxUnitAcc.for_slot(slot_of(acc), 131072)
        self.assertIn(f"the accelerator's last CSR {0x5FE} is past {0x5FD}", ctx.exception.why)


@unittest.skipIf(snax_unit_acc is None, "no GVSoC in install/ (run make build first)")
class Built(unittest.TestCase):
    """The composite's components and their properties, built on GVSoC's build path."""

    def build(self, path):
        (slot,) = snax_cfg.load(path).cores[0].accelerators
        cls = snax_unit_acc.SnaxUnitAcc.for_slot(slot, 131072, path)
        return cls(None, "snax_acc0")

    def test_vecadd(self):
        """One group of one unit: shell and unit (snax_acc0/unit)."""
        acc = self.build(CLUSTER)
        self.assertEqual(sorted(acc.components), ["csr_mux", "shell", "streamer", "unit"])
        first = SNAX_CSR_FIRST + nb_csrs(STREAMER)
        self.assertEqual(acc.components["shell"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS"]})
        group = acc.components["unit"].properties
        (unit,) = group["units"]
        self.assertEqual((group["links"], group["csr_base"]), ([], first))
        self.assertEqual((unit["datapath"], unit["inputs"], unit["output"], unit["op"],
                          unit["lanes"], unit["latency"], unit["ii"], unit["span"], unit["t"]),
                         ("ElementwiseLanes", ["acc_a", "acc_b"], "acc_out", "add", 4, 0, 1, 1,
                          1))

    def test_dot_two_groups(self):
        """dot 1: a shell per group at its window, a group per unit, named after them."""
        with tempfile.TemporaryDirectory() as tmp:
            path = dot_cluster(Path(tmp))
            (slot,) = snax_cfg.load(path).cores[0].accelerators
            acc = self.build(path)
        self.assertEqual(sorted(acc.components), ["csr_mux", "shell_mul", "shell_sum",
                                                  "streamer", "unit_mul", "unit_sum"])
        first = SNAX_CSR_FIRST + nb_csrs(slot.streamer)
        self.assertEqual(acc.components["shell_mul"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS"]})
        self.assertEqual(acc.components["shell_sum"].properties,
                         {"csr_base": first + 4, "csrs": ["START", "JOBS", "JOB_BEATS"]})
        (mul,), (total,) = (acc.components[n].properties["units"] for n in ("unit_mul", "unit_sum"))
        self.assertEqual((mul["datapath"], mul["inputs"], mul["op"], mul["t"]),
                         ("ElementwiseLanes", ["mul_a", "mul_b"], "mul", 1))
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["op"],
                          total["lanes"], total["latency"], total["t"]),
                         ("TreeAccumulate", ["sum_a"], "sum_out", "add", 4, 1, 0))
        self.assertEqual(acc.components["unit_sum"].properties["csr_base"], first + 4)
        self.assertEqual(snax_unit_acc.component_names(slot.accelerator),
                         ({"mul": "shell_mul", "sum": "shell_sum"},
                          {"mul": "unit_mul", "sum": "unit_sum"}))

    def test_dot4_one_linked_group(self):
        """dot 4: one shell and one group_dot over its window (START, JOBS, the MAC's
        JOB_BEATS, STATUS, COUNTER), the MAC's outer inputs and the sum's outer output, the
        wire between them; the sum's T fixed at 1 (params.T), the MAC's from the start."""
        cls = snax_unit_acc.SnaxUnitAcc.for_slot(slot_of(DOT4, DOT4_STREAMER), 131072)
        acc = cls(None, "snax_acc0")
        self.assertEqual(sorted(acc.components), ["csr_mux", "group_dot", "shell_dot",
                                                  "streamer"])
        first = SNAX_CSR_FIRST + nb_csrs(DOT4_STREAMER)
        self.assertEqual(acc.components["shell_dot"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS", "JOB_BEATS"]})
        group = acc.components["group_dot"].properties
        mac, total = group["units"]
        self.assertEqual((group["links"], group["csr_base"]),
                         ([{"from": "mac", "to": "sum", "to_input": 0, "depth": 0}], first))
        self.assertEqual((mac["datapath"], mac["inputs"], mac["output"], mac["accumulate"],
                          mac["reg_out"], mac["latency"], mac["t"], mac["op_width"]),
                         ("Mac", ["mac_a", "mac_b"], "", True, False, 1, 0, 64))
        self.assertEqual((total["datapath"], total["inputs"], total["output"], total["span"],
                          total["t"]), ("TreeAccumulate", [""], "sum_out", 1, 1))
        self.assertEqual(snax_unit_acc.component_names(DOT4), ({"dot": "shell_dot"},
                                                               {"dot": "group_dot"}))
        # The window: five CSRs, the last at first + 4
        self.assertEqual(len(DOT4.csrs), 5)

if __name__ == "__main__":
    unittest.main()
