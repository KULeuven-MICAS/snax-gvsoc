# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what still holds. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there. Entries are dated history: a name or path gone since is marked
once, where it first appears.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the programs and the RTL reference | `sw/README.md`, "Pin" (`ccc7688f`): the copy in `sw/` is at it, and the RTL runs in a checkout at it. Before: SG0 `8ebd422`, SG1–SG4 `b2672f8`, SG5 `d7dd789`, SG6–SG7 `9fbf35d` (#657), SG8 on `05615e4` (#658), then `cf4b0002` (LNK2b) and `b9e475b4` |
| common_cells, the TCDM arbiter (SG3) | `v1.40.0` (`1281545696eb3fcba50ec5b4275993476a3c710e`), in the RTL build's `Bender.lock` |

## Log

### SG0 step 1: detached copy

- 2026-10-12. Done as in `UPSTREAM.md`, "How the copy was made", folding in
  the `snax-gvsoc:gvs1` container (the host git has no `subtree`). Each
  folded folder's tree equals its upstream pin; only `main` pushed.

### SG0 step 2: P1

- 2026-10-12. `UPSTREAM.md`, a README, this file, the SG0 plan; upstream's CI
  workflow and CODEOWNERS removed; `container/` imported from
  snax-gvsoc-experiment `386e433`. The bundled ELF exits 0 on `snitch`.

### SG0 step 4: P2, snax_cluster's toolchain

- 2026-10-12. `container/` after snax_cluster's Dockerfile at `8ebd422`: its
  exact toolchain (clang 21.1.6, bender 0.28.2), no GCC. P2b: the repo is
  mounted at its own path; GVSoC writes `build/` and `install/` in it.

### SG0 step 5: the probe

- 2026-10-12. snax_cluster `8ebd422`'s 17 plain tests on `snitch` at
  `93cedc4`: `simple.elf` stops at cycle 3946 on `unsupported CSR (id:
  0xbc1)`. Its start-up code reads the cluster base and {core count, index}
  from CSRs 0xBC1 to 0xBC3 it added to Snitch. All else matches.

### SG0 step 6: P3, the cluster CSRs

- 2026-10-12. The accurate Snitch core declares 0xBC1 to 0xBC3 read-only
  (base below 2^31, 0xBC2 always 0). All 17 tests exit 0; core 8 reads
  0xBC3 = 0x00090008, as the RTL.

### SG0 step 7: one image, in snax-forge

- 2026-10-13. One image, `ghcr.io/kuleuven-micas/snax-forge:main` from
  snax-forge's `container/` (D118 there); `container/` removed here. pixi
  0.41.4 added; the toolchain stage keeps 0.81.0 (0.41.4 refuses lock v7).
  GVSoC is built outside `pixi shell` (conda's `CC`/`CXX`); `gvrun` in a pixi
  task gets pixi's Python: open item 56 in snax-forge.

### SG0 step 8: SG0 closed

- 2026-10-13. Settled: a detached copy of GVSoC `93cedc4` with history, plus
  P3; snax_cluster `8ebd422`'s plain tests pass on `snitch`; one image
  (D118), clang only; snax_cluster checked out beside the repo. The Snitch
  model: `pulp/pulp/snitch/`, its C++ in `core/models/cpu/iss/src/snitch/`.

### SG1 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG1.md`: the `snax_alu` target (since removed,
  CLN1 R2) by hand from `cfg/snax_alu_cluster_old.hjson` (plain
  interconnect) and the CSR port; pin `b2672f8`. On the RTL `snax-alu`
  prints `Accelerator Cycles: 25`, 0 errors.

### SG1 step 2: P2, the snax-alu app copied in

- 2026-10-13. `tests/snax/snax-alu/` (the `tests/snax/<program>/` folders
  since moved to `sw/apps/`, CI1; `snax-alu` since removed, CLN1 R2):
  `b2672f8`'s app and streamer header, built against the snax_cluster
  checkout's runtime. On `snitch` it stops at the first SNAX CSR (0x3c0).

### SG1 step 3: P3, the snax_alu target

- 2026-10-13. `snax/snax_alu.py` (since removed): one cluster of 2 cores
  (hart 1 the DMA core), `misa` = 0x40001101 (RV32 IMA, the CSR value only).
  GVSoC reads a target twice, at `make build` and under gvrun, with
  different arch classes.

### SG1 step 4: how a CSR instruction can leave the core

- 2026-10-13. Read at `93cedc4`: `csrrw` / `csrrwi` call the CSR object's
  `handle()`; the set and clear forms go through callbacks that see only
  `(is_write, value)`. A CSR can stall the core, as the barrier CSR 0x7C2.

### SG1 step 5: P4, the CSR port

- 2026-10-13. The Snitch core declares 0x3C0 to 0x5FF as `SnaxCsr`s; each
  access is a 32-bit IO request on port `snax_csr` at 4 * CSR number;
  `csrrw` / `csrrwi` read first only when `rd` is not `x0`. An OK answer's
  latency stalls the core; pending or denied is fatal.

### SG1 step 6: P5, the stub register block

- 2026-10-13. `snax/snax_csr_stub.*` (since removed, housekeeping after
  SG6). `ClusterArch` takes `snax_acc` and binds each core's `o_SNAX_CSR`.
  GVSoC runs with `werror: true`: any `force_warning` ends the run.
- P4 fix: `rd = x0` decodes as `ISS_NB_REGS`, not 0. `tests/snax/snax-csr/`
  (one part per CSR path): four lines of `0 errors`, 108 accesses.

### SG1 step 7: snax-alu on the stub

- 2026-10-13. `snax-alu` runs to the end, 100 errors (nothing computes). The
  streamer starts before the ALU, each by a write of 1 to its block's last
  read-write CSR; each streamer runs 25 steps of 4 lanes of 64 bit.

### SG1 step 8: SG1 closed

- 2026-10-13. Acceptance met; settled in `docs/plans/SG1.md`, "Decided"; in
  snax-forge D119, D120.

### SG2 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG2.md`: fit GVSoC's iDMA to the RTL's (fork
  `e859ffc`), differences in SG2.md, "The DMA path". `DMA_BUSY` counts
  `busy_o`, which `snrt_dma_wait_all` polls; GVSoC's counters read 0.

### SG2 step 2: P2, the timing program

- 2026-10-13. `tests/snax/dma-timing/`: one ELF for both sides, cases in its
  README. Unfitted, the DRAM's 100 cycles and 4 B a cycle dominated `done`
  (1x8192: 1939).

### SG2 step 3: the RTL run

- 2026-10-13. Author's RTL run (`b2672f8`, iDMA `e859ffc`): 0 errors; `issue`
  18, 28, 48 for 1, 2, 4 copies; `busy` and `done` as in step 7.

### SG2 step 4: what the RTL does

- 2026-10-13. `busy = L_rd + N_beats + 2` in all eight copy cases (`L_rd` 11
  from DRAM, 5 from L1; one 64 B beat a cycle, no gap between bursts).
  `busy_o` drops before the write response.

