#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Cut snax-alu's run into phases, from per-instruction traces.

Reads one ELF and its two instruction traces, hart 0 (compute core) and
hart 1 (DMA core), from either side:

- SNAX-GVSoC: the files `--trace=pe0/insn:pe0.txt` and `--trace=pe1/insn:pe1.txt`
  write into the work directory;
- snax_cluster's RTL: the raw `logs/trace_chip_00_hart_00000.dasm` and
  `..._00001.dasm` the run writes, read directly, so `make traces` (and its
  `spike-dasm`) is not needed; the `.txt` files `make traces` makes from
  them are read when there is no `.dasm`.

The phase boundaries are markers found in the ELF by function symbol and
instruction pattern (docs/plans/SG5.md, "Phases and markers"), never by a
fixed PC, so another size or a rebuild moves nothing.

Usage:
    phases.py ELF --gvsoc WORKDIR [--json OUT] [--show PHASE]
    phases.py ELF --rtl LOGDIR [--json OUT] [--show PHASE]

Prints one table per hart: each phase's first cycle, its cycles (the next
phase's first cycle minus its own), the instructions traced in it and, for
the poll phases, the polls; then the total, from hart 0's `_start` to its
store to `tohost`, and the total up to the read of 982 (C0 to C5), which
leaves out `printf` and the exit: they wait on the host. Plain Python plus
pyelftools, which the image's venv has.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

# --------------------------------------------------------------------------
# Traces: a list of (cycle, pc) per hart, one entry per traced instruction
# --------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# 174200000: 1742: [/chip/soc/cluster_0/pe0/insn   ] main:0   M 80000254 addi ...
_GVSOC_LINE = re.compile(
    r"^\s*\d+:\s*(\d+):\s*\[[^\]]*\]\s*\S+\s+[MSU]\s+([0-9a-fA-F]{8})\s")


def read_gvsoc(lines):
    """GVSoC's `insn` trace: one line per instruction, the cycle second."""
    out = []
    for line in lines:
        m = _GVSOC_LINE.match(_ANSI.sub("", line))
        if m:
            out.append((int(m.group(1)), int(m.group(2), 16)))
    return out


_DASM_LINE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+0x([0-9a-fA-Fzx]+)\s+DASM\(([0-9a-fA-Fzx]+)\)\s*#;\s*(.*)$")
_EXTRA = re.compile(r"'([^']+)'\s*:\s*0x([0-9a-fA-F]+)")


def read_rtl_dasm(lines):
    """snax_cluster's raw `trace_chip_*_hart_*.dasm` (snitch_cc.sv): time,
    cycle, privilege, pc, `DASM(<word>)`, then `#;` and a dict of extras.

    An instruction is a line from the integer core (`source` 0) that is not
    stalled and not offloaded to the FPU: the lines `gen_trace.py` gives a
    pc in the `.txt`. Stalled lines (load and accelerator write-backs) and
    FPU and sequencer lines are skipped.
    """
    out = []
    for line in lines:
        m = _DASM_LINE.match(line)
        if not m:
            continue
        extras = {k: int(v, 16) for k, v in _EXTRA.findall(m.group(6))}
        if extras.get("source", 0) != 0 or extras.get("stall", 0) or extras.get("fpu_offload", 0):
            continue
        out.append((int(m.group(2)), int(m.group(4), 16)))
    return out


def read_rtl(lines):
    """snax_cluster's `trace_chip_*_hart_*.txt` (util/trace/gen_trace.py).

    Columns: time, cycle, privilege, pc, instruction, then `#;` and
    annotations. Time and cycle are left blank when equal to the line
    before; lines without a pc (stalls, write-backs) carry no instruction.
    The performance metrics after `## Performance metrics` are skipped.
    """
    out = []
    cycle = None
    for line in lines:
        if line.startswith("## Performance metrics"):
            break
        tokens = line.split("#;")[0].split()
        for i, tok in enumerate(tokens):
            if tok in ("M", "S", "U"):
                break
        else:
            continue
        if i >= 2 and tokens[i - 1].isdigit() and tokens[i - 2].isdigit():
            cycle = int(tokens[i - 1])
        if i + 1 < len(tokens) and tokens[i + 1].startswith("0x"):
            if cycle is None:
                raise ValueError(f"trace line before any cycle: {line!r}")
            out.append((cycle, int(tokens[i + 1], 16)))
    return out


