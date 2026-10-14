# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what was learned. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the programs and the RTL reference | `b2672f81bad52654bb3f1549cbe009f8ad8e1faf` (2026-10-13); SG0 used `8ebd422` |
| common_cells, read for the TCDM arbiter (SG3) | `v1.40.0` (`1281545`); the RTL build's commit is checked in SG3 step 4 |

## Log

### SG0 step 1: detached copy

- 2026-10-12. Done as written in `UPSTREAM.md` under "How the copy was made";
  rehearsed in Claude's sandbox first with the same result.
- The git on micas-lapserv1 has no `subtree` command. The clone and the
  folding ran in the `snax-gvsoc:gvs1` container (Ubuntu 24.04, git 2.43),
  the push from the host.
- Checks: each folded folder's tree equals its upstream pin; commit counts
  config_tree 4, core 2080, engine 2013, gvrun 54, gvtest 67, pulp 607,
  pulpos 63. About 210 MB pushed. Only `main`; upstream has no tags.
- GitHub Actions was turned off before the first push, since upstream's
  workflow builds every target on each push. P1 removes it.

### SG0 step 2: P1

- 2026-10-12. `UPSTREAM.md`, a short README, this file and the SG0 plan.
  Upstream's CI workflow and CODEOWNERS removed (listed in `UPSTREAM.md`).
- `container/` imported from snax-gvsoc-experiment `386e433`, unchanged
  apart from its header comments and line endings (CRLF in the experiment,
  LF here); the image was `snax-gvsoc:sg0` (renamed in P2).
- Checked in Claude's sandbox, not in the container (Ubuntu 24.04, a Python
  3.13 venv with `container/requirements.txt`, 2 cores): at the repo root
  `make build TARGETS=snitch` took 9 min 11 s; the bundled
  `fp32_computation_vector.elf` exits 0 in 2 s; `--trace=pe0/insn` gives 484
  lines from cycle 7909 to 23862, as in the experiment. The figures are from
  Claude's run.

### SG0 step 4: P2, snax_cluster's toolchain

- 2026-10-12. `container/` has two stages, after snax_cluster's
  `util/container/Dockerfile` at `8ebd422`: pixi 0.81.0 installs
  `container/toolchain` (the exact builds of snax_cluster's `pixi.lock`:
  clang, lld, llvm-tools, clang-format 21.1.6, bender 0.28.2 from
  kuleuven-micas), and only the environment is copied into the image, at the
  same path, its `bin` last on PATH. rv64 GCC and Snitch LLVM 12 are gone;
  the tutorials keep them in the experiment's `gvs1` image.
- zsh with oh-my-zsh `083c339` and zsh-autosuggestions `v0.7.1`, as
  snax_cluster's image had them at `53efdeb`, but at fixed versions and with
  oh-my-zsh's update check off. GVSoC's `sourceme.sh` handles zsh.
- The image is `snax-gvsoc:main` from now on; `:gvs1` stays for the
  experiment.
- Rehearsed in Claude's sandbox with a stand-in toolchain: conda-forge and
  ghcr.io are blocked there and it has no Docker daemon, so LLVM 21.1.6 came
  from the GitHub release and bender 0.28.2 from its GitHub release.
  snax_cluster `8ebd422` needs its own submodules
  (`git submodule update --init --recursive`) and internet on its first build
  (bender fetches `register_interface`); then
  `make sw CFG_OVERRIDE=cfg/snitch_cluster.hjson` in `target/snitch_cluster`
  builds 17 test ELFs with the image's Python packages.
- Probe preview with that build: `simple.elf` stops at cycle 3946 with
  `Accessing unsupported CSR (id: 0xbc1, name: unknown)` and exits 1;
  `printf_simple.elf` prints nothing. Step 5 confirms it. The figures are from
  Claude's run.
- Not checked in the sandbox: the image build, the conda packages, the zsh
  prompt.
- On the author's side the checks of P2 passed: the lock made with pixi
  0.81.0, the image built (2.26 GB), the toolchain checks in it, and on the
  MICAS server the zsh prompt, the GVSoC build and the bundled ELF.
- P2b: the image no longer sets `GVSOC_WORKDIR` or `WORKDIR /work`. The repo
  is mounted at its own path (`-v "$PWD":"$PWD" -w "$PWD"`, as in
  snax_cluster's README), and GVSoC writes to `build/` and `install/` in the
  repo, both in upstream's `.gitignore`. Checked in Claude's sandbox: the
  build lands there, `git status` stays clean, `gvrun` comes from
  `install/bin` and the bundled ELF exits 0. A build tree made under `/work`
  has that path in its CMake cache, so `build/` is deleted once.
- Build times are not tracked; GVSoC builds in a few minutes on the MICAS
  servers.

### SG0 step 5: the probe

- 2026-10-12. snax_cluster `8ebd422` checked out beside the repo with its
  submodules; its plain tests built with its own flow
  (`make sw CFG_OVERRIDE=cfg/snitch_cluster.hjson`: clang 21.1.6,
  `rtl-generic` runtime, its start-up code and linker script) and run on
  `gvrun --target snitch` at `93cedc4`. Commands in the README.
- Result: `simple.elf` stops at cycle 3946 with
  `Accessing unsupported CSR (id: 0xbc1, name: unknown)` and exits 1;
  `printf_simple.elf` prints nothing.
- Cause: snax_cluster's start-up code (`sw/snRuntime/src/start.S`,
  `team.h`) reads the cluster base address from 0xBC1 and 0xBC2 and
  {core count, core index} from 0xBC3, three CSRs snax_cluster added to
  Snitch (`hw/snitch/src/snitch_pkg.sv`; 0xBC3 is `{NrCores, i}` in
  `snitch_cluster.sv`). Upstream's start-up code works these out from
  `mhartid`, so the experiment's upstream tests never needed them.