### SG2 step 5: P3, the perf counters

- 2026-10-13. The cluster registers count `CYCLE`, `DMA_R_DONE`,
  `DMA_W_DONE`, `DMA_BUSY` from the iDMA's `busy`, `r_beats`, `w_beats`.
  `r` and `w` equal the RTL's beats.

### SG2 step 6: P4, the parameters

- 2026-10-13. `ClusterArch(dma=...)`, `hbm_latency` 6 (default 100), DRAM
  64 B a cycle; the cores' DRAM accesses take the 6 too. `busy` 5 under the
  RTL.

### SG2 step 7: P5, the DMA's read path

- 2026-10-13. `SnitchDma`'s `read_latency` 5 (default 0), plus
  `hbm_latency` from DRAM. `busy` equals the RTL in all eight copy cases (14,
  17, 26, 77, 141, 39, 65, 20); `done` is 2 to 6 under it, the core's issue
  and polling (idle 6 against 12).

### SG2 step 8: SG2 closed

- 2026-10-13. Acceptance met; settled in `docs/plans/SG2.md`, "Decided"; in
  snax-forge D121.

### SG3 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG3.md`: a streamer from the hjson, a crossbar as
  the plain interconnect (since removed, CLN1 R2), a reader-only timing
  program. Streamer CSRs 960 to 977, the ALU's 978 to 982.

### SG3 step 2: P2, the CSR router

- 2026-10-14. `snax/snax_alu_acc.py` (since removed, CLN1 R2): `SnaxAluAcc`,
  a `Router` splitting the CSRs to `streamer` and `alu`, adding no cycle. On
  stdout a `printf` can split a trace line; trace to a file.

### SG3 step 3: P3, the crossbar and the readers

- 2026-10-14. `snax/snax_tcdm_xbar.*` (per-bank arbitration, response one
  cycle after the grant) and `snax/snax_streamer.*`.
  `tests/snax/stream-timing/`: counters 0, 9, 9, 10, 12. The arbiter matched
  `rr_arb_tree` in Icarus in every cycle of 2000.

### SG3 step 4: the RTL run

- 2026-10-14. Author's RTL run: counters 0, 9, 9, 10, 12; common_cells
  1.40.0 at `1281545`.

### SG3 step 5: the counter on both sides

- 2026-10-14. Equal in all five cases: start, AGU pace, end rule and
  round-robin match the RTL. Polls and `mcycle` are the core's.

### SG3 step 6: P4 skipped

- 2026-10-14. Step 5 left no gap in the streamer's counter.

### SG3 step 7: P5, writers, beats and the test datapath

- 2026-10-14. Writers and beat ports in the streamer; a test datapath in the
  ALU's place (removed in SG4 P2); per-mover classes
  (`busy` > `stall_xbar` > `stall_fifo` > `idle`).
  `tests/snax/snax-stream/` (since removed, CLN1 R2) runs the three
  streamers.

### SG3 step 8: SG3 closed

- 2026-10-14. Acceptance met; settled in `docs/plans/SG3.md`, "Decided"; in
  snax-forge D122, open items 57, 58, 60, 62.

### SG4 step 1: P1, the plan

- 2026-10-14. `docs/plans/SG4.md`: an ALU after `snax_alu_shell_wrapper.sv`,
  `alu-timing` on both sides. The ALU's `ready` is tied to 1; a start keeps
  `len_counter`; a firing needs both beats and the writer's `ready`.

### SG4 step 2: P2, the ALU

- 2026-10-14. `snax/snax_alu_shell.*` (since removed, CLN1 R2) replaces the
  test datapath. `snax-alu`: `Accelerator Cycles: 25`, 0 errors.

### SG4 step 3: P3, the CSR-form warnings

