# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snax/snax_unit_acc.py's slot check. Run from snax-gvsoc after
`make build` (the composite imports GVSoC's Python from install/):

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

Skipped where install/ has no GVSoC.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "install"
sys.path[:0] = [str(ROOT / "snax"), str(INSTALL / "python"), str(INSTALL / "bin"),
                str(INSTALL / "generators")]
try:
    import snax_unit_acc  # noqa: E402
    from snax_acc import SNAX_ACC_CSR_LAST, SNAX_CSR_FIRST  # noqa: E402
    from snax_cfg import CfgTargetError  # noqa: E402
    from snax_streamer import nb_csrs  # noqa: E402
except ImportError:
    snax_unit_acc = None

# vecadd's streamer at W = 4 (forge/vecadd): 18 CSRs
STREAMER = {
    "data_reader_params": {"spatial_bounds": [[4], [4]], "temporal_dim": [1, 1],
                           "num_channel": [4, 4], "fifo_depth": [8, 8]},
    "data_writer_params": {"spatial_bounds": [[4]], "temporal_dim": [1], "num_channel": [4],
                           "fifo_depth": [8]},
}


def slot(nb_fields):
    """A slot with STREAMER and a SnaxUnit datapath of nb_fields configuration fields."""
    datapath = SimpleNamespace(unit="SnaxUnit", fields=[f"f{i}" for i in range(nb_fields)])
    return SimpleNamespace(name="acc", at="cores[0].snax_acc_cfg[0]", streamer=STREAMER,
                           datapath=datapath)


@unittest.skipIf(snax_unit_acc is None, "no GVSoC in install/ (run make build first)")
class ShellCsrs(unittest.TestCase):
    """The shell's counter (the slot's last CSR) may be at most SNAX_ACC_CSR_LAST, 0x5FD:
    0x5FE and 0x5FF are snax_cluster's task-queue CSRs, not the accelerator's."""

    def fields_for_counter(self, counter):
        # streamer CSRs, then the fields, start, busy and the counter
        return counter - SNAX_CSR_FIRST - nb_csrs(STREAMER) - 2

    def test_a_counter_on_0x5fd_is_taken(self):
        self.assertEqual(SNAX_ACC_CSR_LAST, 0x5FD)
        cls = snax_unit_acc.SnaxUnitAcc.for_slot(slot(self.fields_for_counter(0x5FD)), 131072)
        self.assertEqual(cls.nb_tcdm_ports, 12)

    def test_a_counter_on_0x5fe_is_refused(self):
        with self.assertRaises(CfgTargetError) as ctx:
            snax_unit_acc.SnaxUnitAcc.for_slot(slot(self.fields_for_counter(0x5FE)), 131072)
        self.assertIn(f"the shell's last CSR {0x5FE} is past {0x5FD}", ctx.exception.why)


if __name__ == "__main__":
    unittest.main()