- What matches: boot address 0x1000, cluster base 0x1000_0000, TCDM 128 KiB
  in 32 banks, peripherals and zero memory, DRAM at 0x8000_0000, nine cores,
  and the peripheral register file (byte-identical). snax_cluster forked
  upstream snitch_cluster at `8cae8d2` (2023-12-07), inside the range GVSoC's
  model follows.
- Run in Claude's sandbox (the toolchain stand-in of step 4).

### SG0 step 6: P3, the cluster CSRs

- 2026-10-12. The accurate Snitch core declares 0xBC1, 0xBC2 and 0xBC3 next
  to its barrier CSR, read-only (write mask 0, as the RTL ignores writes).
  The cluster generator passes each core its cluster's base (`arch.base`),
  the core count (`arch.nb_core`) and its index. Four upstream files,
  listed in `UPSTREAM.md`.
- Limits: only the `accurate` core (the default) has them, not `fast`, Spatz
  or the FP subsystem; the base is read as an `int`, so below 2^31; 0xBC2 is
  always 0.
- Result in Claude's sandbox: all 17 tests exit 0 with no CSR warnings;
  `printf_simple` prints `Hello, World!` nine times; core 8 reads
  0xBC1 = 0x10000000 and 0xBC3 = 0x00090008 (9 cores, index 8), as the RTL
  gives. `perf_cnt` reads all zeros, as on upstream (GVS2).
- On the author's side, in the container on the MICAS server: all 17 tests
  pass with P3.

### SG0 step 7: one image, in snax-forge

- 2026-10-13. The image holds tools only, and each repo keeps its own pixi
  environment, so a separate snax-forge image would have been
  `snax-gvsoc:main` plus pixi. Instead there is one image, owned by
  snax-forge as the hub (D118 there): `ghcr.io/kuleuven-micas/snax-forge:main`
  from snax-forge's `container/`, moved there from this repo's `b029ea4`
  unchanged apart from its header and one layer. `container/` is removed here;
  `snax-gvsoc:main` is no longer built, and `:gvs1` stays for the experiment.