- 2026-10-14. Warnings where GVSoC followed Zicsr and the RTL did not
  (removed in SG6 step 2, as was `priv.hpp`'s write-back on no-write forms).

### SG4 step 4: P4, the timing program

- 2026-10-14. `tests/snax/alu-timing/` (since removed, CLN1 R2): five cases,
  each with a counter independent of the start gap. `out_one_bank` puts all
  of O on one bank: ALU `stall_out 50`, 982 72.

### SG4 step 5: the RTL run

- 2026-10-14. Author's RTL run, 977 / 982: `alu_first` 29 / 32,
  `stream_first` 132 / 25, `out_one_bank` 210 / 72, `len1` 5 / 1,
  `restart_idle` 29 / 32; all 0 errors.

### SG4 step 6: the counters on both sides

- 2026-10-14. Every counter independent of the core's timing is equal. The
  core put about 2 more cycles between two library CSR calls (SG5).

### SG4 step 7: P5 skipped

- 2026-10-14. Step 6 left no gap in the counters compared.

### SG4 step 8: SG4 closed

- 2026-10-14. Acceptance met; settled in `docs/plans/SG4.md`, "Decided"; in
  snax-forge D123, D120 amended, open items 62 to 64.

### SG5 step 1: P1, the plan

- 2026-10-14. `docs/plans/SG5.md`: `snax-alu` at 4, 100, 128, 1024, 4096,
  phases from both sides' traces of one ELF, a three-tier target, `make
  regress`. BASE1 moved out of SG5.

### SG5 step 2: P2, the DMA wait

- 2026-10-14. snax_cluster `d7dd789` (#656): `b2672f8` plus
  `snrt_dma_wait_all()` before the DMA core's barrier; RTL output unchanged.
  `llvm-objdump` names SNAX CSRs `pmpaddr*`, so markers match CSR numbers.

### SG5 step 3: P3, the phase script

- 2026-10-14. `tests/snax/phases.py` (since removed, CLN1 R2b): phases C0
  to C7 (hart 0), D0 to D4 (hart 1). A GVSoC trace file name is relative to
  the work directory. C6 (`printf`) waits on the host's answer, on a grid of
  about 1000 cycles, so tier 2 stops at the read of 982.

### SG5 step 4: P4, the five sizes

- 2026-10-14. 0 errors at every size; before P5 total up to 982 1000, 2983,
  3578, 21950, 84927. D2 and C1 grow about one cycle per 64 B beat, C3 by
  N / 4. Largest size that fits L1: about 5300.

### SG5 P4b: the raw RTL trace

- 2026-10-14. No `spike-dasm` in the image; `phases.py --rtl` read `.dasm`.

### SG5 step 5: the RTL run

- 2026-10-14. 0 errors at every size; total up to 982 1130, 5489, 6750,
  47514, 187304; C5 4535 at 100 (ELFs replaced in step 9).

### SG5 step 6: the phases on both sides

- 2026-10-14. Tier 1 met. C5 20 cycles per element against 45: the RTL
  holds one integer load in flight (fixed in P5). The RTL polls `dmstati`
  every 5 cycles, GVSoC every 2: D2 at 128 20% under, under 3% from 1024.

### SG5 step 7: P5, the core's loads

- 2026-10-14. `Lsu`'s `int_loads_in_flight` (0 no limit, the default) set
  to 1; `ClusterArch`'s `core_latency` `tcdm` 2, `narrow` 6. RTL /
  SNAX-GVSoC, 0 errors and 982 equal:

  | Phase | 128 | 1024 | 4096 |
  |---|---|---|---|
  | C1 barrier | 148 / 154 (+4%) | 374 / 381 (+2%) | 1154 / 1169 (+1%) |
  | D2 DMA wait | 45 / 36 (-20%) | 270 / 262 (-3%) | 1050 / 1050 (0%) |
  | C3 ALU poll | 37 / 39 (+5%) | 262 / 261 (0%) | 1032 / 1029 (0%) |
  | C5 check loop | 5795 / 5698 (-2%) | 46115 / 45244 (-2%) | 184355 / 180754 (-2%) |
  | Total up to 982 | 6750 / 6698 (-1%) | 47514 / 46696 (-2%) | 187304 / 183755 (-2%) |

  Tier 2 met but for D2 at 128; C5 44 cycles per element against 45.

### SG5: the remaining gaps, from the listings

- 2026-10-14. At 100 total up to 982 5471 against the RTL's 5489 (-0.3%).
  C2a and D1: the RTL's L0 cache prefetches, GVSoC's `Hierarchical_cache`
  does not. C7: the testbench's `axi_riscv_atomics_wrap` makes each atomic to
  DRAM a read-modify-write. Accepted, outside the target.

### SG5 step 8: P6, the regression

- 2026-10-14. `tests/snax/regress.py`, `make regress`: exact checks against
  `expected/` and the RTL tables in `rtl/` (replaced in SG6 step 3 by
  finish-only checks); `make regress-plain` since removed (CI1).

### SG5 step 9: the expected files, and the RTL run again

- 2026-10-14. `regress-plain` rebuilt the runtime and the `snax-alu` ELFs
  (why the earlier build differed was not found); total up to 982 1157,
  5444, 6698, 46696, 183755. The RTL rerun: at 128 D2 -20% (accepted), total
  0%; at 1024 and 4096 every row within 3%.

### SG5 step 10: SG5 closed

- 2026-10-14. Acceptance met (SG5.md, "Result"); settled in
  `docs/plans/SG5.md`, "Decided"; in snax-forge D124, D125, open items 65 to
  67, CI1.

### SG6 step 1: round 1, the RTL

- 2026-10-14. Author's run on snax_cluster `ry/sg6-zicsr` at `8d16b0c`
  (pin `4ffe96a`), Questa 2022.4; change in `docs/plans/SG6.md`.
  `snitch.sv` takes `rd` from the accelerator for `csrrw` / `csrrwi` and
  sends `rs1` / `uimm` for set and clear; `snax_intf_translator.sv` makes
  the read-modify-write forms a read then a write. `csrw`, `csrr` unchanged.
- `snax-csr`: before, `csrrw: 17 errors`, exit 20; after, four lines of
  `0 errors`. `snax-alu` (since removed, CLN1 R2) equal to `rtl/<N>`.
- `vsim` exits 0 whatever the program returns; without bender an edited
  `.sv` is missed. Both in snax_cluster's `target/snitch_cluster/README.md`.

### SG6 step 2: round 2, SNAX-GVSoC

- 2026-10-14. Root `CMakeLists.txt` (removed on main by #5) restored from
  `61905d3`. `snax-csr` part 3 (`set/clear/imm`) gains `csrrwi` / `csrrsi`
  / `csrrci` on 960 and the no-write forms on read-only 982; main's GVSoC
  stopped at `csrrc a3, 982, x0`.
- `priv.hpp` (every core): `csrrc` with `x0` and `csrrsi` / `csrrci` with 0
  write nothing, as `csrrs`. Upstream's generic `csrrw` / `csrrwi` path
  still reads with `rd = x0`; SNAX CSRs do not use it. SG4 P3's two
  warnings removed; `UPSTREAM.md`.
- `snax-csr`: `0 errors`, exit 0, 110 accesses (69 reads, 41 writes). The
  forms occur in no other regress ELF. `make regress` passed.

### SG6 step 3: round 3

- 2026-10-14. snax_cluster merged the branch as `9fbf35d` (#657): the pin.
- `make regress` checks only that each program exits 0 within 300 s (14
  SNAX runs on `snax_alu`, since removed in CLN1 R2; 17 plain);
  `expected/`, `rtl/` and `--update` removed, SG5's numbers in
  `docs/plans/SG5.md`; the RTL comparison is by hand (at 100, up to the
  read of 982: 5436 cycles RTL, 5444 GVSoC). A failing program gives
  `FAIL <name>: exit 1`, exit 1; the timeout path was not exercised.

### Housekeeping after SG6

- 2026-10-15. Branch `ry/housekeeping` from main `3cab3fa` (#6). No change
  in output, cycles or traces but one `snitch.cpp` message.
- `snax/snax_csr_stub.*` removed. `snax/snax_csr_block.hpp`
  (`SnaxCsrBlock`) holds the CSR rules both blocks shared (50 lines more in
  all, kept for one place of the rules). Streamer and crossbar loops
  factored; ports as `std::vector`s.
- `snitch.cpp`: an `IO_REQ_INVALID` answer ends the run with `SNAX CSR
  access refused by the block ...`. `regress.py`: per-run `run.log`, last
  20 lines on failure, `-k SUBSTRING`.
- Decided: the ALU keeps its event every cycle while busy. Every saved
  output, phase file and trace equal before and after.

### CI1 round 1

- 2026-10-15. Branch `ry/ci1` from `86a85e3` (#7); `docs/plans/CI1.md`.
  Programs build from a pinned copy of snax_cluster's software in `sw/`
  (`COPIED` in `sw/sync.py`, headers generated with upstream's rules,
  programs moved from `tests/snax/` to `sw/apps/`). `make
  sync-snax-cluster` refuses tracked changes only in what it reads
  (`CHECKED`); a second run at the pin leaves `git status` clean.
- All 32 ELFs equal the reference byte for byte. `regression passed`, 14
  SNAX and 17 plain; also from a standalone clone (build 1 min 39 s).

### CI1 fix-up after review

- 2026-10-15. One list of plain tests (D117 in snax-forge): `COPIED`, from
  `sw/tests/*.c`. `sw/common.mk` writes `-MMD -MP` dependency files.
  `test_phases.py` (since removed, CLN1 R2b) runs with `unittest`.
- 31 ELFs byte-identical after a clean rebuild; `regression passed`.

### CI1 round 2

- 2026-10-15. `.github/workflows/ci.yml`, workflow `CI`, one job `regress`
  in `ghcr.io/kuleuven-micas/snax-forge:main`: ccache in `.ccache`, build,
  unit tests, `make regress`, `regress-logs` on failure. `regress.py`
  prints `::error` annotations under Actions. Locally a second build hit
  the cache on all 509 cacheable calls.
- PR #8 passed (6 min 21 s, no cache); throwaway PR #9 failed at Regress
  with the annotation and artifact (a pull request does not read another's
  cache). Actions moved to Node 24 versions; runner `ubuntu-24.04`.

### SG7 step 2: RTL generation

- 2026-10-15. Branch `ry/sg7-sparse` from `130cc70` (#8);
  `docs/plans/SG7.md`. `rtl-gen` of snax_cluster `9fbf35d` with
  `cfg/snax_alu_cluster.hjson` (snax image `d3d8f5572ff4`): snaxgen's
  `SparseInterconnectGen`, 15 inputs, `[[12, 1], [1, 1], [1, 1], [1, 1]]`.
  A second module with granularity (23 inputs, `[8, 8]`) by hand. Both
  under `build/sg7/`, not committed.

### SG7 step 3: the sparse hjson in sw/

- 2026-10-15. `sw/sync.py` copies `cfg/snax_alu_cluster.hjson` (the copy in
  `sw/cfg/` since removed, CLN1 R2); `SAME_HEADERS` (since removed) checks
  its headers equal the old cluster's, so it runs the same ELFs; on a
  mismatch sync exits 1 with nothing under `sw/` changed.

### SG7 step 4: the sparse pick in the crossbar

- 2026-10-15. `snax/snax_sparse_arb.hpp`, plain C++ shared by the crossbar
  and the check: `SnaxSparseConfig`, `SnaxSparseArb` (priority-1 mask, lock
  on a refusal, next above the last pick, pointer restarted after an idle
  cycle). `snax_tcdm_xbar`: `interconnect` `plain` (since removed, CLN1 R2)
  or `sparse`; `bank_refuses()` the one place a bank refuses its winner;
  `!` marks a priority-1 request in the trace. Plain path byte-identical.

### SG7 step 5: the winner check

- 2026-10-15. `tests/snax/sparse_arb/` (README there), by hand: Verilator
  5.024 runs the elaborated `SparseInterconnect.sv` against
  `snax_sparse_arb.hpp`, same random stimulus, per bank and cycle.
- 20000 cycles, seeds 1 to 3, three configurations: 0 differences in all
  nine runs (seed 1: 56885, 104766 and 42244 selections). Copies with one
  rule broken (no idle restart, no lock, priority ignored): 1534, 1244 and
  8248 differences, exit 1.

### SG7 step 6: the streamer's priority bit

- 2026-10-15. Rule (in `SG7.md`): a new request carries the lane queue's
  hint of the cycle before (reader `count <= 1`, writer `count >=
  fifo_depth - 1`); a resent request keeps its bit.
- `snax_streamer`: `dynamicPriority` / `higherStaticPriority` per channel;
  the bit on a `wire<bool>` per SNAX port (`prio_<i>`), so an unwired port
  asks with 0. Plain target unchanged; readers' bits checked by hand on
  `ab_same_banks`; the writer's not.

### SG7 step 7: the snax_alu_sparse target

- 2026-10-15. `snax/snax_alu_sparse.py` (since removed, CLN1 R2):
  `snax_alu` with `{0: [[12, 1]]}`; `snitch_cluster.py` passes
  `snax_interconnect` (since removed) and `snax_sparse_config`.
  `regress.py` runs each SNAX ELF per target as `<program>.<target>`.
  `regression passed`, 28 SNAX and 17 plain.

### SG7 step 8: predictions

- 2026-10-15. In `SG7.md`, "Predictions", committed before any sparse run,
  from a Python predictor that first reproduced every plain-target grant.
  Every compared counter as on the plain RTL but `out_one_bank`'s 982, 74
  against 72 (priority). New `stream-timing` cases `prio_queued` and
  `idle_restart`: 5 plain, 6 sparse.

### SG7 step 9: runs and comparison

- 2026-10-15. 13 ELFs on both targets and the sparse RTL (`9fbf35d`,
  Questa 2022.4); the plain RTL for the two new cases. All `[SUCCESS]`.
- Every prediction held: `stream-timing` equal on all four sides;
  `alu-timing` (since removed, CLN1 R2) `out_one_bank` 982 74 sparse, 72
  plain; `snax-alu` 1, 25, 32, 256, 1024 cycles, 0 errors; the sparse RTL
  equals SG5's plain phases, the sparse target the plain target's.
- No new gap; the core's timing as before (start gap -5 against -7, open
  items 65 to 67). Not verified: RTL grants one by one; the writer's
  priority bit against the RTL signal; the lock in GVSoC.

### SG7 round 3, step 2: the crossbar, holding inputs and sub-word accesses

- 2026-10-15. Plan in `SG7.md`, "Round 3". `snax_tcdm_xbar`: `holds` per
  input (a loser retries next cycle; a request after its cycle's
  arbitration is fatal); the router's latency added to the bank's; 1 to
  8 byte accesses inside a bank word, a crossing one refused; AMOs and
  LR/SC to the bank. A router's `grant()` reaches `Lsu::data_grant`, a
  no-op for Snitch (`nb_outstanding` 1). Nothing wired yet: 49 `run.log`
  byte-identical.

### SG7 round 3, step 3: the cores and AXI into the crossbar

- 2026-10-15. `snitch_cluster.py`: crossbar inputs the SNAX ports, `core0`,
  `core1`, `axi`; the three hold, priority 0. 15 inputs as the RTL.
- `regression passed`; `dma-timing`'s `l2l1 4x800` moved to done 96, busy
  81: its copies met GVSoC's HTIF `tohost` poll (round 3b, step 3). Its
  cores make 1- and 4-byte L1 accesses; no AMO in L1, nothing on `axi`.

### SG7 round 3, step 4: D125 fitted again

- 2026-10-15. L1 load to next load 4 cycles, the RTL's, so `tcdm` stays 2:
  the crossbar's cycle replaces the LSU's `latency + 1`. The core waited for
  an L1 load's data: C5 +5% (replaced in round 3b, step 2). `snax_alu.py`
  (since removed, CLN1 R2) said why 2 gives 4.

### SG7 round 3, step 5: core-tcdm and its predictions

- 2026-10-15. `sw/apps/core-tcdm`: `subword` (sub-word, AMO, LR/SC),
  `core_vs_reader`, `after_stores`, on both targets. Predictions in
  `SG7.md`, "Predictions of round 3", before any run; `subword` predicted
  to fail its SC on the sparse RTL.

### SG7 round 3, step 6: runs and comparison

- 2026-10-15. 16 ELFs on both targets and both RTLs at `9fbf35d`; all
  `[SUCCESS]` but `subword` on the sparse RTL (exit 2, predicted). The plain
  RTL at the pin gives every value borrowed from SG3 and SG4. Plain RTL
  grants read from `vsim.wlf` (`req_q_valid_flat`, `rsp_q_ready_flat`,
  `bank_select`).
- `subword`'s SC fails on the sparse RTL: snax_cluster's
  `sparse_interconnect_wrapper.sv.tpl` leaves the AMO shim's `core_id` and
  `is_core` undriven (SG8). `ab_same_banks`: B first on the plain RTL
  (`rr_q` 12), now on the plain target too.
- `core_vs_reader` 17 on the plain target against 18: an I-cache miss on
  the start write's line (open item 65; layout fixed in round 3b, step 4).
- Not observed: the sparse RTL's grants (Chisel module); `axi` (input 14)
  on any side (open item 69); core 1 against a streamer channel.

### SG7 round 3b, step 1: the plan

- 2026-10-16. Plan in `SG7.md`, "Round 3b". `subword` on the sparse RTL
  noted as snax_cluster's.

### SG7 round 3b, step 2: the core goes on after a pending L1 load

- 2026-10-16. On the Snitch core's own scoreboard (`scoreboard_reg_valid`,
  `int_offload_exec`), not `CONFIG_GVSOC_ISS_LSU_NB_OUTSTANDING`. With
  `int_loads_in_flight` (SNAX targets): a load answered `IO_REQ_PENDING`
  invalidates its register and the core goes on; `wait_for_load()` stalls
  the next memory access or a user of the register; stores, AMOs, LR/SC
  still wait.
- L1 load to load 4; C5 44 cycles per element (round 3: 47, RTL 45).
- Gaps (open items 70, 71): a store or AMO after a pending load waits for
  its data; an L1 load after a DRAM load reaches the crossbar up to 13
  cycles early. The trace prints a pending load's register before its data.

### SG7 round 3b, step 3: GVSoC's tohost poll

- 2026-10-16. `Htif::htif_handler` polled `tohost` every 1000 cycles, a byte
  per request, on the data ports of four pollers (both cores and both FP
  subsystems), moving the routers' bandwidth stamps. With
  `htif_poll_backdoor` (SNAX targets) `Htif::poll_access` goes through
  `debug_mem_access`, zero time, same value and period; syscall accesses
  stay on the port (their buffers may be in L1, which has no backdoor).
- `dma-timing`'s `l2l1 4x800` done 80, busy 65 (RTL 84, 65), every line SG2
  step 7's. C5 44 per element in 4094 of 4096 iterations (the slower ones
  were the poll); C6 still on the host's 1000-cycle grid.

### SG7 round 3b, step 4: core_vs_reader

- 2026-10-16. Round 3's 17 came from the core's arrival, not the
  arbitration. `start_and_load` puts the start write and both loads in one
  `.balign 32` line, called twice. Measured run 18 on all four sides;
  first run 18 plain RTL, 17 elsewhere. Sparse not as predicted (17): the
  readers' queues hold the first run's words, so they ask with 0. Kept, as
  the four sides agree; the compared counter no longer shows the core
  behind priority-1 readers (the first run still does, not compared).

### SG7 round 3b, step 5: runs and comparison

- 2026-10-16. 17 ELFs on both targets; RTL from round 3 step 6 and step 4.
  Every compared counter matches on each interconnect but `subword` on the
  sparse RTL; `core_vs_reader` 18 on all four. `snax-alu`, RTL (SG5) /
  round 3 / now, both targets the same:

  | Phase | 128 | 1024 | 4096 |
  |---|---|---|---|
  | C1 barrier | 147 / 157 / 154 (+5%) | 373 / 384 / 381 (+2%) | 1153 / 1174 / 1161 (+1%) |
  | D2 DMA wait | 45 / 36 / 36 (-20%, accepted in SG5) | 270 / 262 / 262 (-3%) | 1050 / 1052 / 1042 (-1%) |
  | C3 ALU poll | 37 / 39 / 39 (+5%) | 262 / 261 / 261 (0%) | 1032 / 1029 / 1029 (0%) |
  | C5 check loop | 5795 / 6098 / 5683 (-2%) | 46115 / 48446 / 45107 (-2%) | 184355 / 193543 / 180275 (-2%) |
  | Total up to 982 | 6713 / 7093 / 6661 (-1%) | 47495 / 49916 / 46552 (-2%) | 187285 / 196571 / 183268 (-2%) |

  Tiers 1 and 2 hold. `regression passed`, 38 SNAX and 17 plain.

### SG7 round 4, step 1: the plan

- 2026-10-16. Plan in `SG7.md`, "Round 4": superbank mux, both
  interconnects' lock, a `dma` port. The streamer's commit relies on
  running after the arbitration, so it cannot move to the cycle's end.
  `IDmaBeTcdm::read_line` enqueues at latency 0, only in an L1-to-L1 copy.

### SG7 round 4, step 2: the plain path's lock

- 2026-10-16. `snax/snax_plain_arb.hpp` (`SnaxPlainArb`) with
  `rr_arb_tree`'s `LockIn`; checked against `rr_arb_tree.sv` v1.40.0 in
  `tests/snax/plain_arb/` (both since removed, CLN1 R2): 100000 cycles,
  seeds 1 to 3, 0 differences; broken copies 27128 and 11605.

### SG7 round 4, step 3: the DMA's wide input

- 2026-10-16. `snax_tcdm_xbar`: port `dma`, `superbank_banks`. A beat takes
  its superbank for the cycle and refuses the narrow winner there (locked
  by each interconnect's rule); a line-crossing request is refused; a late
  beat on a bank granted that cycle is fatal. `snitch_cluster.py` binds the
  iDMA there with `snax_dma_data_width` (512: 8 banks, 64 B), no
  `DmaInterleaver`. A short or unaligned beat inside a line is the RTL's
  beat with partial strobes (`dma-timing`'s 800 B copies). `dma-timing`
  unchanged, 602 beats, none refusing.

### SG7 round 4, step 4: dma-tcdm and its predictions

- 2026-10-16. `sw/apps/dma-tcdm`, `dma_vs_reader`: four 64 B DMA copies
  onto superbank 3 (first run) then 0 (A's banks). Predicted before any
  run (`SG7.md`): 264 measured, 260 first, on all four sides.

### SG7 round 4, step 5: runs and comparison

- 2026-10-16. `dma_vs_reader` 977 264 (260) on all four sides, as
  predicted; 982 266 RTL, 268 targets (start gap, not compared). GVSoC's
  beats at +69 to +89 from A's first grant, the RTL's at +74 to +98, A's
  lanes refused in exactly those cycles.
- `dma-timing`: both RTLs equal SG2 step 3's; `busy`, `r`, `w` equal on
  every line; `done` 2 to 6 under the RTL (the core, SG5).
- Other programs: output and phases equal to round 3b's; their DMA beats
  (`snax-alu` 2 to 1040, `dma-timing` 602) refuse none.
- `regression passed`, 40 SNAX and 17 plain. Not verified: a late DMA beat
  (needs an L1-to-L1 copy, open item 72); a core or AXI request refused.

### SG7 round 4 follow-up, step 1: where the DMA's beat cycles come from

- 2026-10-16. Split in `SG7.md`, "Round 4 follow-up": (a) the `dmcpyi`
  cycle, (b) its beat in L1, from GVSoC's traces and the RTL's waveforms;
  both RTLs' DMA events identical. A `dmcpyi` in the cycle a line was
  acknowledged ran with events already queued ((b) 12). `tcdm_write_latency`
  2 in `IDmaBeTcdm` and `one_cycle_per_stage` in `IDmaMe2D`, `IDmaBe`,
  `IDmaBeAxi` (SNAX targets): beat in L1 16 cycles after `dmcpyi`, the
  RTL's. Left: open items 67 and 73.

### SG7 round 4 follow-up, step 2: dma-timing against the RTL

- 2026-10-16. `dma-timing` checks the RTL's `busy`, `r`, `w`: 0 off on both
  targets; `read_latency` 6 gives 8 off, exit 1. On the plain RTL the new
  ELF's `issue` and `done` moved with the code layout: why they are not
  compared.

### SG7 round 5: SG7 closed

- 2026-10-16. No model or program change (`docs/plans/SG7.md`, "Result").
  Every compared counter equal on each interconnect but `subword`'s SC on
  the sparse RTL (snax_cluster #658, SG8); `snax-alu` within SG5's target.
- Settled: priority bit on a wire; both picks checked against their RTL
  modules; cores and AXI as holding inputs 12 to 14; the core going on
  after a pending L1 load; the `tohost` backdoor; the DMA superbank as a
  wide input; `tcdm_write_latency`, `one_cycle_per_stage`; the
  `dma-timing` drift guard. Upstream files: rows marked SG7 in
  `UPSTREAM.md`.
- snax-forge (`ry/sg7-docs`): D119, D121, D122, D124, D125, D126 amended;
  open item 58 closed; 69 to 75 and SG8 added. Open: 65 to 67, 69 to 75.
- `regression passed`, 40 SNAX and 17 plain. Next: SG8, open item 68, GEN1.

### SG8: the sparse interconnect's LR/SC

- 2026-10-16. snax_cluster's Chisel `TcdmReq` had no user field, so the
  sparse wrapper left `mem_req_o[].q.user` undriven: each bank's AMO shim saw
  `core_id` X, no SC succeeded (`core-tcdm` `subword`, sparse RTL only).
- Fix: snax_cluster #658 (`05615e4`), the user struct carried to the banks.
  Ryan's Questa run: `subword` 0 errors; `stream-timing`, `alu-timing` and
  `snax-alu` (both since removed), `core-tcdm`, `dma-tcdm` as SG7. No model
  change. Pin moved to `05615e4`; `make regress` passed (SNAX 40, plain 17).
  Every compared counter is now equal on the sparse RTL and target.

### GEN3: the plan

- 2026-10-17. `docs/plans/GEN3.md`: a BRM's design point gives a generated
  accelerator on `SnaxUnit` and `SnaxShell`, on snax-forge's D127 to D130.
  "What it models" read from source, not run.

### GEN3 step 0a: SNAX-GVSoC from snax-forge

- 2026-10-18. This repo became snax-forge's submodule `gvsoc/snax-gvsoc`
  (not fetched by its CI), driven by snax-forge's `gvsoc/Makefile` (`build`,
  `sw`, `run`, install in `out/snax-gvsoc/`). CMake refuses a build folder
  from another checkout, so `build` clears it when the checkout changes.
- The install's `gvrun` puts its own `targets` and `generators` first on
  `sys.path`: an installed module shadows a `--target-dir` one. gvrun needs
  the image's `/opt/venv` python; under `pixi run` it lacks `rich`.

### GEN3 step 0b: the probe

- 2026-10-18. snax-forge `gvsoc/targets/alu_probe.py` (since removed, with
  `gvsoc/targets/`): a built target under another name. gvrun stopped on
  the missing `libplatform_tree_alu_probe.so` (fallback in round 1b F1).
- Found: the platform tree holds names, bindings and `.so` names, no SNAX
  property; a property (`fifo_depth`) reaches the C++ through
  `gvsoc_config.json` with nothing compiled. SNAX components read every
  property with `get_js_config` (GEN3.md).

### GEN3 step 1: SnaxUnit

- 2026-10-18. `snax/snax_unit.hpp` (`SnaxUnitRule`, op table, no GVSoC
  dependency), `snax_unit.cpp` + `.py`, `tests/snax/unit/`. A start is
  taken idle with count != 0; busy s + 1 to E. `lockstep` fires when every
  input has a beat and the output room; `pipelined` is accel.py's L slots
  and II. Classes in D59's order. Beats are one 64-bit word per channel,
  so `lanes * data_width` is a multiple of 64. `run.sh`: 11 passed.

### GEN3 step 2: SnaxShell, the held start, the stand-in target

- 2026-10-18. `snax/snax_shell.cpp` + `.py` on `SnaxCsrBlock` (D130): the
  fields and start; busy and counter read-only. A start while busy answers
  `IO_REQ_PENDING` and is sent in E + 1; the counter is reset by an
  accepted start and counts busy cycles.
- Snitch core: a pending SNAX CSR write stalls the instruction until the
  response, as an LSU access (UPSTREAM.md); a pending read stays fatal.
  All 57 regress logs byte-identical with it.
- Stand-in target `snax_tiled_add` (`SnaxTiledAddAcc`, since removed) ran
  `sw/apps/snax-shell/` through regress's `OWN_TARGET` (since removed).
  Trace: start 2 held at 2843, accepted 2859 (E + 1). The first run's busy
  cycles follow the code layout (16 or 17).

### GEN3 round 1b F1: a target without its platform tree

- 2026-10-18. `runner_gvrun2.py`: no `libplatform_tree_<target>.so` gives
  `Warning: target '<target>': no platform tree, using the JSON config`
  and runs (UPSTREAM.md). snax-forge's probes (`tiled_add_sparse_probe`,
  since removed, a tree no built target had) ran with nothing compiled;
  regress logs byte-identical, 58 of 58.

### GEN3 round 1b F2: flush in the unit's run line

- 2026-10-18. Class `IDLE` became `FLUSH`: the run line is `run <i>: firings
  <f> busy <b> stall_in <si> stall_out <so> flush <fl>`. Flush: cycles
  after the last firing with results in the pipeline, frozen ones left to
  stall_out, so the four add up to E - s, the shell counter. tb.cpp checks
  the sum; 11 passed.

### GEN3 round 1b F3: snax-shell without layout constants

- 2026-10-18. snax-shell: three unit runs of `RUN_BEATS` (start 1 alone, its
  counter read; starts 2 and 3, 3 held), DATA_LEN 192, checks that hold for
  any layout; `data.h` depends on the Makefile.
- `regress.py` `check_counter`: the program's counter equals run 0's busy +
  stall_in + stall_out + flush, and run 0 fired `beats` times. snax-shell:
  `counter: 17`, held span 19, `errors: 0`.

### GEN3 round 1b F4: the target-name rule, the open edge cases

- 2026-10-18. A generated target never takes an installed target's name
  (tried: a `--target-dir` module of an installed name never loads). Open:
  a start written in E; `csrrw` rd != x0 on a held start.

### GEN3 step 3: the binding and the generator

- 2026-10-18. snax-forge after LNK1 (`platforms/snax_alu.json`, since
  removed: now `platforms/snax_forge.json`): `elementwise_add`'s binding;
  `snax_forge/gen/` (D132), `pixi run gen-gvsoc DESIGN_POINT`, the streamer
  template from the design point (`num_channel` = `n_ports * N / 64`).
- Out: `forge_<design>_acc.py` and `forge_<design>.py` (since removed:
  hjson only, D134), `manifest.json`; trace `snax_acc0/unit`.
- vecadd W = 4: 12 TCDM ports, streamer CSRs 960 to 977, `loopCount` 978,
  start 979, busy 980, counter 981, task `add_acc` 16 beats;
  `forge_vecadd` (since removed) gave `snax_tiled_add`'s lines on
  snax-shell. W = 8 generated only: 24 ports, 8 beats.

### GEN3 step 4: the headers

- 2026-10-18. snax-forge `gen/headers.py`: `streamer_csr_addr_map.h` in
  `Streamer.scala`'s order and `<instance>_csr.h` (`<INST>_RW_<FIELD>`,
  `_RW_START`, `_RO_BUSY`, `_RO_PERF_COUNT`). vecadd's 36 streamer defines
  equal the Chisel header's (960 to 977); `acc_csr.h` 978 to 981, equal to
  snax-shell's `SHELL_*` constants (since removed).

### GEN3 round 2b: fix-ups after round 2

- 2026-10-18. snax-forge. F1: `pixi.lock` written with pixi 0.41.4, CI's;
  DaCe 1.0.2's sdist asks for `scikit-build` and `cmake` only with no cmake
  >= 3.15 on PATH; nothing uses them. Lock in the image.
- F2: 1693 passed; C§14's `memory.fit` row. F3: the design point named by
  its path from snax-forge's root (outside it refused, `gen.point`);
  output byte-identical from any working directory. F4: the install check
  (since removed, LNK2a round 2).

### GEN3 step 5, round 3 step 1: the manifest's symbols

- 2026-10-18. snax-forge `6c94630`: `Manifest.symbols`, the bound graph's
  (vecadd `{"N": 64}`); its `gen.symbols` refusal dropped in round 3b F3.

### GEN3 step 5, round 3 step 2: the vecadd fixture

- 2026-10-18. `forge/vecadd/`: snax-forge's generator output, untouched;
  one design point per folder, refreshed by hand, its diff the check (D128).

### GEN3 step 5, round 3 step 3: the program forge-elementwise

- 2026-10-18. `sw/apps/forge-elementwise/` (since renamed `sw/apps/forge/`,
  GEN2a): DATA_LEN from the manifest, the fixture's `include/`; vecadd's
  task list but `store_C`. vecadd: `0 errors (64 words)`, `counter: 16`;
  mul data on it: `errors: 64`.

### GEN3 step 5, round 3 step 4: regress from the manifest

- 2026-10-18. `regress.py` `FORGE`: each manifest read with plain json, the
  program built per design, run with its `--target-dir` and trace, checked
  by `check_counter` against its one task's beats. `-k forge` passed.

### GEN3 step 5, round 3 step 5: snax-forge reproduces the fixture

- 2026-10-18. snax-forge `tests/gen/test_fixture.py`: the refresh commands
  in a temporary root must give the submodule's `forge/<design>/` byte for
  byte; skipped without it. Passed on this branch; a byte changed fails.

### GEN3 step 6a: elementwise_mul

- 2026-10-18. snax-forge: `elementwise_mul` bound as `elementwise_add`
  (mul = 2), `kernels/polybench/vecmul.py`, `recipes/vecmul.json`.
  `forge/vecmul/` differs from vecadd only in names and `op=2`. `-k forge`:
  2 passed; snax-forge's fixture test passes both.

### GEN3 step 7: the lockstep half of the unit cross-check

- 2026-10-18. snax-forge `ElementwiseTiledSpatialLockstepSpec` reads
  `tests/snax/unit/cases/` from `SNAX_GVSOC_UNIT_CASES` (canceled without
  it) and drives the Chisel block through every lockstep case: fire, push,
  busy and each start agree per cycle; a flipped bit fails it.

### GEN3 round 3: docs and the full runs

- 2026-10-18. GEN3.md: step 6 split into 6a (done) and 6b (round 4).
  snax-forge D128 amended (each design point regress runs is a fixture in
  `forge/<design>/`). `make regress` passed (forge 2), nothing compiled.

### GEN3 round 3b F1: no __pycache__ in forge/

- 2026-10-18. `regress.py`'s `gvrun()` sets `PYTHONDONTWRITEBYTECODE=1`;
  `.gitignore` covers hand runs. snax-forge's fixture test no longer needs
  its `__pycache__` exclusion.

### GEN3 round 3b F2: BEATS and LANES from the manifest

- 2026-10-18. The app's `BEATS` from `tasks[0].beats`, `LANES = N / BEATS`
  (a make error if it does not divide). vecadd, vecmul: counter 19, not 16
  (`stall_in 3`): with BEATS an immediate the starts follow the
  configuration sooner, less head start for the streamer (read, not
  traced).

### GEN3 round 3b F3: drop gen.symbols (snax-forge)

- 2026-10-18. snax-forge `c817e7e`: `gen.symbols` removed;
  `DesignPoint.load` already refuses a null symbol, before anything is
  written.

### GEN3 round 3b F4: make regress K=

- 2026-10-18. `make regress K=<substring>` runs `regress.py -k
  <substring>` (make itself takes `-k`).

### GEN3 round 4, step 1: the Accumulator with start, busy and no drain cycle

- 2026-10-19. snax-forge (D133): `Accumulator.scala` with `start`, `busy`,
  `done`, `loopCount` (n) and `len` (T) latched at a start. `out.valid` the
  cycle after a sum's T-th input: T cycles per sum, no drain cycle.
  `in.ready` needs `!allIn`, or the block takes the next run's first beat
  as its last sum leaves. n not a multiple of T: the last sum ends at n.

### GEN3 round 4, step 2: SnaxUnit for one-input reductions

- 2026-10-19. `start(cycle, count, rate = 1)`: a pipelined firing gives a
  result on every rate-th firing, and only a result enters the pipeline;
  L 1, II 1 needs no drain. One input is a fold; property `config` names
  the start words (`count`, `rate`; default `['count']`).
- Five `pipelined_rate_*` cases (`pipelined_rate_t4`: `firings 8 busy 8
  stall_in 0 stall_out 0 flush 1`): 16 passed. Other regress logs equal
  main's, traced ones with port pointers masked (they vary run to run).

### GEN3 round 4, step 3: the Accumulator's binding, its adapter and vsum (snax-forge)

- 2026-10-19. snax-forge: `chisel_accumulator` drain 1 to 0 (D133, D103
  amended), bound to `Accumulator` (`loopCount = n`, `len = T`); D129:
  `counted` the only control. No cycle count moved. `gen/blocks.py`'s
  adapter (`config ['count', 'rate']`); `recipes/vsum.json` (W 1, N 64):
  `loopCount` 973, `len` 974, counter 977, task `sum_acc` 64 beats.

### GEN3 round 4, step 4: the vsum fixture and forge-reduce

- 2026-10-19. `forge/vsum/`; `sw/apps/forge-reduce/` (N, BEATS, RATE from
  the manifest). `forge-reduce.vsum`: `run 0: firings 64 busy 64 stall_in 2
  stall_out 0 flush 1`, 0 errors, counter 67.

### GEN3 round 4, step 5: the fixture test over vecadd, vecmul and vsum (snax-forge)

- 2026-10-19. snax-forge's fixture test holds vsum: 3 passed with the
  submodule on `ry/gen3r4`; a changed byte fails vsum only.

### GEN3 round 4, step 6: the Accumulator against SnaxUnit's rate cases (snax-forge)

- 2026-10-19. snax-forge `SnaxUnitCases` (the shared case parser);
  `AccumulatorRateSpec` drives the Accumulator through the rate cases,
  checking fire, push, busy, starts, sums and `expect run` per cycle. 55
  passed; the old drain cycle fails at `pipelined_rate_backpressure`.

### GEN3 round 4, step 7: docs and full runs

- 2026-10-19. GEN3.md 6b done; Open: T < n only in unit cases, n not a
  multiple of T, the combinational `in.ready`, `chisel_adder_tree`.
  `make regress` passed (forge 3); snax-forge 1721 passed. GEN3's
  acceptance met: vecadd, vecmul and vsum correct with the counter
  `check_counter` predicts, all three reproduced by snax-forge.

### GEN3 round 4b, F1: more than one sum per run

- 2026-10-19. forge-reduce's `RATE_OVERRIDE` replaces the manifest's len;
  regress's `forge-reduce.vsum-r16` runs the multi-output path until a
  kernel gives T < N: start at 2280, 4 sums (132, 1580, -5582, 5095),
  counter 67.

### GEN3 round 4b, F2: snax-forge's STATUS (snax-forge)

- 2026-10-19. snax-forge STATUS: M14 `wip`, GEN3 done, LNK2a next.

### LNK2a round 1, steps 1 to 5: the target read from the hjson

- 2026-10-19. Findings in `docs/plans/LNK2a.md`. `ClusterArch.Tcdm` takes
  size, banks, bank width (UPSTREAM.md). `make build` recompiles
  `cluster_registers` every time (not looked into).
- `snax/snax_cfg.py`, `snax/snax_hjson.py` (`--param hjson=`, the cluster
  files in `install/generators/cfg/`), `snax/snax_unit_acc.py`. The forge
  fixtures became hjson (`snax_alu.hjson`, since renamed
  `snax_forge*.hjson`) on `snax_hjson`; the `snax_alu` targets (since
  removed) became `SnaxHjsonBoard`. Every program equal on both.
- Cycles as main: vecadd start 2420, counter 19; vecmul 2414, 19; vsum
  2245, 67; vsum-r16 2280, 67.

### LNK2a round 1, step 6: snax-forge's STATUS (snax-forge)

- 2026-10-19. snax-forge STATUS: LNK2a `wip`; open item 51 (cross-file
  `$ref`), 68 (L1 size and base reach the program via `sw/generated/`).

### LNK2a round 2: snax-forge's writer, three hjson files

- 2026-10-19. snax-forge's D134, C§16. `snax_cfg.py` resolves `{$ref:
  "file.hjson"}`; snax-forge's `gen/gvsoc.py` writes the three hjson files
  (install check gone); `sw/sync.py` copies the cluster schema. forge/
  rewritten, `include/` byte-identical, cycles as round 1.

### GEN2a round 1, steps 1 to 6: the program from the task list (snax-forge)

- 2026-10-19. `docs/plans/GEN2a.md`; snax-forge's D135. D113: dtype a
  parameter, integers first. `gen/data.py` writes `data.h` (goldens, whole
  beats, 64 B aligned); check `memory.runtime`; `lower/c.py` the task list
  to `main.c` (image's clang: no RISC-V GCC); `gen-gvsoc` writes both.

### GEN2a round 1, steps 7 to 9: the plan, the generic app and regress

- 2026-10-19. `sw/apps/forge/` builds `forge/$(DESIGN)/main.c`; regress runs
  each folder (`forge.<design>`) plus `forge-reduce.vsum-r16`
  (`FORGE_REDUCE`); `check_counters` matches the k-th task to `run k:`.
  Clang's per-core threading duplicated `forge_main_exit` (since removed;
  fixed in round 1b F3). Counters replaced in round 1b F1.

### GEN2a round 1, step 10: the marks and the runtime margin

- 2026-10-19. vecadd: 23 `forge_*` mark symbols, each pc in the trace once
  on its core. start.S keeps 40 B of snax-forge's 256 B margin; the TLS is
  inside each stack.

### GEN2a round 1, step 11: docs and the full regress

- 2026-10-19. `make regress` passed (forge 4). Not verified: the ELFs on
  RTL (GEN2b); `check_counters` past run 0.

### GEN2a round 1b: the start marks, the DMA waits, one function per core

- 2026-10-20. snax-forge's `lower/c.py` (D135 amended). F1: a start's marks
  before its first write: counters 19, 19, 67 (vecadd, vecmul, vsum), as
  the hand-written apps. F2: the DMA waited for on dependences only (the
  iDMA queues). F3: one `noinline` function per core via `forge_cores`.
- Starts 2922, 2923, 2324 against 2420, 2414, 2245 by hand: about 470 of
  vecadd's 500 cycles come before main (snRuntime zeroing a larger `.bss`).

### GEN2a round 2: the adder tree

- 2026-10-20. `SnaxUnit`'s fold takes W lanes through `snax_unit_tree`;
  snax-forge's Accumulator a `reduceTree` (D133), `chisel_adder_tree` bound.
  `forge/vsum_tree/` (W 4, 16 beats): 0 errors, counter 19, `run 0:
  firings 16 busy 16 stall_in 2 stall_out 0 flush 1`. regress forge 5.
- 2026-10-23. LNK2b round 3: sync to snax_cluster `cf4b0002` (#659), new
  cluster schema. `SNAX_ACC_CSR_LAST = 0x5FD`: 0x5FE and 0x5FF go to the
  cluster's top-level CSR port, so `SnaxUnitAcc` refuses a counter past it.
- 2026-10-23. GEN2b round 3: `SnaxShellRule` in `snax/snax_shell.hpp`,
  `tests/snax/shell/` (8 cases) in `make regress`; logs equal main's; the
  same cases pass snax-forge's `ShellCasesSpec`.

### M13 B0 round 6: forge-reduce retired (snax-forge)

- 2026-10-26. `forge-reduce` retired in snax-forge's M13 B0: its hand-set
  `len` is replaced by the `rowsum_serial` fixture (T = 16, four sums), and
  snax-forge's open item 81 is closed. `forge/rowsum/` (W 4, M 8, N 64: 128
  beats, `len` 16, eight sums): counter 131. `forge/rowsum_serial/` (W 1,
  M 4, N 16: 64 beats, `len` 16): counter 67, `run 0: firings 64 busy 64
  stall_in 2 stall_out 0 flush 1`, as `vsum-r16`'s.