# --------------------------------------------------------------------------
# Markers: PCs found in the ELF by symbol and instruction pattern
# --------------------------------------------------------------------------

BARRIER = 0x7C202073  # csrr x0, 0x7c2 (snrt_cluster_hw_barrier)
RET = 0x00008067      # jalr x0, 0(ra)


def _sext(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def csr_of(word):
    """The CSR number of a SYSTEM instruction with a CSR, else None."""
    if word & 0x7F == 0x73 and (word >> 12) & 0x7 not in (0, 4):
        return word >> 20
    return None


def csr_writes(word):
    """True if a CSR instruction writes its CSR (Zicsr: csrrw/csrrwi always,
    set and clear forms only with a nonzero rs1 or immediate)."""
    if csr_of(word) is None:
        return False
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    return funct3 in (1, 5) or rs1 != 0


def jal_target(pc, word):
    """Target of a `jal`, else None."""
    if word & 0x7F != 0x6F:
        return None
    imm = (((word >> 31) & 1) << 20 | ((word >> 12) & 0xFF) << 12
           | ((word >> 20) & 1) << 11 | ((word >> 21) & 0x3FF) << 1)
    return pc + _sext(imm, 21)


def branch_target(pc, word):
    """Target of a conditional branch, else None."""
    if word & 0x7F != 0x63:
        return None
    imm = (((word >> 31) & 1) << 12 | ((word >> 7) & 1) << 11
           | ((word >> 25) & 0x3F) << 5 | ((word >> 8) & 0xF) << 1)
    return pc + _sext(imm, 13)


def is_dmstati(word):
    """Snitch's `dmstati` (custom-1, funct3 0, funct7 0b0000100)."""
    return word & 0x7F == 0x2B and (word >> 12) & 0x7 == 0 and word >> 25 == 0b0000100


def store_address(pc, prev_word, word):
    """Address of an S-type store whose base was just set by `auipc`, else None."""
    if word & 0x7F != 0x23 or prev_word & 0x7F != 0x17:
        return None
    if (word >> 15) & 0x1F != (prev_word >> 7) & 0x1F:
        return None
    imm_s = _sext(((word >> 25) << 5) | ((word >> 7) & 0x1F), 12)
    return (pc - 4 + _sext(prev_word & 0xFFFFF000, 32) + imm_s) & 0xFFFFFFFF


class Elf:
    """The words of the ELF's executable sections and its function symbols."""

    def __init__(self, path):
        self.words = {}
        self.symbols = {}
        with open(path, "rb") as f:
            elf = ELFFile(f)
            for sec in elf.iter_sections():
                if sec["sh_type"] == "SHT_PROGBITS" and sec["sh_flags"] & 0x4:
                    data, base = sec.data(), sec["sh_addr"]
                    for off in range(0, len(data) - 3, 4):
                        self.words[base + off] = int.from_bytes(data[off:off + 4], "little")
            for sym in elf.get_section_by_name(".symtab").iter_symbols():
                if sym.name:
                    self.symbols[sym.name] = (sym["st_value"], sym["st_size"])

    def addr(self, name):
        if name not in self.symbols:
            raise MarkerError(f"symbol {name} not in the ELF")
        return self.symbols[name][0]

    def body(self, name):
        """(pc, word) for every word of function `name`."""
        start, size = self.symbols.get(name, (None, 0))
        if not size:
            raise MarkerError(f"function {name} not in the ELF or of size 0")
        return [(pc, self.words[pc]) for pc in range(start, start + size, 4)]

    def find(self, name, test, what):
        """The PCs in function `name` whose word passes `test`; at least one."""
        pcs = [pc for pc, word in self.body(name) if test(pc, word)]
        if not pcs:
            raise MarkerError(f"{what} not found in {name}")
        return pcs

    def poll_loop(self, name, test, what):
        """A loop in `name` of one instruction passing `test` at P and a branch
        at P + 4 back to P. Returns (P, exit), exit = P + 8."""
        for pc, word in self.body(name):
            nxt = self.words.get(pc + 4)
            if test(pc, word) and nxt is not None and branch_target(pc + 4, nxt) == pc:
                return pc, pc + 8
        raise MarkerError(f"poll loop of {what} not found in {name}")


class MarkerError(Exception):
    pass


# A phase starts at the first trace entry, from where the previous phase
# started, that matches its start rule:
#   ("at", pcs)    the first entry at one of the PCs
#   ("after", pcs) the entry right after the first one at one of the PCs
# A poll phase also names the PC whose entries it counts.

def markers(elf):
    """The phase list per hart, from the ELF."""
    c_main = elf.addr("main")
    barrier = elf.find("main", lambda pc, w: w == BARRIER, "the barrier")
    w975 = elf.find("start_streamer", lambda pc, w: csr_of(w) == 975 and csr_writes(w), "the write to 975")
    w980 = elf.find("start_alu", lambda pc, w: csr_of(w) == 980 and csr_writes(w), "the write to 980")
    r982 = elf.find("main", lambda pc, w: csr_of(w) == 982 and not csr_writes(w), "the read of 982")
    ret = elf.find("main", lambda pc, w: w == RET, "main's ret")
    alu_call, alu_exit = elf.poll_loop(
        "main", lambda pc, w: jal_target(pc, w) == elf.addr("read_busy_alu"), "read_busy_alu")
    str_call, str_exit = elf.poll_loop(
        "main", lambda pc, w: jal_target(pc, w) == elf.addr("read_busy_streamer"), "read_busy_streamer")
    dm_poll, dm_exit = elf.poll_loop("main", lambda pc, w: is_dmstati(w), "dmstati")
    tohost = elf.addr("tohost")
    store = [pc for pc, w in elf.words.items()
             if store_address(pc, elf.words.get(pc - 4, 0), w) == tohost]
    if not store:
        raise MarkerError("no store to tohost")
    start = [elf.addr("_start")]
    return {
        0: [("C0 boot", ("at", start), None),
            ("C1 barrier", ("at", [c_main]), None),
            ("C2a CSR setup", ("after", barrier), None),
            ("C2b CSR setup", ("after", w975), None),
            ("C3 ALU poll", ("after", w980), alu_call),
            ("C4 streamer poll", ("at", [alu_exit]), str_call),
            ("C5 check loop", ("at", [str_exit]), None),
            ("C6 printf", ("after", r982), None),
            ("C7 exit", ("after", ret), None),
            ("end", ("at", store), None)],
        1: [("D0 boot", ("at", start), None),
            ("D1 DMA issue", ("at", [c_main]), None),
            ("D2 DMA wait", ("at", [dm_poll]), dm_poll),
            ("D3 barrier", ("at", [dm_exit]), None),
            ("D4 post-main and exit", ("after", barrier), None)],
    }


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------

def _find(trace, i, rule, name):
    kind, pcs = rule
    for j in range(i, len(trace)):
        if trace[j][1] in pcs:
            j = j + 1 if kind == "after" else j
            if j >= len(trace):
                break
            return j
    raise MarkerError(f"start of {name} not found in the trace")


def cut(trace, phases, end_cycle=None):
    """Cut one hart's trace into `phases`. The last entry named "end" marks
    the run's end; without it the run ends at `end_cycle`."""
    starts, i = [], 0
    for name, rule, _ in phases:
        i = _find(trace, i, rule, name)
        starts.append(i)
    if phases[-1][0] == "end":
        end_cycle = trace[starts[-1]][0]
        phases, starts = phases[:-1], starts[:-1]
    if end_cycle is None:
        raise ValueError("no end cycle")
    rows = []
    for k, (name, _, poll_pc) in enumerate(phases):
        first = starts[k]
        last = starts[k + 1] if k + 1 < len(starts) else None
        cycle = trace[first][0]
        nxt = trace[last][0] if last is not None else end_cycle
        entries = trace[first:last] if last is not None else [
            e for e in trace[first:] if e[0] < end_cycle]
        rows.append({
            "phase": name,
            "start": cycle,
            "cycles": nxt - cycle,
            "insns": len(entries),
            "polls": sum(1 for e in entries if e[1] == poll_pc) if poll_pc else None,
        })
    return rows, end_cycle


def show(trace, phases, name, words):
    """One line per instruction of phase `name`: its cycle, the cycles to the
    next instruction, its pc and its word. For finding where a phase's
    cycles go on either side."""
    names = [p[0] for p in phases]
    if name not in names or name == "end":
        raise MarkerError(f"no phase {name} on this hart")
    i, starts = 0, []
    for pname, rule, _ in phases:
        i = _find(trace, i, rule, pname)
        starts.append(i)
    k = names.index(name)
    first = starts[k]
    last = starts[k + 1] if k + 1 < len(starts) else len(trace) - 1
    out = []
    for j in range(first, last):
        cycle, pc = trace[j]
        out.append(f"{cycle:>8} +{trace[j + 1][0] - cycle:<4} {pc:08x} {words.get(pc, 0):08x}")
    return "\n".join(out)


def phase_tables(elf_path, traces):
    """`traces` maps hart to its trace; returns the tables and the total."""
    marks = markers(Elf(elf_path))
    table0, end = cut(traces[0], marks[0])
    table1, _ = cut(traces[1], marks[1], end_cycle=end)
    c6 = next(r["start"] for r in table0 if r["phase"] == "C6 printf")
    return {
        "harts": {"0": table0, "1": table1},
        "total": end - table0[0]["start"],
        "total_to_982": c6 - table0[0]["start"],
    }


def load_traces(args):
    if args.gvsoc:
        files = {h: Path(args.gvsoc) / f"pe{h}.txt" for h in (0, 1)}
        reader = read_gvsoc
    else:
        files = {}
        for h in (0, 1):
            for ext in ("dasm", "txt"):
                found = sorted(Path(args.rtl).glob(f"trace_chip_*_hart_*{h}.{ext}"))
                if found:
                    break
            if len(found) != 1:
                raise SystemExit(f"expected one trace for hart {h} in {args.rtl}, found {len(found)}")
            files[h] = found[0]
        reader = None
    traces = {}
    for h, path in files.items():
        read = reader or (read_rtl_dasm if path.suffix == ".dasm" else read_rtl)
        with open(path) as f:
            traces[h] = read(f)
    return traces


def format_tables(result, side):
    out = []
    for hart, rows in result["harts"].items():
        out.append(f"{side}, hart {hart}")
        out.append(f"  {'phase':<24}{'start':>8}{'cycles':>8}{'insns':>8}{'polls':>8}")
        for r in rows:
            polls = "" if r["polls"] is None else r["polls"]
            out.append(f"  {r['phase']:<24}{r['start']:>8}{r['cycles']:>8}{r['insns']:>8}{polls:>8}")
    out.append(f"{side}, total {result['total']}, up to the read of 982 {result['total_to_982']}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("elf")
    side = p.add_mutually_exclusive_group(required=True)
    side.add_argument("--gvsoc", metavar="WORKDIR", help="holds pe0.txt and pe1.txt")
    side.add_argument("--rtl", metavar="LOGDIR", help="holds trace_chip_*_hart_*.dasm (or .txt)")
    p.add_argument("--json", metavar="OUT", help="also write the tables as JSON")
    p.add_argument("--show", metavar="PHASE",
                   help="also list a phase's instructions, e.g. 'C2a CSR setup'")
    args = p.parse_args(argv)
    try:
        traces = load_traces(args)
        result = phase_tables(args.elf, traces)
        if args.show:
            elf = Elf(args.elf)
            marks = markers(elf)
            hart = 0 if args.show[0] == "C" else 1
            listing = show(traces[hart], marks[hart], args.show, elf.words)
    except MarkerError as e:
        print(f"phases.py: {e}", file=sys.stderr)
        return 1
    result["side"] = "gvsoc" if args.gvsoc else "rtl"
    print(format_tables(result, result["side"]))
    if args.show:
        print(f"{result['side']}, {args.show}: cycle, +cycles to the next, pc, word")
        print(listing)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
