# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_unit_acc.py: the slot's CSR limit, and the composite built
from accelerator.json, one group (forge/vecadd/) and two (dot 1, test_snax_cfg's DOT).
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
from test_snax_cfg import CLUSTER, STREAMER, VECADD, dot_cluster  # noqa: E402


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
        """One group of one unit: shell and unit, as before (snax_acc0/unit)."""
        acc = self.build(CLUSTER)
        self.assertEqual(sorted(acc.components), ["csr_mux", "shell", "streamer", "unit"])
        first = SNAX_CSR_FIRST + nb_csrs(STREAMER)
        self.assertEqual(acc.components["shell"].properties,
                         {"csr_base": first, "csrs": ["START", "JOBS"]})
        unit = acc.components["unit"].properties
        self.assertEqual((unit["datapath"], unit["inputs"], unit["outputs"], unit["op"],
                          unit["lanes"], unit["latency"], unit["ii"], unit["csr_base"]),
                         ("ElementwiseLanes", ["a", "b"], ["out"], "add", 4, 0, 1, first))

    def test_dot_two_groups(self):
        """dot 1: a shell per group at its window, a unit per unit, named after them."""
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
        mul, total = (acc.components[n].properties for n in ("unit_mul", "unit_sum"))
        self.assertEqual((mul["datapath"], mul["inputs"], mul["op"], mul["csr_base"]),
                         ("ElementwiseLanes", ["a", "b"], "mul", first))
        self.assertEqual((total["datapath"], total["inputs"], total["outputs"], total["op"],
                          total["lanes"], total["latency"], total["csr_base"]),
                         ("TreeAccumulate", ["a"], ["out"], "add", 4, 1, first + 4))
        self.assertEqual(snax_unit_acc.component_names(slot.accelerator),
                         ({"mul": "shell_mul", "sum": "shell_sum"},
                          {"mul": "unit_mul", "sum": "unit_sum"}))


if __name__ == "__main__":
    unittest.main()
