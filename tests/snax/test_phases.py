# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of phases.py. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

The GVSoC lines are copied from a `snax-alu` run (`--trace=pe0/insn`); the
RTL lines are written in the format of snax_cluster's util/trace/gen_trace.py
(TRACE_OUT_FMT, blank time and cycle when equal to the line before), not
copied from a run.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phases  # noqa: E402

GVSOC = """\
174200000: 1742: [\x1b[34m/chip/soc/cluster_0/pe0/insn      \x1b[0m] $d:0          M 00001000 csrrs     a0, 0, mhartid    a0=00000000
252900000: 2529: [\x1b[34m/chip/soc/cluster_0/pe0/insn      \x1b[0m] main:0        M 8000029c csrrs     0, 0, barrier
253000000: 2530: [\x1b[34m/chip/soc/cluster_0/pe0/insn      \x1b[0m] main:0        M 800002a0 csrrs     a1, 0, mcycle     a1=000009e2
some other output
"""

RTL = """\
   1000000      100        M 0x80000000 auipc   sp, 0x10                 #; (wrb) sp  <-- 0x80010000
                           M 0x80000004 addi    sp, sp, -16              #; sp  = 0x80010000
   1020000      102        M                                             #; (lsu) a0  <-- 0x0
   1030000      103        M 0x80000008 lw      a0, 0(sp)                #; sp  = 0x8000fff0
## Performance metrics
Performance metrics for section 0 @ (100, 103):
"""


# The raw RTL trace, in the format of snitch_cc.sv's $sformat
# ("%t %1d %8d 0x%h DASM(%h) #; %s": time, cycle, privilege, pc, word,
# extras), not copied from a run: an issued instruction, a stalled line
# (a load's write-back), an FPU line, and an instruction offloaded to the FPU.
DASM = """\
1000000 100        3 0x80000000 DASM(00010117) #; {'source': 0x0, 'stall': 0x0, 'rd': 0x2, 'fpu_offload': 0x0, }
1010000 101        3 0x80000004 DASM(00012503) #; {'source': 0x0, 'stall': 0x1, 'retire_load': 0x1, 'fpu_offload': 0x0, }
1010000 101        3 0xzzzzzzzz DASM(zzzzzzzzzzzzzzzz) #; {'source': 0x1, 'acc_q_hs': 0x1, }
1020000 102        3 0x80000008 DASM(0005a007) #; {'source': 0x0, 'stall': 0x0, 'fpu_offload': 0x1, }
1030000 103        3 0x8000000c DASM(00000013) #; {'source': 0x0, 'stall': 0x0, 'fpu_offload': 0x0, }
"""


class Traces(unittest.TestCase):
    def test_gvsoc(self):
        self.assertEqual(phases.read_gvsoc(GVSOC.splitlines()),
                         [(1742, 0x1000), (2529, 0x8000029C), (2530, 0x800002A0)])

    def test_rtl_dasm(self):
        self.assertEqual(phases.read_rtl_dasm(DASM.splitlines()),
                         [(100, 0x80000000), (103, 0x8000000C)])

    def test_rtl(self):
        # The second line repeats cycle 100; the line without a pc is skipped;
        # nothing after the metrics header is read.
        self.assertEqual(phases.read_rtl(RTL.splitlines()),
                         [(100, 0x80000000), (100, 0x80000004), (103, 0x80000008)])


class Decode(unittest.TestCase):
    # Words from snax-alu.dump (LLVM 21.1.6).
    def test_csr(self):
        self.assertEqual(phases.csr_of(0x3CF0D073), 975)          # csrwi 975, 1
        self.assertTrue(phases.csr_writes(0x3CF0D073))
        self.assertEqual(phases.csr_of(0x3D602473), 982)          # csrr s0, 982
        self.assertFalse(phases.csr_writes(0x3D602473))
        self.assertEqual(phases.csr_of(phases.BARRIER), 0x7C2)
        self.assertIsNone(phases.csr_of(0x00008067))              # ret

    def test_jumps(self):
        self.assertEqual(phases.jal_target(0x80000308, 0xF45FF0EF), 0x8000024C)
        self.assertEqual(phases.branch_target(0x8000030C, 0xFE051EE3), 0x80000308)
        self.assertIsNone(phases.branch_target(0x80000308, 0xF45FF0EF))

    def test_dmstati(self):
        self.assertTrue(phases.is_dmstati(0x082002AB))
        self.assertFalse(phases.is_dmstati(0x00D6002B))           # dmsrc

    def test_store_address(self):
        auipc = 0x00000597                                       # auipc a1, 0
        sw = (25 << 25) | (10 << 20) | (11 << 15) | (2 << 12) | 0x23  # sw a0, 800(a1)
        self.assertEqual(phases.store_address(0x800028A4, auipc, sw), 0x80002BC0)
        self.assertIsNone(phases.store_address(0x800028A4, 0x00000613, sw))


class Cut(unittest.TestCase):
    PHASES = [("A", ("at", [0x10]), None),
              ("B", ("after", [0x20]), 0x30),
              ("C", ("at", [0x34]), None),
              ("end", ("at", [0x40]), None)]

    def test_cut(self):
        trace = [(5, 0x00), (10, 0x10), (11, 0x14), (12, 0x20), (20, 0x24),
                 (21, 0x30), (25, 0x30), (29, 0x30), (30, 0x34), (31, 0x38),
                 (40, 0x40), (41, 0x44)]
        rows, end = phases.cut(trace, self.PHASES)
        self.assertEqual(end, 40)
        self.assertEqual(rows, [
            {"phase": "A", "start": 10, "cycles": 10, "insns": 3, "polls": None},
            {"phase": "B", "start": 20, "cycles": 10, "insns": 4, "polls": 3},
            {"phase": "C", "start": 30, "cycles": 10, "insns": 2, "polls": None}])

    def test_end_from_other_hart(self):
        trace = [(10, 0x10), (12, 0x20), (20, 0x24), (30, 0x34), (35, 0x38), (50, 0x3C)]
        rows, end = phases.cut(trace, self.PHASES[:-1], end_cycle=40)
        self.assertEqual(rows[-1], {"phase": "C", "start": 30, "cycles": 10, "insns": 2, "polls": None})

    def test_show(self):
        trace = [(10, 0x10), (12, 0x20), (20, 0x24), (30, 0x34), (35, 0x38), (40, 0x40)]
        lines = phases.show(trace, self.PHASES, "B", {0x24: 0x13}).splitlines()
        self.assertEqual(lines, ["      20 +10   00000024 00000013"])

    def test_missing_marker(self):
        with self.assertRaisesRegex(phases.MarkerError, "start of C"):
            phases.cut([(10, 0x10), (12, 0x20), (20, 0x24)], self.PHASES)


if __name__ == "__main__":
    unittest.main()