- The added layer is pixi 0.41.4, the version snax-forge's CI pins and its
  lock was written with. The toolchain stage keeps 0.81.0: 0.41.4 refuses the
  toolchain lock ("lock file version is 7, but only up to including version 6
  is supported"), checked in Claude's sandbox.
- How it is used: one container started from the folder that holds
  snax-forge, snax-gvsoc and snax_cluster, mounted at its own path.
  `pixi install` in snax-forge writes `snax-forge/.pixi/`, which also works
  from the host with the same pixi version. GVSoC is built outside
  `pixi shell`: snax-forge's environment sets `CC` and `CXX` to conda's gcc.
- `gvrun` ends in `exec python3 -m gvrun`; inside a pixi task that is pixi's
  Python, without GVSoC's packages. Open item 56 in snax-forge, for FLOW3.
- On the author's side: the image built and pushed; on micaseb19 pixi 0.41.4
  runs, snax-forge's `pixi install`, `pixi run check` and `pixi run test`
  pass, and GVSoC builds and runs the bundled ELF in it.

### SG0 step 8: SG0 closed

- 2026-10-13. All steps done.
- Settled:
  - The repository: a detached copy of GVSoC `93cedc4` with its seven
    submodules folded in, history kept; `UPSTREAM.md` holds the pins, the
    license and every changed file.
  - The chosen commit: `93cedc4` with P3 (the cluster CSRs 0xBC1 to 0xBC3).
    snax_cluster `8ebd422`'s plain tests (17, built with its own flow) all
    pass on the `snitch` target. Nothing else differed: boot address, memory
    map, core count and peripheral registers match.
  - The tools: one image, `snax-forge:main` from snax-forge's `container/`
    (D118), with GVSoC's build tools, snax_cluster's clang 21.1.6 and bender
    0.28.2, pixi 0.41.4 and zsh. Programs are built with clang only, as
    snax_cluster builds them for its RTL; there is no RISC-V GCC in the image.
  - The way of working: one container started from the folder that holds
    snax-forge, snax-gvsoc and snax_cluster, mounted at its own path;
    snax_cluster is a plain checkout beside this repo, and only its ELF files
    are run here.
- Where GVSoC keeps the Snitch model (an SG1 item, read for P3): the
  generator is `pulp/pulp/snitch/snitch_core.py` (class `Snitch`, the
  `accurate` core), the cluster `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py`,
  the core's C++ in `core/models/cpu/iss/src/snitch/` with the shared ISS in
  `core/models/cpu/iss/src/`. The `fast` core, Spatz and the FP subsystem are
  separate models.
- SG1 starts from: the stock `snitch` target already matches snax_cluster's
  `cfg/snitch_cluster.hjson` (9 cores, 128 KiB TCDM in 32 banks); what is
  left is generating it from the hjson (for snax_alu's 2-core cluster with
  `rv32ima` cores, for one), and recording cycles per test against the RTL.
- SG2 starts from the list under "SG2 starts from" in `docs/plans/SG0.md`.

### SG1 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG1.md` written: SG1 builds the `snax_alu`
  target from `cfg/snax_alu_cluster_old.hjson` by hand and adds the CSR
  port; the DMA (SG2), the streamer (SG3), the ALU (SG4) and the cycle
  comparison (SG5) follow.
- The snax_cluster pin moves to `b2672f8`, which adds
  `snax_alu_cluster_old.hjson`: the `snax_alu` cluster with the plain
  interconnect (`sparse_interconnect: false`, 12 narrow TCDM ports). The
  sparse interconnect comes after SG5.
- The reference: `snax-alu` on the RTL built from that file prints
  `Accelerator Done!`, `Accelerator Cycles: 25` and `Number of errors: 0`
  (author's run). 25 is `LOOP_ITER` (`LENGTH` 100 over 4 lanes): the ALU's
  counter is set to 1 by the CSR write and counts each busy cycle up to the
  last output, so 25 is one output per cycle. Neither number depends on the
  data values.
- At `b2672f8` snax_cluster's own build does not make the app for the old
  file: `sw/Makefile` names `snax_multi_alu_cluster_old.hjson`, and
  `sw/apps/Makefile` has no branch for it. The copy in step 2 does not need
  either.

### SG1 step 2: P2, the snax-alu app copied in

- 2026-10-13. `tests/snax/snax-alu/` holds snax_cluster `b2672f8`'s app,
  its library and `datagen.py` unchanged, the streamer header that
  `rtl-gen` wrote for the old hjson (from the author's RTL build: streamer
  registers 960 to 977, the ALU's 978 to 982 in `snax-alu-lib.h`), and a
  `data.h` made with NumPy seed 0. Its Makefile builds against the runtime
  of the snax_cluster checkout beside the repo, built with
  `make sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson` (no sbt needed;
  `CFG_CLUSTER_NR_CORES 2`). That build also rebuilds `sw/tests/build/` for
  2 cores, so the 17 plain ELFs of SG0 are kept aside for step 5.
- With the same `data.h`, snax_cluster's own build of the app gives a
  byte-identical ELF.
- On the stock `snitch` target (9 cores): pe0 stops at cycle 9528 with
  `Accessing unsupported CSR (id: 0x3c0, name: unknown)` and exits 1, at
  the first streamer register write.
- Figures from Claude's sandbox run (LLVM 21.1.6 and bender 0.28.2 from
  their GitHub releases, as in SG0 step 4).
- On the author's side, in the container on the MICAS server: the same
  stop on `0x3c0`, at cycle 9639. The sandbox's ELF and runtime come from
  another build of clang 21.1.6 and are not byte-identical to the author's;
  the author's figures are the reference from here on.

### SG1 step 3: P3, the snax_alu target

- 2026-10-13. `snax/snax_alu.py` is the target `snax_alu`: the Snitch chip
  of `pulp/pulp/chips/snitch/snitch.py` with one cluster of 2 cores (hart 0
  computes, hart 1 is the DMA core, as GVSoC takes the last core), 128 KiB
  TCDM in 32 banks, boot ROM at 0x1000, DRAM at 0x8000_0000, and
  `misa` = 0x40001101 (RV32 I, M, A). The values are those of
  `snax_alu_cluster_old.hjson`, written by hand. `snax/CMakeLists.txt`
  installs it where gvrun looks (`install/generators`), as pulp's does.
- GVSoC reads a target twice: `make build` lists its components through
  gapy without `USE_GVRUN`, and gvrun runs it with `USE_GVRUN` set; pulp's
  modules define different arch classes for the two. The build path reuses
  `SnitchArch` with 2 cores; the run path has its own arch tree, since
  `SnitchAttr` fixes 9 cores.
- Upstream edits (in `UPSTREAM.md`): `ClusterArch` passes `misa` to each
  Snitch core, `None` keeping today's value; `Makefile` adds `snax/` to
  `GVSOC_MODULES`.
- `misa` is only the value the CSR reads: the start-up code skips its FP
  register setup when F and D are absent, as on the RTL's `rv32ima` cores.
  GVSoC still executes FP instructions; the RTL would not.
- Results in Claude's sandbox: `simple` and `printf_simple`, rebuilt for 2
  cores in step 2, exit 0; `Hello, World!` twice. In `simple`, pe0 reads
  `misa` = 0x40001101, branches over the FP setup and reaches
  `init_global_pointer` at cycle 3460 (3944 on `snitch`, which reads
  0x4004112d and runs the setup). `snax-alu` stops on `0x3c0` at cycle 8730
  (9528 on `snitch`).
- On the author's side: all four checks pass (`simple` and `printf_simple`
  on `snax_alu`, the skipped FP setup, `snax-alu` stopping on `0x3c0`, a
  plain 9-core ELF on `snitch`).

### SG1 step 4: how a CSR instruction can leave the core

- 2026-10-13. Read at `93cedc4`, no code. `csrrw` and `csrrwi`
  (`core/models/cpu/iss/include/isa/priv.hpp`) first ask
  `iss->csr.get_csr(number)`; if a register object is declared there, its
  virtual `handle()` runs the whole instruction and returns the next PC.
  `csrrs`, `csrrc` and their immediate forms never call `handle()`: they
  call `check_access()` and then `iss_csr_read()` / `iss_csr_write()`, which
  run the object's callbacks. The callbacks get `(is_write, value)` only,
  not the instruction or the CSR number.
- The default `handle()` reads before every write, whatever `rd` is, so a
  plain callback would turn each `csrw` into a read and a write.
- `snax-alu` uses both paths: 17 `csrw` and 2 `csrwi` (`csrrw`, `csrrwi`;
  first counted as 18 and 2, see SG1 step 7)
  and 3 `csrr` (`csrrs`, on 976, 981, 982). objdump names 0x3C0 and up
  `pmpaddr16` and on.
- A CSR can make the core wait: the barrier CSR 0x7C2
  (`src/snitch/snitch.cpp`) sends a request from its callback and calls
  `exec.insn_stall()` if not answered; the answer calls `stalled_dec()` and
  `insn_terminate()`. `dmcpy` (`include/isa/xdma.hpp`) does the same for a
  value, parking `rd` in `exec.stall_reg` until `Exec::offload_grant`.
- The core's `acc_req` / `acc_rsp` ports carry FP instructions to the FP
  subsystem, and `offload` is the DMA core's link to the iDMA: neither is
  the SNAX CSR path.

### SG1 step 5: P4, the CSR port

- 2026-10-13. The accurate Snitch core declares 0x3C0 to 0x5FF in one loop,
  one `SnaxCsr` object each (it carries its number, which the callback path
  does not see), named `snax_csr_<number>`. Every access becomes a 32-bit IO
  request on the new master port `snax_csr`, at byte address 4 * CSR
  number. `csrrw` / `csrrwi` go through `SnaxCsr::handle()`: one write, after
  one read only when `rd` is not `x0` (as shipped, P4 also read for `x0`;
  fixed in P5, see SG1 step 6). The other CSR instructions go through
  the callback. `Snitch.o_SNAX_CSR` binds the port; nothing binds it yet.
- Answers: `IO_REQ_OK` gives the value at once and its latency is counted
  as stall cycles. A pending or denied answer is a fatal error naming the
  CSR, until a block needs one (SG5 looks at the RTL's response timing).
- Unbound port: the same "unsupported CSR" warning as before, now with the
  CSR's name (`snax_csr_960`), and exit 1.
- Cost: only Snitch's own files change, so only that core recompiles. Other
  instructions are untouched; a CSR instruction does the map lookup it did
  before, in a map with 576 more entries. The one `IoReq` is reused, not
  allocated. `handle()` does not go through `iss_csr_write()`, so a `csrw`
  does not switch the core out of its fast execution mode.
- Results in Claude's sandbox: the 17 plain ELFs (9-core build) exit 0 on
  `snitch`; on `snax_alu`, `simple` and `printf_simple` exit 0 and
  `snax-alu` stops at cycle 8730 with `Accessing unsupported CSR (id:
  0x3c0, name: snax_csr_960)`. With a plain memory bound to pe0's port in a
  throwaway edit, the `csrr` reads returned the memory's contents, so the
  busy loop never ended (P5's stub answers 0). That run was also read as
  "every `csrw` was one write", which was wrong: see SG1 step 6.
- On the author's side: the 17 plain ELFs pass on `snitch` and `snax-alu`
  stops on `snax_csr_960` at the same cycle as with P3.

### SG1 step 6: P5, the stub register block

- 2026-10-13. `snax/snax_csr_stub.py` / `.cpp`: an IO slave holding a list
  of read-write CSRs (read back what was written, 0 after reset) and
  read-only CSRs (read 0). The rules follow snax_cluster's
  `ReqRspManager.scala`: read-write registers first, then read-only ones;
  a write past the read-write ones, or any access past the end, fires an
  assertion there. The stub refuses those with a warning naming the CSR.
  The start handshake (bit 0 of the last read-write CSR raises `valid` and
  the write waits for `ready`) is not modelled; it is SG3 / SG4's.
- `snitch_cluster.py`: `ClusterArch` takes `snax_acc`, `{core index:
  function(parent, name) -> component}`; `SnitchCluster` builds each as
  `snax_acc<core>` and binds the core's `o_SNAX_CSR` to its `i_INPUT()`.
  Both arch classes carry it, since `make build` reads the build-time one to
  find the sources to compile. `snax_alu.py` sets `{0: snax_alu_acc}` with
  960 to 975 and 978 to 980 read-write, 976, 977, 981, 982 read-only.
- GVSoC runs with `werror: true` (`gvsoc_config.json`): any
  `force_warning` ends the run at once with exit 1. That is how the
  unsupported-CSR warning stopped `snax-alu`, and how a refused stub access
  stops; the core's fatal for a non-OK answer is then not reached.
- P4 fix: the decoder gives `rd = x0` the index `ISS_NB_REGS` (32), not 0
  (`core/models/cpu/iss/src/decode.cpp`), so `handle()`'s `!= 0` check made
  every `csrw` read first. Upstream's `csrrw_exec` has the same check,
  harmless there. Now `!= ISS_NB_REGS`. Found by counting the stub's
  accesses for `snax-csr`: 129 before, 108 after (66 reads, 42 writes).
- `tests/snax/snax-csr/`: four parts, one per CSR instruction path (see its
  README); returns its error count.
- Results in Claude's sandbox: `snax-csr` prints four lines of `0 errors`,
  exits 0, 108 stub accesses; the 17 plain ELFs (9-core build) exit 0 on
  `snitch`; `simple` and `printf_simple` exit 0 on `snax_alu`. Throwaway
  programs: a write to 976 stops with `Write to read-only CSR 976 (value:
  0x1)`, a read of 983 with `CSR 983 is not held by this block`.
  `snax-alu` runs to the end with no CSR warning: `Accelerator Cycles: 0`,
  `Number of errors: 100`, exit code 100 (nothing computes the output).
- On the author's side: P5's checks pass (`snax-csr` four lines of `0
  errors`, 108 stub accesses, the 17 plain ELFs on `snitch`).

### SG1 step 7: snax-alu on the stub

- 2026-10-13. `snax-alu` runs to the end with no CSR warning:
  `Accelerator Done!`, `Accelerator Cycles: 0`, `Number of errors: 100`,
  exit code 100. Nothing computes `local_o`, so all 100 outputs differ.
- The stub sees 22 accesses (`--trace=snax_acc0`), cycles from Claude's
  sandbox:

  | Cycle | CSR | Value | What |
  |---|---|---|---|
  | 8730 to 9237 | 960 to 964 | `0x10000000`, 0, 8, 25, 32 | reader 0: base `local_a`, spatial stride 8 B, 25 steps of 32 B |
  | 9459 to 9573 | 965 to 969 | `0x10000320`, ... | reader 1: base `local_b` (+800 B) |
  | 9693 to 9697 | 970 to 974 | `0x10000640`, ... | writer 0: base `local_o` |
  | 9815, 9914 | 978, 979 | 0, 25 | ALU mode, length |
  | 9919 | 975 | 1 | streamer start |
  | 10034 | 980 | 1 | ALU start |
  | 10040, 10046 | 981, 976 | 0 | ALU busy, streamer busy |
  | 21814 | 982 | 0 | ALU counter, after the check loop and `printf` |

- For SG3 and SG4: the streamer is started before the ALU, and each start
  is a write of 1 to the last read-write CSR of its block, the write that
  raises `valid` in `ReqRspManager.scala` and waits for `ready`. Each
  streamer runs 25 steps of 4 lanes of 64 bit.
- The ELF holds 19 SNAX CSR writes (17 `csrw`, 2 `csrwi`), one per write
  that runs; step 4's count of 18 `csrw` was one too many.

### SG1 step 8: SG1 closed

- 2026-10-13. All steps done; acceptance met: `snax-csr` reads back every
  written value, `snax-alu` runs to the end on the stub, the 17 plain tests
  still pass on `snitch`.
- Settled (the list is in `docs/plans/SG1.md` under "Decided"): the
  `snax_alu` target by hand, the CSR port at 4 * CSR, accelerators per core
  through `snax_acc`, the stub's rules. In snax-forge: D119 (M16's order)
  and D120 (the CSR path).
- Upstream files changed in SG1: the Snitch core (`class.hpp`,
  `snitch.cpp`, `snitch_core.py`), the cluster (`snitch_cluster.py`) and
  the `Makefile`; rows in `UPSTREAM.md`.
- Next: a housekeeping pass on this branch, then SG2 (the DMA), from the
  list under "SG2 starts from" in `docs/plans/SG1.md`.

### SG2 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG2.md` written: the iDMA model is adapted to
  snax_cluster's iDMA RTL, checked with a timing program on both sides. The
  housekeeping pass over SG1's code moves to after SG5.
- Read from source, not run (snax_cluster `b2672f8`, the iDMA fork's
  `master` at `e859ffc`, upstream v0.6.5; the fork is taken at
  `rev: master` with no lock file, so the commit in the RTL build may
  differ). The backend `idma_backend_rw_axi` is generated at build time
  (`make idma-rtl-gen`); read here from the fork's templates through
  `util/gen_idma.py`. The values are in SG2.md under "The DMA path".
- RTL and GVSoC differ in: bursts in flight (3 per direction in the iDMA, 2
  at the testbench DRAM; 24 in GVSoC), the burst split (both sides in the
  RTL, the AXI side only in GVSoC), read data (one 64 B beat per cycle; the
  whole burst at once in GVSoC), the L1 write width (64 B; 4096 B), the end
  of a transfer (the last write response; the last L1 write), the request
  queue (3; 8) and the DRAM (no latency of its own behind cuts, 64 B per
  beat; 100 cycles and 4 B per cycle).
- `snax-alu` does not wait for its two copies: the DMA core starts them and
  goes to the barrier, which does not wait for the DMA. The compute core
  starts the streamers about 1000 cycles of CSR setup later. Matters for
  SG3 to SG5, not for the stub.
- The cluster's perf counters (`perf_cnt.h`, `snitch_cluster_peripheral`)
  count `DMA_BUSY` from the iDMA's `busy_o`, the signal `snrt_dma_wait_all`
  polls; DMA events do not depend on `hart_select`. The enable is a posted
  store, so the program reads it back before starting the DMA. In
  `idma_inst64_events.sv` the buffer lines overwrite `r_stall` and
  `w_stall`, and `buf_r_stall` / `buf_w_stall` are never set. GVSoC's
  cluster registers come from an identical `snitch_cluster_peripheral_reg.hjson`
  but hold the counters as plain registers: they read 0.

### SG2 step 2: P2, the timing program

- 2026-10-13. `tests/snax/dma-timing/`: one ELF for the RTL and for
  `snax_alu`, built like `snax-alu` against the runtime of `../snax_cluster`.
  Its README lists the cases and the fields. Source words come from a seeded
  `data.h` (8 KiB in `.data`, which `base.ld` puts in DRAM); the L1 buffer
  starts at `snrt_l1_next()` rounded to 64 B.
- Two details of the measured window, from the disassembly:
  `snrt_mcycle()` has a `"memory"` clobber, so case fields read through a
  pointer were reloaded from DRAM between the marks (105 cycles of `issue`
  for the idle case at first); they are now read into locals before the
  first mark. The enable read-back is used by an `mv`, since a load into
  `x0` would not stall the core. The window now holds only `csrr 0xbc2`, the
  `dmsrc`, `dmdst`, `dmcpyi` of each copy and the loop.
- Results on `snax_alu` today (Claude's sandbox: LLVM 21.1.6 and bender
  0.28.2 from their GitHub releases, Python 3.12 venv with the image's
  requirements): exit 0, no warning, 0 errors, every counter 0 (the cluster
  registers store them but nothing counts).

  | Case | issue | done |
  |---|---|---|
  | idle | 3 | 6 |
  | l2l1 1x64 | 16 | 119 |
  | l2l1 1x256 | 16 | 119 |
  | l2l1 1x800 | 16 | 121 |
  | l2l1 1x4096 | 16 | 915 |
  | l2l1 1x8192 | 16 | 1939 |
  | l2l1 2x800 | 25 | 222 |
  | l2l1 4x800 | 43 | 622 |
  | l1l2 1x800 | 16 | 21 |

- Read against the model as it is: a copy issues in 16 cycles and each
  further copy adds 9; up to 800 B the 100-cycle DRAM latency dominates;
  from 4 KiB to 8 KiB `done` grows by 1024 cycles, 4 B per cycle, the DRAM's
  `width_log2=2` (why one 4 KiB copy takes 915 and not about 1140 is not
  read yet); each extra 800 B copy adds about 200 cycles for the same
  reason; L1 to L2 ignores the DRAM latency, as `idma_be_axi.cpp` does for
  writes.

### SG2 step 3: the RTL run

- 2026-10-13. Author's run of P2's ELF on snax_cluster's RTL built from
  `snax_alu_cluster_old.hjson` at `b2672f8`. Bender took the iDMA fork at
  `e859ffc`, the commit read in step 1. `Number of errors: 0`.

  | Case | issue | done | busy | r | w | ar_stall | w_stall | r_stall |
  |---|---|---|---|---|---|---|---|---|
  | idle | 6 | 12 | 0 | 0 | 0 | 0 | 67 | 0 |
  | l2l1 1x64 | 18 | 34 | 14 | 1 | 1 | 0 | 88 | 0 |
  | l2l1 1x256 | 18 | 39 | 17 | 4 | 4 | 0 | 90 | 0 |
  | l2l1 1x800 | 18 | 44 | 26 | 13 | 13 | 0 | 86 | 0 |
  | l2l1 1x4096 | 18 | 99 | 77 | 64 | 64 | 0 | 90 | 0 |
  | l2l1 1x8192 | 18 | 159 | 141 | 128 | 128 | 0 | 86 | 0 |
  | l2l1 2x800 | 28 | 59 | 39 | 26 | 26 | 0 | 88 | 0 |
  | l2l1 4x800 | 48 | 84 | 65 | 52 | 52 | 0 | 87 | 0 |
  | l1l2 1x800 | 18 | 39 | 20 | 13 | 13 | 0 | 81 | 0 |

- `dma_trace_00001_00000.log` (the iDMA's own trace, hart 1) is kept by
  the author; 814 lines, one per cycle with backend activity.

### SG2 step 4: what the RTL does

- 2026-10-13. Read from step 3's numbers and trace. The trace's busy
  windows equal the `busy` counter in every case (two runs per case).
  In the trace, `bus.axi_rsp_valid` is a read beat and `bus.axi_req_valid`
  a write beat.
- Per copy, counting from the cycle the backend takes it: the read request
  in cycle 1; the first read beat `L_rd` cycles later (11 from DRAM, 5 from
  L1); then one read beat per cycle, with no gap between bursts or between
  back-to-back copies; each write beat one cycle after its read beat; busy
  drops after the last write beat; the write response (`rsp_valid`) comes 5
  cycles later for an L1 write and 11 for a DRAM write. So
  `busy = L_rd + N_beats + 2`, with `N_beats` the 64 B beats the copy
  touches (800 B is 13, also at +800); exact for all eight copy cases.
- 8 KiB: both 4 KiB bursts are requested at the start and the beats run on
  through the page boundary, so the burst split costs nothing. 4x800: the
  backend takes a copy every 10 cycles, the issue cost per copy, and the
  beats stay continuous.
- `snrt_dma_wait_all` polls `busy_o`, which drops before the write
  response: software never waits for it.
- `ar_stall` and `r_stall` are 0 in every case: the testbench's 2-read
  limit and the 3-beat buffer never bite here. `w_stall` counts cycles in
  which the memory side is ready, whether a copy runs or not (67 when
  idle); it says nothing about a copy.
- Outside the engine, `done - busy` is 18 to 22 cycles: issue and the
  poll. One copy issues in 18 cycles, each further copy adds 10 (GVSoC
  today: 16 and 9). The idle case (6 and 12, GVSoC 3 and 6) is the cost of
  `mcycle` and `dmstati` in the core, an SG5 matter.
- Against GVSoC today (step 2): the DRAM is 100 cycles away there against
  about 11 for a first beat, and 4 B per cycle against 64; GVSoC moves L1
  to L2 without the DRAM latency. These set P4's values; P5 keeps only what
  P4's run leaves.

### SG2 step 5: P3, the perf counters

- 2026-10-13. GVSoC's cluster registers count four events of
  `snitch_cluster_peripheral.sv`: `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and
  `DMA_BUSY`. Accesses to the perf range (0x000 to 0x17F) are handled before
  the generated regmap: enable, hart select and a 48-bit value per counter,
  8 bytes apart, any access inside one register. A counter counts the event
  of its lowest enable bit, as the RTL's if-else chain does; the other
  events count nothing. `CYCLE` and `DMA_BUSY` are brought up to date from
  timestamps before any change and any read, with no per-cycle event. The
  RTL's one-cycle register on the events is not modelled; it changes a
  count only when an event crosses the moment a counter starts or stops.
- The iDMA frontend drives three wires: `busy`, from the transfer IDs as
  `dmstat 2` returns them, and `r_beats` / `w_beats`, the 64 B beats of
  each copy when it is queued (`beat_size`, a `SnitchDma` property). A beat
  never straddles a 4 KiB page, so the sum per copy equals the RTL's sum
  per burst. Unbound wires are not driven, so other users of `SnitchDma`
  (magia) are unchanged. `SnitchCluster` binds them, except with Spatz,
  whose cluster registers are another model.
- Results in Claude's sandbox: `dma-timing` on `snax_alu` exits 0 with 0
  errors; `issue` and `done` as in step 2; `r` and `w` equal the RTL's
  beats in every case; `busy` is the model's engine time today (103, 103,
  106, 900, 1924, 206, 606 and 6 for the copy cases, RTL 14 to 141).
  `snax-csr` gives four lines of `0 errors`; `snax-alu` still ends with
  `Accelerator Cycles: 0` and 100 errors. The 17 plain tests (9-core
  build) exit 0 on `snitch`; `perf_cnt` now prints `End: 1531 cycles`
  (0 before) and still 0 for its DMA byte counters, which count
  `DMA_AR_BW` and `DMA_AW_BW`.

### SG2 step 6: P4, the parameters

- 2026-10-13. `snax_alu.py` sets what step 4 measured, through two new
  arch values: `ClusterArch(dma=...)` replaces `SnitchCluster`'s `SnitchDma`
  defaults (`tcdm_width` 64, `transfer_queue_size` 3, `burst_queue_size` 3,
  for the RTL's 512-bit beat, `dma_req_fifo_depth` and
  `dma_axi_req_fifo_depth`), and `Soc`'s `hbm_latency` (default 100) is 6.
  The DRAM memory is 64 B per cycle (`width_log2=6`). Targets that set
  neither keep today's values.
- The 6 is only the DRAM's share of a read's latency: 11 cycles to a first
  beat from DRAM against 5 from L1. The 5 common to both are the wide
  crossbar's cuts and the AXI-to-memory conversion, which belong to the DMA
  model (P5). The cores' fetches and loads from DRAM take the same chip
  mapping, so they now see 6 cycles there too; their RTL latency is not
  measured (SG5).
- Results in Claude's sandbox: `dma-timing` exits 0 with 0 errors and no
  warning; `r` and `w` as in step 5.

  | Case | busy | RTL | done | RTL |
  |---|---|---|---|---|
  | idle | 0 | 0 | 6 | 12 |
  | l2l1 1x64 | 9 | 14 | 25 | 34 |
  | l2l1 1x256 | 12 | 17 | 27 | 39 |
  | l2l1 1x800 | 21 | 26 | 37 | 44 |
  | l2l1 1x4096 | 72 | 77 | 87 | 99 |
  | l2l1 1x8192 | 136 | 141 | 151 | 159 |
  | l2l1 2x800 | 34 | 39 | 50 | 59 |
  | l2l1 4x800 | 60 | 65 | 76 | 84 |
  | l1l2 1x800 | 15 | 20 | 31 | 39 |

- `busy` is 5 under the RTL in every copy case: GVSoC now gives
  `busy = (L_rd - 5) + N_beats + 2`, so the beat rate, the page crossing,
  the back-to-back copies and the 2 fixed cycles already match; only the
  common read path is missing. `done - busy` is 15 to 16 here against 18
  to 22 on the RTL: issue and polling in the core, as the idle case (SG5).
- `snax-csr` gives four lines of `0 errors`; `snax-alu` is unchanged; the
  17 plain tests (9-core build) exit 0 on `snitch`, `perf_cnt` printing
  what it did after P3.

### SG2 step 7: P5, the DMA's read path

- 2026-10-13. The 5 cycles a DMA read waits on the RTL before its first
  beat, from L1 and DRAM alike (the wide crossbar's cuts and the
  AXI-to-memory conversion), are a `SnitchDma` argument, `read_latency`,
  set to 5 by `snax_alu.py`; DRAM reads add `hbm_latency` (6) on top, 11 in
  all. Default 0, and the backends read it only when present, so the other
  users of `pulp/idma/` (`reg_dma`, `cheshire_dma`, `pulp_open_dma`, magia's
  `SnitchDma`) are unchanged.
- AXI reads (`idma_be_axi.cpp`): added to each burst's latency. Bursts are
  sent ahead (3 in flight), so back-to-back bursts overlap it, as on the
  RTL. L1 reads (`idma_be_tcdm.cpp`): this side keeps one line request open,
  so a per-line latency would be paid on every line; it is paid only when a
  line does not follow the previous one on the next cycle, once per read
  stream.
- Results in Claude's sandbox: `dma-timing` exits 0 with 0 errors and no
  warning; `busy` equals the RTL in all eight copy cases.

  | Case | busy | RTL | done | RTL |
  |---|---|---|---|---|
  | idle | 0 | 0 | 6 | 12 |
  | l2l1 1x64 | 14 | 14 | 29 | 34 |
  | l2l1 1x256 | 17 | 17 | 33 | 39 |
  | l2l1 1x800 | 26 | 26 | 41 | 44 |
  | l2l1 1x4096 | 77 | 77 | 93 | 99 |
  | l2l1 1x8192 | 141 | 141 | 157 | 159 |
  | l2l1 2x800 | 39 | 39 | 54 | 59 |
  | l2l1 4x800 | 65 | 65 | 80 | 84 |
  | l1l2 1x800 | 20 | 20 | 35 | 39 |

- The rest of `done` is issue and polling in the core: 15 to 16 cycles
  here, 18 to 22 on the RTL, a gap of 2 to 6 per case; the idle case (6
  against 12) shows the same core cost. SG5's.
- `snax-csr` gives four lines of `0 errors`; `snax-alu` is unchanged; the
  17 plain tests (9-core build) exit 0 on `snitch`, `dma_simple` and
  `perf_cnt` printing what they did after P4.

### SG2 step 8: SG2 closed

- 2026-10-13. All steps done; acceptance met: `dma-timing` runs on the RTL
  and on `snax_alu`, its cycles per case are logged on both sides (steps 3
  and 7) and the gap is explained: the DMA's engine time equals the RTL in
  all eight copy cases, and `done` is 2 to 6 cycles under it, the core's
  issue and polling (SG5).
- Settled (the list is in `docs/plans/SG2.md` under "Decided"): GVSoC's
  iDMA model kept and fitted by measurement; the read latency split into
  the DRAM's 6 cycles (`hbm_latency`) and the DMA's 5 (`read_latency`); the
  target's DMA values through `ClusterArch(dma=...)`; the cluster's perf
  counters for `CYCLE`, `DMA_BUSY`, `DMA_R_DONE`, `DMA_W_DONE`. In
  snax-forge: D121.
- Upstream files changed in SG2: the iDMA frontend and backends
  (`pulp/pulp/idma/fe/idma_fe_xdma.*`, `be/idma_be_axi.*`,
  `be/idma_be_tcdm.*`), `pulp/pulp/idma/snitch_dma.py`, the cluster
  registers (`cluster_registers.cpp`, `.py`), `snitch_cluster.py` and the
  chip's `snitch.py`; rows in `UPSTREAM.md`.
- Next: SG3, the streamer, planned in its own round from the list under
  "SG3 starts from" in `docs/plans/SG2.md`.

### SG3 step 1: P1, the plan

- 2026-10-13. `docs/plans/SG3.md` written: a streamer model with the
  hjson's parameter names, a crossbar that arbitrates the 12 SNAX ports per
  bank as the plain interconnect does, a test datapath in the ALU's place,
  and a reader-only timing program run on both sides.
- Read from source, not run (snax_cluster `b2672f8`, common_cells
  `v1.40.0`; the values are in SG3.md under "The streamer on the RTL" and
  "The path around it"):
  - The streamer's CSRs are 5 per mover (pointer low and high, spatial
    stride, temporal bound, temporal stride), the start CSR, then `busy`
    and the counter: 960 to 977. The ALU's are 978 to 982, reached through
    a combinational mux that subtracts 18.
  - The start write waits only while the streamer is busy; the core feels
    it only when the 2-deep offload cut is full or a later CSR read queues
    behind it. `snax-alu` starts an idle streamer.
  - A reader is done at its last grant, with data still buffered, so a
    reader-only run ends without the ALU when each lane reads at most
    `fifo_depth` (8) beats and the writer's bound is 0.
  - The plain interconnect is one `rr_arb_tree` per bank (`FairArb`,
    `LockIn`, no priority), not the sparse interconnect's arbiter that
    SNAX-MODEL copied (D31 in snax-forge). Read data comes one cycle after
    the grant.
  - On the RTL `csrrw` only writes and `csrrs` / `csrrc` only read; D120
    reads before a write when `rd` is not `x0`. `snax-alu` does not hit
    this; noted for SG5.
- GVSoC today: `L1_interleaver` does not arbitrate; a second access to a
  bank in a cycle gets one cycle of latency from the bank's cyclestamp, in
  call order. A sync `Router` with bandwidth 0 adds no latency, so a CSR
  access through it passes in its cycle (checked by run in P2).
- `snax-alu`'s buffers start at banks 0 (A), 4 (B) and 8 (O); the writer
  can meet a reader in the same banks when the readers run two beats ahead.
  Not run yet; `snax-stream` shows it in P5.

### SG3 step 2: P2, the CSR router

- 2026-10-14. `snax/snax_alu_acc.py`: `SnaxAluAcc`, the compute core's
  accelerator as `snax_acc_wrapper.sv.tpl` builds it. A GVSoC `Router`
  (synchronous, no bandwidth, no latency) splits the core's CSR accesses as
  `snax_csr_mux_demux.sv` does: 960 to 977 to `streamer`, 978 up to the last
  SNAX CSR (0x5FF) to `alu`, each mapping removing its base. Both are
  `SnaxCsrStub`s for now. The CSR lists moved there from `snax_alu.py`,
  which now sets `snax_acc={0: SnaxAluAcc}`.
- `SnaxCsrStub` takes `csr_base` (default 0): the CSR is `csr_base +
  offset / 4`, so a stub behind the router keeps the absolute CSR numbers
  in its checks and trace. Bound directly, it behaves as before.
- No upstream file changed.
- Trace to a file: `--trace=snax_acc0:<file>`. On stdout a `printf` of the
  program can land inside a trace line, which hid one of `snax-csr`'s 108
  accesses from a `grep`.
- Results in Claude's sandbox, on main before P2 and with P2: `snax-csr`
  four lines of `0 errors`, exit 0, 108 accesses (91 streamer, 17 ALU);
  `snax-alu` `Accelerator Cycles: 0`, `Number of errors: 100`, exit code
  100, 22 accesses (17 streamer, 5 ALU). Every access has the same cycle,
  CSR and value with and without P2: the router adds no cycle. Throwaway
  programs: a read of 983 stops with `CSR 983 is not held by this block`
  from `alu`, a write to 976 with `Write to read-only CSR 976` from
  `streamer`.
- The cycles of SG1 step 7 moved with SG2's DRAM latency (the core fetches
  from DRAM): `snax-alu` now writes 960 at cycle 2508, starts the streamer
  (975) at 2616 and the ALU (980) at 2630, reads 981 at 2636 and 976 at
  2642, and reads 982 at 4696, after the check loop and `printf`.
