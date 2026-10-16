# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what was learned. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the programs and the RTL reference | `sw/README.md`, "Pin": the copy in `sw/` is at it, and the RTL runs in a checkout at it (CI1). From SG6 on `9fbf35d` (#657): `d7dd789` plus SG6's Zicsr fix in `snitch.sv` and `snax_intf_translator.sv`, the programs unchanged; SG0 used `8ebd422`, SG1 to SG4 `b2672f8`, SG5 `d7dd789` (`b2672f8` plus the DMA wait in `snax-alu.c`, SG5 P2) |
| common_cells, the TCDM arbiter (SG3) | `v1.40.0` (`1281545696eb3fcba50ec5b4275993476a3c710e`), in the RTL build's `Bender.lock` (SG3 step 4) |

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

### SG3 step 3: P3, the crossbar and the readers

- 2026-10-14. `snax/snax_tcdm_xbar.py` / `.cpp`: `SnaxTcdmXbar`, the SNAX
  ports into the TCDM banks as the plain interconnect arbitrates them: per
  bank `rr_arb_tree`'s tree (`sel = ~left | right & rr_q[level]`) and
  `FairArb` state (the next requester above `rr_q`, else the first at or
  below it). A request is held (`IO_REQ_PENDING`) until the crossbar's event
  of that cycle, queued by the first request; the winner's bank access
  happens then, `grant()` in that cycle, `resp()` one cycle later plus the
  bank's latency. A loser gets nothing and its master sends it again the
  next cycle, as an RTL master keeps `valid` high. Built in
  `SnitchClusterTcdm` when an accelerator has TCDM ports, its outputs on the
  same bank memories the cores use; inputs numbered in core order, as
  snax_cluster packs `snax_tcdm_req_i`.
- `snax/snax_streamer.py` / `.cpp`: `SnaxStreamer`, configured from the
  hjson's streamer template (`STREAMER_TEMPLATE` in `snax_alu_acc.py`,
  `snax_alu_streamer_template` with its keys); other keys are refused by
  name. CSRs, start, busy, counter, AGU and readers as SG3.md reads the RTL.
  One event per cycle while busy sends the requests, then a commit event
  (delay 0, after the crossbar's) pops the granted addresses and lets the
  AGUs push. Busy and the counter are computed from the start cycle and the
  end cycle when read. A streamer with no credit and no room sleeps. Not
  yet: writers (a writer that would start is refused with a warning), the
  beats out (P5).
- `snax_alu_acc.py`: `csr_mux`, `streamer`, `alu_regs`; the ALU's first CSR
  computed from the template (978); `SnaxAluAcc.nb_tcdm_ports` (12) and
  `o_TCDM()` for the cluster.
- `snax-csr` leaves out the start CSR 975 (its pattern has bit 0 set and
  would start the streamer): 103 accesses, 63 reads and 40 writes. The
  ALU's start CSR 980 stays until SG4.
- `tests/snax/stream-timing/`: one ELF per case (`CASE_<name>`), since the
  reader queues keep their beats and credit after a run with no ALU, on the
  RTL too. Results in Claude's sandbox; s is the start write's cycle:

  | Case | s | Last grant | Busy up to | Counter |
  |---|---|---|---|---|
  | `zero_bound` | 4707 | none | s + 1 | 0 |
  | `a_alone` | 4707 | 4716 | 4717 | 9 |
  | `ab_other_banks` | 4711 | 4720 | 4721 | 9 |
  | `ab_same_banks` | 4711 | 4721 | 4722 | 10 |
  | `a_stride0` | 4707 | 4719 | 4720 | 12 |

  All five as predicted from source in step 1. The first grant is at
  s + 2. `ab_same_banks`: in s + 2 A wins banks 0 to 3 (`grant in_0`,
  `held: in_4`, ...), then B runs one cycle behind with no further conflict.
  `a_stride0`: bank 0 grants in_0, in_1, in_2, in_3 in turn and the lanes
  stay one cycle apart. The printed `polls` (0, 0, 3, 4, 1) and `mcycle`
  spans (15, 15, 24, 27, 18) are the core's timing: in `a_alone` the first
  busy read comes 11 cycles after the start write and already reads 0.
- The arbiter against the RTL, run, not read: common_cells v1.40.0's
  `rr_arb_tree` (`FairArb`, `LockIn`, `AxiVldRdy`, the grant always given)
  in Icarus Verilog 12 on 2000 cycles of random requests, against
  `tree_pick()` and `next_rr()` taken verbatim from `snax_tcdm_xbar.cpp`:
  the same winner in every cycle at 12, 15 and 4 inputs, and the RTL's 15
  inputs with 3 idle give the model's 12-input winners.
- Throwaway program: a second start write while the streamer is busy stops
  with `Start (CSR 975) while the streamer is busy`.
- `snax-alu` now stops at its start write (cycle 2616) with `Writer at CSR
  970 started: writers are not modelled yet (SG3 P5)`; it runs again in P5.
- Results in Claude's sandbox: `snax-csr` four lines of `0 errors`, 103
  accesses (86 streamer, 17 `alu_regs`); `dma-timing` exits 0 with every
  field as in SG2 step 7; the 17 plain tests (9-core build) exit 0 on
  `snitch`, which builds no crossbar, `perf_cnt` printing `End: 1531
  cycles`.
- For step 4 (author's run on the RTL): the five ELFs of
  `tests/snax/stream-timing/build/`, the printed lines, and the
  common_cells version in snax_cluster's `Bender.lock`.

### SG3 step 4: the RTL run

- 2026-10-14. Author's run of P3's five `stream-timing` ELFs on
  snax_cluster's RTL (Verilator) built from `snax_alu_cluster_old.hjson` at
  `b2672f8`:

  ```
  stream-timing zero_bound: counter 0, polls 0, mcycle 13
  stream-timing a_alone: counter 9, polls 3, mcycle 25
  stream-timing ab_other_banks: counter 9, polls 3, mcycle 19
  stream-timing ab_same_banks: counter 10, polls 3, mcycle 19
  stream-timing a_stride0: counter 12, polls 3, mcycle 25
  ```

- `Bender.lock`: common_cells 1.40.0 at `1281545`, the commit read in step
  1 and simulated against the model's arbiter in step 3.

### SG3 step 5: the counter on both sides

- 2026-10-14. The streamer's counter is equal on the RTL and on SNAX-GVSoC
  in all five cases:

  | Case | RTL | SNAX-GVSoC |
  |---|---|---|
  | `zero_bound` | 0 | 0 |
  | `a_alone` | 9 | 9 |
  | `ab_other_banks` | 9 | 9 |
  | `ab_same_banks` | 10 | 10 |
  | `a_stride0` | 12 | 12 |

  So the start (first request at s + 2), the AGU's pace, the end rule
  (counter g - s) and the round-robin order per bank match the RTL.
- `polls` and `mcycle` are the core's: the RTL polls 3 times in every
  running case, SNAX-GVSoC 0 to 4 (its first busy read comes 11 cycles after
  the start write in `a_alone`); the RTL's `mcycle` span does not follow the
  counter (`a_alone` 25, `ab_same_banks` 19), so the core's fetch timing
  differs per ELF. SG5's, with SG2's issue and polling gaps.

### SG3 step 6: P4 skipped

- 2026-10-14. Step 5 left no gap in the streamer's counter.

### SG3 step 7: P5, writers, beats and the test datapath

- 2026-10-14. `SnaxStreamer` gains the writers and the beat ports
  `reader_<i>` and `writer_<j>` (`num_channel` x 8 B, lane 0 first; size 0
  is a probe, `DENIED` means not this cycle). Rules from the RTL: read data
  enters its lane's queue one cycle after the grant and can leave the cycle
  after; a beat leaves when every lane holds data, `repeat` times with
  temporal stride 0; a pop returns credit in that cycle; a beat given to a
  writer is taken when no lane's queue is full and can be written the next
  cycle; a writer channel requests with an address and its lane's data, with
  no credit, and is done at its last grant. A streamer that can do nothing
  sleeps until a beat moves.
- `snax/snax_test_datapath.py` / `.cpp`: `SnaxTestDatapath` in the ALU's
  place (`test_datapath`), not the ALU. The ALU's 5 CSRs: mode (bit 0 copies
  B instead of A, bits 7:4 are k - 1), length, start; busy (start + 1 to the
  last firing), counter (those cycles). A firing takes one beat from each
  reader and gives the chosen one to the writer, all or nothing (probes
  first). Its event runs before the streamer's step in a cycle, so a pop
  returns credit in time for that cycle's requests; at its first cycle the
  order may be the other way round, which delays a request by one cycle at
  most. `snax_csr_stub` is no longer used by the target and stays as a
  placeholder for blocks not modelled yet.
- Folded in from the profiling review (open items 59 and 61 of the plan
  for P6, and the `resp` and queue events): the crossbar names its inputs
  by owner (`snax_acc0.streamer.reader0.lane2`), from the accelerator's
  `tcdm_port_names` through the cluster, and traces each response (`Resp`)
  at trace level; the streamer traces each lane queue's count (`Queue`) at
  trace level, at the cycle a word enters or leaves; per mover it classes
  every cycle of a run as SNAX-MODEL did (`busy` > `stall_xbar` >
  `stall_fifo` > `idle`, cycles slept through keep the class they had) and
  writes the classes and each lane queue's highest count in the run's last
  busy cycle. The classes add up to e - s in every run checked.
- `tests/snax/snax-stream/`: `snax-alu`'s three streamers through its
  library; the datapath copies A at k = 1, then B at k = 3; each run checks
  O and prints the streamer's and the datapath's counters.
- `snax-csr` leaves out the ALU's start CSR 980 as well: 98 accesses, 60
  reads and 38 writes.
- Results in Claude's sandbox:
  - `snax-stream`: `copy A, k=1: errors 0, streamer counter 42, datapath
    counter 25` and `copy B, k=3: errors 0, streamer counter 79, datapath
    counter 73`; exit 0. In the first run the datapath starts 14 cycles
    after the streamer, the readers wait 5 cycles for credit before it,
    and the writer loses a bank to a reader twice (`stall_xbar 2`): the
    writer meets the readers in the same banks, as step 1 expected.
  - `snax-alu` runs to the end: `Accelerator Done!`, `Accelerator Cycles:
    25`, `Number of errors: 97`, exit code 97. The datapath copies A where
    the ALU adds; the 3 outputs that match are the elements where B is 0.
  - `stream-timing`: the same five counters (0, 9, 9, 10, 12);
    `snax-csr` four lines of `0 errors`; `dma-timing` as in SG2 step 7; the
    17 plain tests (9-core build) exit 0 on `snitch`.

### SG3 step 8: SG3 closed

- 2026-10-14. All steps done, P4 skipped; acceptance met: standalone tests
  of `snax-alu`'s three streamers (`stream-timing` with its readers on both
  sides, `snax-stream` with all three on SNAX-GVSoC), and per-bank
  arbitration of a streamer port in the crossbar's trace (`ab_same_banks`,
  `a_stride0`).
- Settled (the list is in `docs/plans/SG3.md` under "Decided"): the
  crossbar copies the plain interconnect's `rr_arb_tree` and carries only
  the SNAX ports; one streamer component from the hjson's template; the
  beats by request with a probe; a test datapath in the ALU's place until
  SG4. In snax-forge: D122, and open items 57, 58, 60 and 62 from SG3's
  profiling review and reading (59 and 61 were done in P5).
- Upstream files changed in SG3: `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py`
  (P3, P5); rows in `UPSTREAM.md`. New in `snax/`: `snax_alu_acc`,
  `snax_streamer`, `snax_tcdm_xbar`, `snax_test_datapath`.
- Next: SG4, the ALU, planned in its own round from the list under "SG4
  starts from" in `docs/plans/SG3.md`.

### SG4 step 1: P1, the plan

- 2026-10-14. `docs/plans/SG4.md` written: an ALU model after
  `snax_alu_shell_wrapper.sv` in the test datapath's place, `snax-stream` on
  the ALU's modes, a timing program `alu-timing` run on both sides, and the
  core's warnings on the two CSR forms where SNAX-GVSoC and the RTL differ.
- Read from source, not run (snax_cluster `b2672f8`; the values are in
  SG4.md under "The ALU on the RTL"):
  - The ALU's CSRs are 978 to 982: mode, length and start in the
    ReqRspManager, busy and the counter from `snax_alu_csr.sv`. Its `ready`
    is tied to 1, so a start is never held, not even while busy.
  - A start latches mode and length at the end of its cycle but does not
    reset `len_counter`: a start while busy keeps the firings done, the end
    wins over a start in the same cycle, and length 0 never ends.
  - The counter is 1 at s + 1 and stops counting once `len_counter` reaches
    `length - 1`, so it ends at f - s + 1 with f the second-to-last firing.
    The test datapath's f_last - s gives the same 25 for back-to-back
    firings, and differs when the last firing is late (1 with length 1 on
    the RTL).
  - The PE is combinational: a firing needs busy, both readers' beats and
    the writer's `ready` in one cycle. The writer's `ready` is all lane
    queues not full (`pipe = false`), the rule SG3 modelled, now read in
    `Writer.scala`.
- `alu-timing` compares, per case, the counter that does not depend on the
  gap between the two start writes, since that gap is the core's timing.

### SG4 step 2: P2, the ALU

- 2026-10-14. `snax/snax_alu_shell.py` / `.cpp`: `SnaxAluShell`, the ALU after
  `snax_alu_shell_wrapper.sv` (`num_pe` 4, `data_width` 64), as `alu` in
  `SnaxAluAcc` on the same CSRs (978 to 982) and beat ports as the test
  datapath, which is removed. Rules as SG4.md reads the RTL: a start is
  recorded when written and applied at the first event or access in a later
  cycle, so a firing in its cycle still uses the old mode and length; busy
  and the counter come from s, F (the firing that brings `len_counter` to
  `length - 1`) and E (the last firing). How it waits (`try_fire`) and what
  it computes (`compute`) are one method each.
- GVSoC runs with `werror`: `force_warning` stops the run. The warning on a
  start that cannot end (length 0, or firings kept past `length - 1`) uses
  `force_warning_no_error`, since the RTL just stays busy; P3's CSR-form
  warnings need the same.
- `tests/snax/snax-stream/`: one run per mode (add, sub, mul, xor), 25
  beats in `snax-alu`'s layout, 64-bit data from a fixed generator, O checked
  against the core's own result; runs on the RTL too. Dropped: the runs
  "copy A, k=1" and "copy B, k=3", since the test datapath and its mode bits
  are gone; the back-pressure k = 3 gave comes back in P4
  (`out_same_banks`). clang inlines the 64-bit multiply (no `__muldi3`).
- Claude's sandbox now builds with LLVM 21.1.6 from LLVM's release and bender
  0.28.2 from its release (the conda channels are not reachable from it).
  On main this setup gives SG3's numbers (`snax-alu` 25 / 97 errors,
  `snax-stream` 42 / 25 and 79 / 73) and `stream-timing`'s polls and
  `mcycle` spans of SG3 step 3, but `dma-timing`'s `done` 1 to 3 cycles under
  SG2 step 7 (`busy` equal): the ELF, not P2, since main gives the same.
- Results in Claude's sandbox:
  - `snax-alu`: `Accelerator Done!`, `Accelerator Cycles: 25`, `Number of
    errors: 0`, exit 0. The streamer starts at 2625, the ALU at 2630, the
    ALU fires in every cycle from 2631 to 2655 (`busy 25, stall_out 0,
    stall_in 0`), and the streamer is done at 2657 (counter 31).
  - `snax-stream`: `errors 0, streamer counter 31, alu counter 25` in all
    four modes, exit 0; the two start writes are 5 cycles apart in each run.
  - A throwaway program (not kept): length 1 with the streamer started 288
    cycles after the ALU gives counter 1; a start (add, 100) then a start
    (sub, 25) before any firing gives O = A - B with 0 errors; a start with
    length 0 warns, busy reads 1 and the program ends with exit 0.
  - `stream-timing`: counters 0, 9, 9, 10, 12; `snax-csr`: four lines of `0
    errors`; `dma-timing`: exit 0, `busy` as in SG2 step 7. The 17 plain tests
    were not run: the `snitch` target builds no SNAX component, and P2
    changes no upstream file.

### SG4 step 3: P3, the CSR-form warnings

- 2026-10-14. The Snitch core warns once per run, without stopping it
  (`force_warning_no_error`), on the two forms where SNAX-GVSoC follows
  Zicsr (D120) and the RTL does not: in `SnaxCsr::handle()` on `csrrw` /
  `csrrwi` with `rd` not `x0`, in `Iss::snax_csr_access()` on any write from
  `csrrs`, `csrrc`, `csrrsi` or `csrrci` (the callback sees no instruction,
  but a write there is always one of these). Two flags on `Iss`; rows in
  `UPSTREAM.md`.
- Read from source, not run (snax_cluster `b2672f8`): on the RTL,
  `csrrw rd, csr, rs1` with `rd` not `x0` writes the CSR with `rs1` and
  writes `rd` with the ALU's sum of `rs1` and the CSR number (`snitch.sv`
  leaves `write_rd` at 1 and `alu_op` at `Add`, operand B the CSR number);
  `csrrwi` the same with the immediate. The four set and clear forms are
  sent as reads only (`snax_intf_translator.sv`, `write_csr = 0`).
- Found in GVSoC's ISS (`core/models/cpu/iss/include/isa/priv.hpp`, shared
  by every core): `csrrc` with `rs1 = x0` and `csrrsi` / `csrrci` with 0 write
  back the value they read, where Zicsr writes nothing; `csrrs` checks
  `rs1`. On a read-only SNAX CSR that write is refused and stops the run.
  No SNAX program uses these forms (`csrr_ss` is `csrrs rd, csr, x0`).
  Warned about now; fixed right after the SG series, with the RTL's fix.
- `snax-csr`'s README still named the test datapath (missed in P2); fixed.
- Results in Claude's sandbox:
  - `snax-csr`: four lines of `0 errors`, exit 0, and the two warnings,
    both on CSR 960 (part 2's `csrrw` at cycle 5201, part 3's `csrrs` at
    7161); still 98 accesses, 60 reads and 38 writes.
  - `snax-alu`, `snax-stream`, `stream-timing`, `dma-timing`: output as after
    P2, no warning.
  - The 17 plain tests (9-core build) exit 0 on `snitch`, `printf_simple`
    printing `Hello, World!` 9 times; none warns.

### SG4 step 4: P4, the timing program

- 2026-10-14. `tests/snax/alu-timing/`: one ELF, five cases in sequence on
  `snax-alu`'s streamers and the ALU through its library; per case the
  errors, the streamer's counter (977), the ALU's (982) and the start gap
  (`mcycle` before `start_alu()` minus before `start_streamer()`). Each case
  has one counter that does not depend on the gap, the one to compare: 977
  for `alu_first` and `restart_idle`, 982 for `stream_first` and
  `out_one_bank`, both for `len1`.
- Changed from the plan: `out_same_banks` (O on A's banks lane by lane) gave
  no conflict, since the writer writes beat t one cycle after the ALU takes
  it, when reader A asks for beat t + 9, four banks on. O's four lanes on one
  bank (beats on consecutive banks) did not stall the ALU either: the lanes
  of consecutive beats write in parallel. `out_one_bank` puts every word of
  O on one bank (spatial stride 256 B, temporal 1024 B), so the writer gets
  one grant a cycle.
- `stream_first` uses `snax-alu`'s own layout, where the writer loses banks
  8 to 11 to reader B twice (crossbar trace, 8 lane conflicts); its 8-deep
  queue absorbs them, so the ALU does not stall.
- Results in Claude's sandbox, exit 0, `errors 0` in every case:

  | Case | 977 | 982 | Gap | ALU classes |
  |---|---|---|---|---|
  | `alu_first` | 29 | 34 | -16 | busy 25, stall_in 9 |
  | `stream_first` | 134 | 25 | 105 | busy 25 |
  | `out_one_bank` | 211 | 72 | 105 | busy 25, stall_out 50 |
  | `len1` | 5 | 1 | -7 | busy 1, stall_in 9 |
  | `restart_idle` | 29 | 34 | -7 | busy 25, stall_in 9 |

  - `alu_first`: the trace's start writes are 6 cycles apart (ALU at s_a,
    streamer at s_a + 6); the ALU's first firing is at s + 4, s the
    streamer's start, and its last at s + 28; the writer's last grant at
    s + 29 ends the streamer, counter 29.
  - `out_one_bank`: the ALU's last firing is 75 cycles after its start;
    the counter stops at the second-to-last, 72. The writer's queues reach
    7 to 8.
  - `restart_idle`: the second start (sub, 25) replaces the first (add, 100)
    before any firing; O = A - B.
- Not rerun: the other programs and the plain tests; P4 adds a program and
  changes nothing they use.

### SG4 step 5: the RTL run

- 2026-10-14. Author's run of P4's ELFs (`snax-alu`, `snax-stream`,
  `alu-timing`) on snax_cluster's RTL (Verilator) built from
  `snax_alu_cluster_old.hjson` at `b2672f8`:

  ```
  Accelerator Done!
  Accelerator Cycles: 25
  Number of errors: 0

  snax-stream add: errors 0, streamer counter 29, alu counter 25
  snax-stream sub: errors 0, streamer counter 29, alu counter 25
  snax-stream mul: errors 0, streamer counter 29, alu counter 25
  snax-stream xor: errors 0, streamer counter 29, alu counter 25

  alu-timing alu_first: errors 0, streamer counter 29, alu counter 32, start gap -5
  alu-timing stream_first: errors 0, streamer counter 132, alu counter 25, start gap 103
  alu-timing out_one_bank: errors 0, streamer counter 210, alu counter 72, start gap 104
  alu-timing len1: errors 0, streamer counter 5, alu counter 1, start gap -5
  alu-timing restart_idle: errors 0, streamer counter 29, alu counter 32, start gap -5
  ```

### SG4 step 6: the counters on both sides

- 2026-10-14. SNAX-GVSoC's values from Claude's sandbox (steps 2 and 4).
  Every counter that does not depend on the core's timing is equal:

  | Program, case | Counter | RTL | SNAX-GVSoC |
  |---|---|---|---|
  | `snax-alu` | 982 | 25 | 25 |
  | `snax-stream`, each mode | 982 | 25 | 25 |
  | `alu_first` | 977 | 29 | 29 |
  | `stream_first` | 982 | 25 | 25 |
  | `out_one_bank` | 982 | 72 | 72 |
  | `len1` | 982, 977 | 1, 5 | 1, 5 |
  | `restart_idle` | 977 | 29 | 29 |

  So the beat path (reader → ALU → writer), the writer's last grant, its
  `ready` rule and the back-pressure into the ALU, the counter's end rule
  and the re-latch on a second start match the RTL. The writer's timing and
  the beat handshake, open since SG3, are checked.
- The counters that depend on the gap between the two start writes differ
  by the core's timing: with the ALU first, 982 is the gap plus 28 (RTL 32,
  4 cycles; SNAX-GVSoC 34, 6 cycles); with the streamer first, 977 is the
  gap plus 26 (`snax-stream`: RTL 29, 3 cycles; SNAX-GVSoC 31, 5 cycles);
  after the 100-cycle wait, 132 against 134 and 210 against 211. SNAX-GVSoC's
  core puts about 2 more cycles between two library CSR calls. SG5's.
- The first-cycle ordering of SG3 step 7 is not visible: `stream_first`
  starts the ALU on full readers, and a refill request one cycle late is
  absorbed by the 8 beats buffered.

### SG4 step 7: P5 skipped

- 2026-10-14. Step 6 left no gap in the counters compared.

### SG4 step 8: SG4 closed

- 2026-10-14. All steps done, P5 skipped; acceptance met: `snax-alu` prints
  `Accelerator Cycles: 25` and `Number of errors: 0` on SNAX-GVSoC, as on
  the RTL, and every counter of `snax-stream` and `alu-timing` that does not
  depend on the core's timing equals the RTL.
- Settled (the list is in `docs/plans/SG4.md` under "Decided"): the ALU
  copies `snax_alu_csr.sv`, start while busy included; the test datapath is
  gone and `snax-stream` runs on both sides; timing by the same ELFs on both
  sides; the CSR-form warnings until SG6 fixes both sides. In snax-forge:
  D123 (the same ELF on both sides), D120 amended, open items 62 to 64, and
  SG6.
- Upstream files changed in SG4: `core/models/cpu/iss/src/snitch/snitch.cpp`
  and `include/cores/snitch/class.hpp` (P3); rows in `UPSTREAM.md`. New in
  `snax/`: `snax_alu_shell`; removed: `snax_test_datapath`. New test:
  `alu-timing`.
- Next: SG5, the baseline, planned in its own round from the list under
  "SG5 starts from" in `docs/plans/SG4.md`.

### SG5 step 1: P1, the plan

- 2026-10-14. `docs/plans/SG5.md` written: `snax-alu` at five sizes (4, 100,
  128, 1024, 4096) on both sides, per-phase cycles cut from each side's
  instruction trace of the same ELF, a three-tier error target fixed before
  the first comparison, and a regression (`make regress`) locking
  SNAX-GVSoC's numbers.
- Read from source, not run (snax_cluster `b2672f8`; details in SG5.md under
  "The app on the RTL"):
  - The runtime runs init on the CPU, a hardware barrier, `main`, a second
    hardware barrier and the exit (a reduction in DRAM, a global barrier,
    core 0's store to `tohost`). Hart 0 computes, hart 1 is the DMA core.
  - `snrt_cluster_hw_barrier()` is `csrr x0, 0x7C2` and waits for the cores
    only. `snax-alu.c`'s DMA core issues A and B and goes to the barrier
    without waiting, so the transfer runs while the compute core sets up
    and polls, and the readers do not wait for it.
  - From SG2's DMA times (estimate, not run): reader B asks for B before the
    DMA has written it once N is about 250 or more, so 1024 and 4096 would
    give errors on both sides that depend on each side's initial L1 and on
    core timing.
- Changed from the planning round: the app gets `snrt_dma_wait_all()` before
  its barrier, in snax_cluster itself (P2), so the copy here stays the app
  unchanged; D2 becomes the DMA wait and holds the transfer, with C1; the
  DMA core gets D3 (barrier) and D4 (the post-main barrier, which holds the
  compute core's C2 to C6, and the exit); C4 moves to tier 3, since the
  streamer ends 2 to 4 cycles after the ALU at any N; the fit of 4096 is
  checked from the runtime's L1 layout, not the linker map (L1 is allocated
  at run time from the TCDM start).
- BASE1 is out of SG5 (after the SG series); snax-forge's SG5 row updated.

### SG5 step 2: P2, the DMA wait

- 2026-10-14. snax_cluster `d7dd789` (#656) is `b2672f8` plus
  `snrt_dma_wait_all()` in `snax-alu.c`, after the DMA core's two starts and
  before its barrier; nothing else changed, so the RTL and SG2 to SG4's RTL
  results are those of `b2672f8`. The copy in `tests/snax/snax-alu/` is
  synced, its README names the new commit, the pin above and the clone
  command in `README.md` moved to it. The other programs' READMEs keep
  `b2672f8`, where their RTL runs were made.
- Author's run on the RTL: the same three lines as before the change.
- Results in Claude's sandbox (LLVM 21.1.6 from LLVM's release, the ELF
  built here), `snax-alu` at 100 before and after P2, with
  `--trace=pe0/insn` and `--trace=pe1/insn`:
  - Both print `Accelerator Done!`, `Accelerator Cycles: 25`, `Number of
    errors: 0` and exit 0.
  - After P2 the DMA core issues its second copy at 2497, polls `dmstati` 15
    times (2498 to 2526) and reaches the barrier at 2529. Both cores' barrier
    instructions are traced at 2529, against 2489 before: the compute core
    leaves the barrier 40 cycles later, once A and B are in L1.
  - The compute core's start writes move by 27 cycles, not 40 (975 at 2643
    against 2616, 980 at 2657 against 2630): its CSR setup is 13 cycles
    shorter after P2, probably because the DMA no longer shares the path to
    DRAM while the core fetches the setup code (not checked). ALU and
    streamer polls are unchanged (5 and 1).
  - The read of 982 moves from 4716 to 4736, but hart 0's last instruction is
    at 11264 in both runs. Left for the phase script (P3) to explain.
- Seen in the dump, for P3's markers: `dmstati` disassembles as `<unknown>`
  in `llvm-objdump` but as `dmstati` in GVSoC's trace; CSR 982 disassembles
  as `pmpaddr38` and the SNAX CSRs in GVSoC's trace as `snax_csr_<n>`, so
  markers match on the CSR number, not its name.
- Not rerun: the other programs and the plain tests; P2 changes no file they
  use.

### SG5 step 3: P3, the phase script

- 2026-10-14. `tests/snax/phases.py ELF --gvsoc WORKDIR | --rtl LOGDIR
  [--json OUT]` cuts a `snax-alu` run into the phases of SG5.md from both
  cores' instruction traces, with markers found in the ELF by symbol and
  instruction word: the barrier word in `main`, the CSR writes to 975 and
  980 and the read of 982 by CSR number, the three poll loops as a call (or
  `dmstati`) at P with a branch back at P + 4, `main`'s `ret`, and the
  store to `tohost` as an `auipc` and store pair. A missing marker is a
  named error (the ELF before P2 gives "poll loop of dmstati not found in
  main"). 9 unit tests in `tests/snax/test_phases.py`; the RTL lines in them
  follow `gen_trace.py`'s format, not a run, until step 5.
- On SNAX-GVSoC a trace file name is relative to the work directory:
  `--trace=pe0/insn:pe0.txt` writes `<work-dir>/pe0.txt`; a path with the
  work directory in it fails with "Unable to open file" (exit 134).
- Results in Claude's sandbox, `snax-alu` at 100:

  | Hart 0 | Start | Cycles | Insns | Polls |
  |---|---|---|---|---|
  | C0 boot | 1754 | 644 | 122 | |
  | C1 barrier | 2398 | 132 | 19 | |
  | C2a CSR setup | 2530 | 114 | 46 | |
  | C2b CSR setup | 2644 | 14 | 3 | |
  | C3 ALU poll | 2658 | 33 | 22 | 5 |
  | C4 streamer poll | 2691 | 6 | 4 | 1 |
  | C5 check loop | 2697 | 2040 | 1510 | |
  | C6 printf | 4737 | 6445 | 2846 | |
  | C7 exit | 11182 | 76 | 12 | |

  | Hart 1 | Start | Cycles | Insns | Polls |
  |---|---|---|---|---|
  | D0 boot | 1754 | 653 | 331 | |
  | D1 DMA issue | 2407 | 91 | 33 | |
  | D2 DMA wait | 2498 | 30 | 30 | 15 |
  | D3 barrier | 2528 | 2 | 2 | |
  | D4 post-main and exit | 2530 | 8728 | 30 | |

  Total 9504 cycles; up to the read of 982 (C0 to C5) 2983.
- C6 is the host's: each `printf` line ends in a syscall through `tohost`,
  and `_putchar` spins on `fromhost` until the host answers. Here the three
  spins (about 100 cycles each) end at 6009, 9006 and 11009, on a grid of
  about 1000 cycles. That is why the run ends at the same cycle before and
  after P2 (step 2). Tier 2's total therefore stops at the read of 982; C6,
  C7 and the full total move to tier 3 (SG5.md updated).
- C5 takes about 20 cycles per element: the core loads OUT from DRAM, two
  32-bit loads per 64-bit element. A tier-2 phase, on the core's path to
  DRAM.
- Not rerun: the other programs and the plain tests; P3 adds a script and
  changes no program.

### SG5 step 4: P4, the five sizes

- 2026-10-14. `make -C tests/snax/snax-alu DATA_LEN=N` writes
  `build/N/data.h` with `datagen.py` (NumPy seed 0, mode 0, N elements) and
  builds `build/N/snax-alu.elf`; without `DATA_LEN` the build is unchanged.
  At 100 the generated `data.h` and the ELF equal the default build byte for
  byte. The streamer's counter (977), which the app does not read, comes
  from its trace: `--trace=streamer:streamer.txt`, the line `Done: busy up
  to cycle ..., counter N`.
- Results in Claude's sandbox. Every size exits 0 with `Number of errors: 0`
  and `Accelerator Cycles:` N / 4; each run takes 1 to 2 s. Cycles per phase
  (polls in brackets):

  | Phase | 4 | 100 | 128 | 1024 | 4096 |
  |---|---|---|---|---|---|
  | C0 boot | 633 | 644 | 659 | 661 | 653 |
  | C1 barrier | 111 | 132 | 133 | 360 | 1148 |
  | C2a CSR setup | 114 | 114 | 114 | 115 | 115 |
  | C2b CSR setup | 14 | 14 | 14 | 14 | 14 |
  | C3 ALU poll | 9 (1) | 33 (5) | 39 (6) | 261 (43) | 1029 (171) |
  | C4 streamer poll | 6 (1) | 6 (1) | 6 (1) | 6 (1) | 6 (1) |
  | C5 check loop | 113 | 2040 | 2613 | 20533 | 81962 |
  | C6 printf | 5716 | 6445 | 6765 | 6696 | 6496 |
  | C7 exit | 77 | 76 | 74 | 73 | 73 |
  | D0 boot | 642 | 653 | 659 | 661 | 653 |
  | D1 DMA issue | 92 | 91 | 95 | 96 | 96 |
  | D2 DMA wait | 8 (4) | 30 (15) | 36 (18) | 262 (131) | 1050 (525) |
  | D3 barrier | 2 | 2 | 2 | 2 | 2 |
  | D4 post-main and exit | 6049 | 8728 | 9625 | 27698 | 89695 |
  | Total up to 982 | 1000 | 2983 | 3578 | 21950 | 84927 |
  | Total | 6793 | 9504 | 10417 | 28719 | 91496 |
  | 982 | 1 | 25 | 32 | 256 | 1024 |
  | 977 | 16 | 42 | 48 | 272 | 1040 |

- D2 and C1 grow by about one cycle per 64-byte beat (1024 beats at 4096),
  as SG2's DMA does; C3 by N / 4; C5 by about 20 cycles per element, the
  core's two DRAM loads per 64-bit element. C0 moves by up to 28 cycles with
  N, though nothing in boot depends on N but where `.data` sits; probably
  instruction-fetch alignment (tier 3, not looked into).
- L1 at 4096: A, B and O start at 0x10000000, 0x10008000 and 0x10010000 (the
  DMA's `dmdst` operands), so O ends at 0x10018000 (96 KiB); the stacks sit
  at the top, 1 KiB per core (`SNRT_LOG2_STACK_SIZE` 10), hart 1's `sp`
  starting at 0x1001fbd8. About 30 KiB stay free; the largest size that fits
  is about 5300.
- 977 is 42 at 100 with and without P2 (the ELF of `b2672f8` rerun here):
  the two start writes are 14 cycles apart (975 at 2643, 980 at 2657), as in
  SG3 step 2 (2616 and 2630). SG4 step 2's "streamer starts at 2625" and its
  counter 31 do not match a rerun of either ELF; taken as a slip in that
  entry. 977 depends on that gap, so it sits beside the target, not in it.
- The author's container gives the same cycles and polls in C2a to C4 and
  D2 at 100 (step 3's run), with C0, D0 and C6 a few tens of cycles off and
  other instruction counts there: the runtime is built by another toolchain
  build. The regression's expected files come from that container (SG5.md).
- Not rerun: the other programs and the plain tests; P4 changes only
  `snax-alu`'s Makefile and README.

### SG5 P4b: the raw RTL trace

- 2026-10-14. `make traces` stops in the image: `spike-dasm` is not in it
  (`/bin/sh: spike-dasm: not found`, then `gen_trace.py` fails on its empty
  input). The phase script needs only each instruction's cycle and pc, which
  the raw `logs/trace_chip_*_hart_*.dasm` already holds, so it reads those
  directly (`read_rtl_dasm`): the lines from the integer core (`source` 0)
  that are not stalled and not offloaded to the FPU, the lines `gen_trace.py`
  gives a pc in the `.txt`. `--rtl` reads the `.dasm` when there is one,
  the `.txt` otherwise. Format from `snitch_cc.sv` and `snitch_pkg.sv` at
  `d7dd789`; one more unit test (10), on lines written in that format, not
  copied from a run.
- `spike-dasm` would be a build of Spike (riscv-isa-sim) in snax-forge's
  image; not needed for SG5, so not added.

### SG5 step 5: the RTL run

- 2026-10-14. Author's run of the five ELFs of P4 (built in the author's
  container) on snax_cluster's RTL (Verilator, `snax_alu_cluster_old.hjson`
  at `d7dd789`), the raw `.dasm` traces kept per size. Every size prints
  `Accelerator Done!`, `Accelerator Cycles:` 1, 25, 32, 256, 1024 and
  `Number of errors: 0`. Phases from `phases.py --rtl` (polls in brackets):

  | Phase | 4 | 100 | 128 | 1024 | 4096 |
  |---|---|---|---|---|---|
  | C0 boot | 656 | 653 | 639 | 632 | 632 |
  | C1 barrier | 122 | 137 | 148 | 374 | 1154 |
  | C2a CSR setup | 110 | 111 | 110 | 110 | 110 |
  | C2b CSR setup | 16 | 16 | 16 | 16 | 16 |
  | C3 ALU poll | 7 (1) | 32 (6) | 37 (7) | 262 (52) | 1032 (206) |
  | C4 streamer poll | 5 (1) | 5 (1) | 5 (1) | 5 (1) | 5 (1) |
  | C5 check loop | 214 | 4535 | 5795 | 46115 | 184355 |
  | C6 printf | 7238 | 7485 | 8020 | 8240 | 8260 |
  | C7 exit | 143 | 140 | 143 | 143 | 143 |
  | D0 boot | 656 | 653 | 639 | 633 | 633 |
  | D1 DMA issue | 99 | 99 | 100 | 100 | 100 |
  | D2 DMA wait | 20 (4) | 35 (7) | 45 (9) | 270 (54) | 1050 (210) |
  | D3 barrier | 3 | 3 | 3 | 14 | 14 |
  | D4 post-main and exit | 7733 | 12324 | 14126 | 54880 | 193910 |
  | Total up to 982 | 1130 | 5489 | 6750 | 47514 | 187304 |
  | Total | 8511 | 13114 | 14913 | 55897 | 195707 |

- The `.dasm` reader of P4b works on the real traces: every marker is
  found on both harts at every size.

### SG5 step 6: the phases on both sides

- 2026-10-14. Against the author's SNAX-GVSoC run of the same ELFs (P4):
  tier 1 is met (982 equal, 0 errors on both sides, every size). The blocks
  match: at 4096, C1 1148 against 1154, D2 1050 against 1050, C3 1029
  against 1032. C5 does not: 20 cycles per element on SNAX-GVSoC, 45 on the
  RTL, at every size, so the total up to 982 is 55% under at 4096.
- Each instruction's cycle in C5 on both sides (a throwaway script, `--show`
  since P5; one iteration, 15 instructions):
  the RTL issues `lw` (L1), then the next `lw` 4 cycles later, then two
  `lw` from DRAM 14 cycles apart each; each load waits for the previous
  load's data, as `num_int_outstanding_loads: 1` in the hjson says. GVSoC
  issued the four loads on four cycles and stalled once, 6 cycles, at the
  first use; a DRAM load took about 9 cycles. Class: a target parameter
  (the hjson and the core's path, which SG2 left unmeasured): fixed in P5.
- Not fixed, the core's own timing: the RTL polls `dmstati` every 5 cycles
  against GVSoC's 2, so D2 and C1 end up to 9 cycles later at small sizes
  (D2 at 128: 45 against 36, 20%); under 3% from 1024 on. Tier-3 gaps left
  to explain (C2a, C7, D1, D3) follow the fix (step 7).

### SG5 step 7: P5, the core's loads

- 2026-10-14. `Lsu` (`core/models/cpu/iss/`) takes `int_loads_in_flight`
  from the core's properties: 0, no limit, GVSoC's behaviour and the default;
  1, a load stalls the core until the previous load's data is back. Only
  `load` and `load_signed` (integer loads) are limited; stores, `elw` and FP
  loads are not. `ClusterArch` takes `core` (`Snitch` arguments) and
  `core_latency` (cycles on the core's map to the TCDM and to
  `narrow_axi`). `snax_alu.py` sets one load in flight, `tcdm` 2 and
  `narrow` 6: from one load to the next, 4 cycles from L1 and 14 from DRAM,
  as on the RTL (`--show 'C5 check loop'`). Rows in `UPSTREAM.md`.
- First try counted the wait twice: `get_cycles()` already holds the stall
  just accounted, so the load's own latency counts from it without adding
  the wait again.
- `phases.py --show PHASE` lists a phase's instructions on either side; one
  more unit test (11).
- Results in Claude's sandbox (its ELFs; the RTL columns are the author's
  run of the author's ELFs, so boot and `printf` differ by the toolchain
  too). Every size: `Number of errors: 0`, 982 equal. RTL / SNAX-GVSoC:

  | Phase | 128 | 1024 | 4096 |
  |---|---|---|---|
  | C1 barrier | 148 / 154 (+4%) | 374 / 381 (+2%) | 1154 / 1169 (+1%) |
  | D2 DMA wait | 45 / 36 (-20%) | 270 / 262 (-3%) | 1050 / 1050 (0%) |
  | C3 ALU poll | 37 / 39 (+5%) | 262 / 261 (0%) | 1032 / 1029 (0%) |
  | C5 check loop | 5795 / 5698 (-2%) | 46115 / 45244 (-2%) | 184355 / 180754 (-2%) |
  | Total up to 982 | 6750 / 6698 (-1%) | 47514 / 46696 (-2%) | 187304 / 183755 (-2%) |

  Tier 2 is met but for D2 at 128 (step 6). C5 is 44 cycles per element
  against 45: the RTL waits 2 more cycles before `xor a6, a6, a7`, probably
  the L1 load's write-back waiting for a free register-file port (SG5.md,
  "Not verified").
- Tier 3, still to explain from `--show` on both sides: C2a 133 against 110
  (114 before P5: its DRAM loads are now as slow as the RTL's, so something
  else is faster there), C7 81 against 143, D1 117 against 100, D3 2
  against 14 at 1024 and 4096. C6 and the full total now land within 15%.
- Other programs on `snax_alu`, exit 0: `snax-stream` errors 0, 977 31, 982
  25 in all four modes (unchanged); `alu-timing` 977 and 982 as before but
  `out_one_bank`'s 977 209 (211 before, RTL 210), start gaps -7 / 103 /
  103 / -7 / -7; `stream-timing` counters 0, 9, 9, 10, 12 (unchanged), polls
  0, 0, 3, 4, 1; `dma-timing` `busy` unchanged, `done` unchanged but 4x800
  at 82 (80 before, RTL 84); `snax-csr` four lines of `0 errors` and both
  warnings. The 17 plain tests (9-core build) exit 0 on `snitch`,
  `printf_simple` printing `Hello, World!` 9 times.

### SG5: the remaining gaps, from the listings

- 2026-10-14. The author's rerun of the five sizes with P5 (the same ELFs
  as the RTL run) at 100: total up to 982 5471 against the RTL's 5489
  (-0.3%), C5 4468 against 4535. The listings of `phases.py --show` on both
  sides at 100 explain the rest (C2a, D1, C7 below).
- The RTL source behind P5 (snax_cluster `d7dd789`):
  `hw/snitch/src/snitch_lsu.sv` holds loads waiting for data in a queue
  `NumOutstandingLoads` deep (line 72) and holds a new load while it is
  full, stores excepted (lines 118, 155); the hjson sets it to 1. The core's
  data port has a request and a response register (`RegisterCoreReq`,
  `RegisterCoreRsp`, `snitch_cc.sv` lines 308-309, on in the hjson): the
  `tcdm` +2. The way to DRAM adds the narrow crossbar cut on all ports
  (`NarrowXbarLatency`, `snitch_cluster.sv` line 360) and the external
  narrow port's registers (`RegisterExtNarrow`, lines 1413 and 1502): the
  `narrow` +6 is fitted to the trace, not counted stage by stage.
- C2a (RTL 111, SNAX-GVSoC 133): the loads now cost the same on both sides
  (14 cycles to the next load or the use). The difference is instruction
  fetch: both caches have 32-byte lines (`cacheline: 256`); GVSoC misses
  each time execution enters a new line (6 misses of about 10 cycles), the
  RTL twice (16 and 22 cycles, entering `0x2c0` and `0x2e0` on the way back
  into `main`). The RTL's L0 prefetches on a hit, the next line or the
  target of a taken branch or `jal` it finds in the line
  (`cluster_icache`'s `snitch_icache_l0.sv` lines 289-371, read at `main`,
  `d94589e`; the RTL build's `Bender.lock` holds the exact commit), so the
  `configure_*` lines are there on the first jump; GVSoC's
  `Hierarchical_cache` L0 does not prefetch. The core's fetch timing:
  explained, accepted, not modelled.
- D1 (RTL 99, SNAX-GVSoC 115): the same, on the DMA core (GVSoC misses at
  `0x254`, `0x260`, `0x280`, `0x3ac`, `0x3c0`, `0x3e0`); the RTL instead
  waits 5 to 8 cycles after each of its first three stack stores (not
  looked into).
- C7 (RTL 140, SNAX-GVSoC 79): the testbench's memory. The exit's second
  barrier waits for the DMA core's software global barrier (atomic adds, a
  load and a store on `_snrt_barrier` in DRAM): 78 cycles on the RTL, 50 on
  SNAX-GVSoC; the load of `_reduction_result` right after takes 41 cycles
  on the RTL, 13 on SNAX-GVSoC. The RTL testbench puts
  `axi_riscv_atomics_wrap` (at most 2 reads and 2 writes in flight) in
  front of its DRAM (`target/common/test/tb_memory_axi.sv` line 58), so
  every atomic to DRAM is a read-modify-write in that adapter and the load
  behind them waits; SNAX-GVSoC treats an atomic as one access. Outside the
  cluster, tier 3, accepted. The first post-main barrier's 14 cycles on the
  RTL (1 here) are not looked into.
- All four are the core's or the testbench's own timing (SG5.md, "Gaps
  outside the target"); they go to snax-forge as open items in P7.

### SG5 step 8: P6, the regression

- 2026-10-14. `tests/snax/regress.py`, `make regress`: builds the programs,
  runs each on `snax_alu`, and compares exactly with `expected/` per
  program: `snax-alu` at five sizes (`<N>.out`: printed lines, exit code,
  977 from the streamer's trace; `<N>.phases.json`), `snax-stream`,
  `alu-timing`, the five `stream-timing` cases, `dma-timing`, `snax-csr`
  with its two warnings. It then checks `snax-alu` against
  `tests/snax/snax-alu/rtl/` (the author's printed lines and phase tables of
  step 5, the JSON written from those tables in `phases.py --json`'s form):
  tier 1 at every size, tier 2 at 128, 1024 and 4096, C1 and D2 at 128 in
  an accepted list with their reason. `REGRESS_FLAGS=--update` rewrites
  `expected/` only. Exit 0 when all match, 1 otherwise, so CI can run it as
  it is.
- `make regress-plain` builds snax_cluster's plain tests for its 9-core
  cluster into `build/regress/plain/`, then rebuilds the runtime for the ALU
  cluster; `regress` runs them on `snitch` when they are there (17, each
  exit 0). In Claude's sandbox the round trip leaves `snax-alu`'s ELF
  byte-identical.
- Results in Claude's sandbox (its own expected files, not checked in):
  `--update` then `make regress` passes in about 50 s with the plain tests;
  tier 2 at 128: C1 +4%, D2 -20% (accepted), C3 +5%, C5 -2%, total up to
  982 -1%; at 1024 and 4096 every row within 3%. With one expected value
  changed (977 at 100) it fails on that file alone and exits 1.
- The expected files are written in step 9, in the author's container.

### SG5 step 9: the expected files, and the RTL run again

- 2026-10-14. Author's container: `make regress-plain`, then
  `make regress REGRESS_FLAGS=--update` wrote the 19 expected files, and
  `make regress` passed. Its numbers equal Claude's sandbox exactly (total
  up to 982 1157, 5444, 6698, 46696, 183755; 977 16, 42, 48, 272, 1040), but
  not the author's earlier run (5471 at 100): `regress-plain` rebuilt
  snax_cluster's runtime, and with it the `snax-alu` ELFs. The ELFs of
  steps 4 to 7 came from an earlier runtime build (C0 123 instructions, now
  122; only boot, `printf` and exit code differ, `main` is the same); what
  made that build differ was not found.
- So the step-5 RTL tables were from other ELFs than SNAX-GVSoC now runs.
  The author ran the current five ELFs on the RTL again and refreshed
  `tests/snax/snax-alu/rtl/` (`phases.py --json`, the printed lines, and
  the ELF's sha256 per size); C0 is 122 instructions on both sides.
  `make regress` passes against it: at 128 C1 +5%, D2 -20% (accepted), C3
  +5%, C5 -2%, total up to 982 0%; at 1024 and 4096 every row within 3%, as
  before. The step-5 table above stays as the record of that run.
- P6b: `regress.py` checks each size's ELF against `rtl/<N>.elf.sha256` and
  fails a size whose ELF changed ("the RTL reference ... comes from another
  ELF"); a missing hash file fails too. The top README has the commands to
  refresh `rtl/`. In Claude's sandbox: passes with the hashes of its ELFs;
  with one hash changed it fails on that size alone and exits 1.

### SG5 step 10: SG5 closed

- 2026-10-14. All steps done; acceptance met: the deviation per phase is
  inside the target or explained (SG5.md, "Result"), and `make regress`
  fails when a number drifts (step 8) or when the RTL reference is from
  another ELF (P6b).
- Settled (the list is in `docs/plans/SG5.md` under "Decided"): the phases
  from both sides' instruction traces of one ELF; the DMA wait in
  snax_cluster's app (`d7dd789`); five sizes; the three-tier target with
  tier 2's total up to the read of 982; the core's loads as the hjson and
  the RTL have them; the regression with expected files from the author's
  container and RTL references hash-checked against the ELF. In snax-forge:
  D124, D125, open items 65 to 67, CI1.
- Upstream files changed in SG5: `core/models/cpu/iss/include/lsu.hpp`,
  `include/lsu_implem.hpp`, `src/lsu.cpp`, `pulp/pulp/snitch/snitch_core.py`,
  `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` (P5) and `Makefile`
  (P6); rows in `UPSTREAM.md`. New: `tests/snax/phases.py`,
  `test_phases.py`, `regress.py`, `snax-alu`'s `DATA_LEN` builds and its
  `expected/` and `rtl/` folders, the other programs' `expected/`.
- Next: SG6, Zicsr on SNAX CSRs on both sides, from the list under "SG6
  starts from" in `docs/plans/SG5.md`; then the housekeeping pass; then CI1.

### SG6 step 1: round 1, the RTL

- 2026-10-14. Author's run on snax_cluster's branch `ry/sg6-zicsr` at
  `8d16b0c` (`4ffe96a`, the pin, adds a README and `.gitignore` change
  only), RTL built from `snax_alu_cluster_old.hjson` and run on Questa
  2022.4. `docs/plans/SG6.md` has the forms and the change:
  - `snitch.sv`, the SNAX branches of the decoder only: `csrrw` / `csrrwi`
    with `rd` not `x0` take `rd` from the accelerator's response (`write_rd`
    0, `uses_rd` and `acc_register_rd` 1, as `csrrs`); `csrrs` / `csrrc` send
    `rs1` as operand A, `csrrsi` / `csrrci` the `uimm`.
  - `snax_intf_translator.sv`: a read then a write for `csrrw` / `csrrwi`
    with `rd` not `x0` and for the set and clear forms with `rs1` / `uimm`
    not 0 (old value, or old `|` / `& ~` mask), accepted only with no older
    read outstanding, `qready` low until the write is taken. A small state
    machine (`RmwIdle`, `RmwWaitRsp`, `RmwWrite`); the read's data goes to
    the core through the existing ID FIFO. `csrw` and `csrr` keep their
    handshake and timing.
- Before, at `d7dd789`, `snax-csr` (the program of SG5) on the RTL:
  `csrw/csrr: 0 errors`, `csrrw: 17 errors` (each old value read as
  `rs1 + CSR number`), `csrrs/csrrc/csrrwi: 20 errors` (3 more: nothing
  written), `read-only: 20 errors`, exit code 20.
- After, on `ry/sg6-zicsr`: four lines of `0 errors`, exit code 0.
  `snax-alu` at the five sizes, the ELFs of `rtl/` (sha256 equal): the phase
  tables of `phases.py --rtl` and the printed lines equal `rtl/<N>.json` and
  `rtl/<N>.out`. A clean rebuild (`make clean`, 750 modules compiled) gave the
  same.
- Seen on the way: `vsim` exits 0 whatever the program returns (the
  testbench prints `[SUCCESS]` or `[FAILURE] Finished with exit code N`); on a
  host without bender, `make bin/snitch_cluster.vsim` does not see an edited
  `.sv` file. Both are in snax_cluster's `target/snitch_cluster/README.md` on
  that branch.

### SG6 step 2: round 2, SNAX-GVSoC

- 2026-10-14. Before the change, `make build TARGETS="snitch;snax_alu"`
  failed: main (`44453a3`, #5) removed the root `CMakeLists.txt`. Restored on
  the branch from `61905d3`, unchanged, to be fixed on main. snax_cluster's
  runtime was rebuilt (`make sw` for the ALU cluster; round 1's `make clean`
  had removed it); the `tests/snax/` ELFs relinked against it differ from
  `rtl/` only in their symbol table, three mapping symbols (`$x`, `$d`, `$d`)
  from `snitch_cluster_start.S`: with every symbol stripped they are
  byte-identical. The earlier ELFs were put back, so `rtl/`'s hashes hold;
  why the start-up object gained the symbols was not found. Then
  `make regress` passed.
- `snax-csr`'s part 3 gains, on 960 after `csrwi 5`: `csrrwi rd, 960, 7`,
  `csrrsi rd, 960, 8`, `csrrci rd, 960, 3` (old value 5, 7, 15; then 7, 15,
  12), and on the read-only 982 (0, nothing ran): `csrrc rd, 982, x0`,
  `csrrsi rd, 982, 0`, `csrrci rd, 982, 0`, each 0. Its label is now
  `set/clear/imm`. With main's GVSoC it stopped at the first no-write form,
  `csrrc a3, 982, x0` (pc `0x80001218`), at cycle 9270:
  `/chip/soc/cluster_0/snax_acc0/alu/trace Write to read-only CSR 982
  (value: 0x0)`, exit 1; the checks on 960 had passed. The two SG4 warnings
  came out on stdout there, not stderr as the README said.
- `priv.hpp` (every core): `csrrc` with `rs1 = x0` and `csrrsi` / `csrrci`
  with 0 write nothing and ask `check_access()` for no write, as `csrrs`.
  An input `x0` decodes as 0 (`decode.cpp`); only an output `x0` is
  `ISS_NB_REGS`. Upstream's generic `csrrw` / `csrrwi` path still reads with
  `rd = x0` (its `!= 0` check, SG1 step 6); SNAX CSRs do not use it
  (`SnaxCsr::handle()`), so it is left.
- SG4 P3's two warnings and their flags removed (`snitch.cpp`, `class.hpp`),
  the comments saying both sides follow Zicsr; `UPSTREAM.md` drops SG4 P3's
  rows and gains `priv.hpp`'s.
- Results in the author's container:
  - `snax-csr`: four lines of `0 errors`, exit 0, nothing on stderr. The
    streamer and the ALU see 110 accesses, 69 reads and 41 writes (streamer
    58 and 37, ALU 11 and 4); SG4's 98 plus 9 reads and 3 writes on 960 and
    3 reads on 982. As in SG3 step 2, a `printf` line split one `csr_mux`
    trace line, so a `grep` there finds 68 reads.
  - Static scan of the 31 ELFs `make regress` runs (a throwaway script,
    opcode 0x73, funct3 3, 6 or 7, bits 19:15 = 0): 0 in every ELF but
    `snax-csr`, which has 4, its three forms and a copy of the `csrrc` that
    clang put in the error path of the check before it.
  - `make regress`: failed on `snax-csr`'s expected file alone (`expected:
    csrrs/csrrc/csrrwi: 0 errors`, `got: set/clear/imm: 0 errors`; the two
    warning lines gone too); `REGRESS_FLAGS=--update` wrote that one file;
    then `regression passed`, every other number unchanged.

### SG6 step 3: round 3

- 2026-10-14. snax_cluster merged the branch as `9fbf35d` (#657), the same
  tree as `4ffe96a`; it is the pin for the programs and the RTL reference
  (Pins above, the clone command in `README.md`, `snax-alu`'s README, the
  comments in `snitch.cpp`). The app, its library and the runtime are as at
  `d7dd789`.
- `make regress` checks only that each program finishes (the author's
  choice): exit 0 within 300 s, on `snax_alu` for the 14 SNAX runs and on
  `snitch` for the 17 plain ELFs when they are there; it names each program
  that does not. No exact numbers, `expected/` files, RTL references or ELF
  hashes: every `tests/snax/*/expected/` and `tests/snax/snax-alu/rtl/` are
  removed (SG5's numbers stay in `docs/plans/SG5.md`, "Result", and in the
  entries above), and `--update` is gone. `phases.py` and its tests stay:
  the comparison with the RTL is made by hand from fresh runs of one ELF on
  both sides (README, "Comparing with the RTL (by hand)"). Tried at 100 with
  round 1's RTL traces: up to the read of 982, 5436 cycles on the RTL and
  5444 on SNAX-GVSoC.
- `make regress-plain`, then `make regress`: `regression passed`, exit 0
  (14 SNAX runs, 17 plain). The rebuilt runtime relinks the `snax-alu`
  ELFs (round 2's symbol-table difference), which no longer matters. With
  `snax-csr` returning 1 for one run: `FAIL snax-csr: exit 1`, then
  `regression FAILED: 1 program(s): snax-csr`; `regress.py` exits 1 (`make`
  2). Reverted; passes again. The timeout path was not exercised.

### Housekeeping after SG6

- 2026-10-15. Branch `ry/housekeeping` from main `3cab3fa` (#6). No change
  in what a program prints, in any cycle or in any trace line, but the one
  message in `snitch.cpp` below.
- Removed: `snax/snax_csr_stub.py` / `.cpp`, unused since SG3 P2 (the
  target binds `SnaxAluAcc`, whose `csr_mux` splits the CSRs between the
  streamer and the ALU); the README's layout row no longer names it.
- `snax_streamer.cpp`: `start()` configures the movers in place and returns
  nothing. `channel(mover, lane)`, `agu_has_room()` and `has_addresses()`
  (used by `mover_busy()`) replace the loops repeated in `commit_handler`,
  `reader_req`, `writer_req` and `summary_handler`. The TCDM, reader and
  writer ports, `Channel::reqs` and `Channel::bufs` are `std::vector`s, sized
  once before any port is registered or any pointer taken.
- `snax_tcdm_xbar.cpp`: one `Response {cycle, req, input}` per pending
  response; `respond()` answers the due ones in grant order and keeps the
  others in place. `bank_req` is a member, cleared per arbitration; inputs
  and banks are `std::vector`s; the input names are set in one loop.
- `snax/snax_csr_block.hpp`: `SnaxCsrBlock`, what the ALU's and the
  streamer's `csr_req` shared: the size and alignment check, the read-write
  read and write, the read-only read and the write refusal, the "not held by
  this block" refusal, with the same trace lines. Each block keeps its start
  (the ALU's latch; the streamer's start and its busy refusal) and how it
  computes busy and the counter. The header is 110 lines and the two
  `csr_req` went from 59 and 63 lines to 30 and 32, so 50 lines more in all;
  kept, since the rules are now in one place and a next block writes only
  its own part.
- `snax_alu_shell.cpp`: `reset()` clears `classes[]`.
- `snitch.cpp`: an `IO_REQ_INVALID` answer ends the run with `SNAX CSR access
  refused by the block (id: ..., is_write: ...); see its trace`; pending and
  denied keep `not answered at once`. With `werror` the block's own warning
  stops the run before either (SG1 step 6), so no program prints them.
- `snax_alu_acc.py`: `SNAX_CSR_FIRST` and `SNAX_CSR_LAST` both in hex (0x3C0,
  0x5FF). `cfg/snax_alu_cluster_old.hjson` is unchanged from `b2672f8` up to
  the pin `9fbf35d` (`git diff` in snax_cluster); said there and in
  `snax_alu.py`'s docstring.
- `regress.py`: each run writes its stdout and stderr to
  `build/regress/work/<name>/run.log` (`plain/<test>/run.log` for the plain
  tests); a failure prints that path and the log's last 20 lines.
  `-k SUBSTRING` runs only the programs whose name holds it. README,
  "Regression".
- Stale text: `snax-csr.c`'s header and README (no test datapath, no SG3 or
  SG4 history), "On SNAX-GVSoC" in the program READMEs, `SG6.md` line 7.
  `alu-timing`'s README still showed SG4 P4's output (start gaps -16, 105,
  105; 977 134 and 211); it now shows today's (-7, 103, 103; 132 and 209), as
  in SG5 step 7. The counters it compares are unchanged.
- Decided: the ALU keeps its event every cycle while busy (about N / 4
  cycles a run); sleeping would need the streamer to wake it while keeping
  the ALU-before-streamer order.
- Upstream file changed: `snitch.cpp`; its row in `UPSTREAM.md`.
- Results, Claude's runs in the snax-forge image on the MICAS server:
  - On main, before any edit: `make build TARGETS="snitch;snax_alu"`,
    `make regress-plain`, `make regress`: `regression passed` (14 SNAX runs,
    17 plain). A throwaway script then saved the stdout and stderr of the 31
    runs `make regress` makes, `phases.py --json` at the five sizes (and the
    md5 of both `insn` traces), and the `snax_acc0` and `snax_xbar` traces of
    `snax-alu` at 100 and `stream-timing` `ab_same_banks`.
  - With the changes: `make build`, then `make regress`: `regression passed`.
    The script's rerun equals the first run in every file: empty diff. Only
    the heap addresses in GVSoC's `New slave port (... port: 0x...)` lines
    were masked; they differ between two runs of main too.
  - With `snax-csr` returning 1: `FAIL snax-csr: exit 1`, then
    `log build/regress/work/snax-csr/run.log, last 20 lines:` and its five
    lines (the four `0 errors`, then `Input error: Platform returned an error
    (exitcode: 1)`), `regression FAILED: 1 program(s): snax-csr`, `make` exit
    2. Reverted. `-k snax-csr` runs 1 program, `-k stream-timing` 5.

### CI1 round 1

- 2026-10-15. Branch `ry/ci1` from main `86a85e3` (#7); `docs/plans/CI1.md`.
  snax-gvsoc builds its programs from a pinned copy of snax_cluster's
  software in `sw/`, so no snax_cluster checkout is needed to build or run
  them; the RTL still runs in one. Round 2, the workflow, comes later.
- Step 0, on main before any change: `make regress-plain` (exit 0; its
  second `make sw` built `snax-alu-lib.c` without error), then every
  program: `snax-alu` at `DATA_LEN` 4, 100, 128, 1024, 4096 and without,
  `snax-stream`, `alu-timing`, the five `stream-timing` cases,
  `dma-timing`, `snax-csr`. The 32 ELFs (17 plain, 15 SNAX) were kept
  outside the repos as the reference.
- `sw/` (144 files): 114 copied unchanged from snax_cluster `9fbf35d` and
  its two submodules (the list is `COPIED` and `MATH` in `sw/sync.py`: the
  runtime, `math/` but its Makefile, `.gitignore` and `include/bits/`, the
  17 plain tests, the `snax-alu` app and library, the two cluster hjsons,
  `data_utils.py`, the licences), snax_cluster's `sw/` and
  `target/snitch_cluster/sw/` merged so every relative include works;
  6 generated with upstream's rules (`snitch_cluster_cfg.h` and
  `snitch_cluster_addrmap.h` per cluster, `snitch_cluster_peripheral.h`,
  equal for both, `alltypes.h`); `streamer_csr_addr_map.h`, a hand copy,
  moved from `tests/snax/snax-alu/include/`; `sync.py`, `README.md`,
  `Makefile`, `common.mk`; the 19 files of the six programs, moved from
  `tests/snax/` to `sw/apps/` (`snax-alu`'s checked-in `data.h`, `lib/`
  and `include/` removed: `data.h` is made per build, default `DATA_LEN`
  100). Nothing beyond the planned copy list was needed.
- `make sync-snax-cluster SNAX_CLUSTER=../snax_cluster`, in the image: run
  twice at the pin, the second left `git status` clean; a file added under
  `sw/math/` by hand was removed. It refuses tracked changes only in what it
  reads (`CHECKED`: `sw/`, `target/`, `util/`, `hw/snitch_cluster/`,
  `LICENSE`), so the generated `StreamParamGen.scala` that `rtl-gen` leaves
  modified does not stop it. The checkout's `streamer_csr_addr_map.h` (from
  its last `rtl-gen`) equals ours but for its `Generated at` line, which
  the comparison skips.
- ELF comparison: every one of the 32 ELFs built from `sw/` equals its
  reference, stripped with `llvm-objcopy --strip-all` and also unstripped,
  byte for byte; `snax-alu` without `DATA_LEN` was compared with the new
  default 100 (the old checked-in `data.h` was the 100-element one).
- `make build TARGETS="snitch;snax_alu"`, then `make regress`:
  `regression passed`, 14 SNAX runs and 17 plain, about 70 s.
  `test_phases.py`: 11 passed (pytest is not in the image; it ran from a
  throwaway install in the container). A plain ELF missing fails the run
  (`FAIL plain simple: build/nonexistent/simple.elf missing`, exit 1, with
  the folder pointed elsewhere).
- Standalone: `ry/ci1` cloned into a folder with nothing else in it,
  mounted alone in the image: `make build TARGETS="snitch;snax_alu"` (1 min
  39 s), then `make regress`: `regression passed`, 14 and 17. In the
  Makefiles only `sync-snax-cluster` names a snax_cluster path.
- Figures from Claude Code's runs in the snax-forge image on the MICAS
  server.

### CI1 fix-up after review

- 2026-10-15. On `ry/ci1` (the open pull request), after round 1's review.
  No change to what any program is built from or prints.
- One list of plain tests (D117 in snax-forge): `COPIED` in `sw/sync.py`.
  `sw/Makefile` takes `TESTS` from `sw/tests/*.c` and `regress.py` its
  plain tests from the same files; a test whose ELF is missing from
  `build/sw/tests/` still fails the run.
- Header dependencies: `sw/common.mk` adds `-MMD -MP -MT $@ -MF` with the
  ELF's name in `.d` to every program's compile and includes the files, so
  each ELF in `build/sw/apps/<name>/` has its `.d` beside it. The
  hand-listed headers are gone from `stream-timing`'s Makefile
  (`streamer_csr_addr_map.h`) and from `dma-timing`'s (`data/data.h`);
  `snax-alu` keeps its generated `data.h` as a prerequisite, since it must
  be made before the first compile.
- Correction to round 1's entry: `test_phases.py` is a `unittest` file;
  `python3 -m unittest discover -s tests/snax -p 'test_*.py'` runs it in the
  image with nothing installed (Ran 11 tests, OK). Round 1 installed pytest
  in a throwaway container for it; that was not needed. `CI1.md` names
  this command, and round 2's workflow will run it.
- `CI1.md`: round 2 lands in the same pull request as round 1 and this
  fix; the fix-up is ticked there.
- Checks, in the image:
  - Before any edit, `make sw` and every program (`snax-alu` at 4, 100,
    128, 1024, 4096) were built and the 31 ELFs of `build/sw/` kept outside
    the repos. After the fix, a clean rebuild gives 31 ELFs, each equal
    byte for byte.
  - `touch sw/generated/snax_alu_cluster_old/streamer_csr_addr_map.h`:
    `make -C sw/apps/snax-alu` relinks, `make -C sw/apps/snax-csr` does not;
    then `make -q` exits 0 for both. `touch sw/apps/dma-timing/data/data.h`
    relinks `dma-timing` through its `.d` alone.
  - `simple.elf` moved out of `build/sw/tests/`, and `regress.py`'s
    `main()` called from Python with its `make` of `sw/` replaced by a
    no-op, `-k plain`: `FAIL plain simple: build/sw/tests/simple.elf
    missing`, 16 run, `regression FAILED: 1 program(s): plain simple`, exit
    1. The ELF was moved back.
  - `make regress`: `regression passed`, 14 SNAX runs and 17 plain.
- Figures from Claude Code's runs in the snax-forge image on the MICAS
  server.

### CI1 round 2

- 2026-10-15. On `ry/ci1` (the open pull request); `docs/plans/CI1.md`,
  "Round 2".
- `.github/workflows/ci.yml`, workflow `CI`: on push to main, on pull
  requests and by hand; one run per ref at a time (a newer one cancels
  it); read-only contents. One job `regress` on `ubuntu-latest` in
  `ghcr.io/kuleuven-micas/snax-forge:main`, 30 minutes at most: checkout
  (no submodules); the ccache environment set through `$GITHUB_ENV` from
  `$GITHUB_WORKSPACE` (`CCACHE_DIR` in `.ccache`, 500 MB, CMake's C and C++
  launchers, so the Makefile is unchanged); the latest ccache restored;
  `make build TARGETS="snitch;snax_alu"` and `ccache -s`; `python3 -m
  unittest discover -s tests/snax -p 'test_*.py'`; `make regress`; on a
  failure every `run.log` as the `regress-logs` artifact; ccache saved
  after every run whose build passed, pull requests included. Only
  `snax/`, `sw/` and `tests/snax/` are built and tested.
- `regress.py`: with `GITHUB_ACTIONS=true` each failure also prints
  `::error title=<program>::<why>, log <path>` (no log part for a missing
  plain ELF); nothing changes outside Actions. `.ccache/` is ignored.
- Local checks, Claude Code's runs in the snax-forge image on the MICAS
  server (the workflow itself runs only on GitHub):
  - `yaml.safe_load` reads the workflow: one job, 8 steps.
  - With `build/`, `install/` and `.ccache` removed, the commands of steps
    2 to 6 as written, from the repository root with the same variables
    (`GITHUB_WORKSPACE` the repository, `GITHUB_ENV` a file read back):
    `make build` passed with CMake's cache holding the `ccache` launchers
    (cmake 3.28.3); `ccache -s`: 509 cacheable calls, 485 misses, the cache
    in `.ccache` (21 MB); the unit tests ran 11, OK; `make regress`:
    `regression passed`, 14 SNAX runs and 17 plain. A second build after
    removing `build/` and `install/` hit the cache on all 509 calls.
  - With `snax-csr` returning one more than its error count (not
    committed) and `GITHUB_ACTIONS=true`, `regress.py -k snax-csr` printed
    `::error title=snax-csr::exit 1, log build/regress/work/snax-csr/run.log`
    beside its `FAIL` line and log tail, then `regression FAILED: 1
    program(s): snax-csr`, exit 1.
- The GitHub runs; the figures are from GitHub's run pages, not from
  Claude Code's runs:
  - https://github.com/KULeuven-MICAS/snax-gvsoc/actions/runs/38748023138,
    PR #8 at `0b71d09` (the revert; the break commit arrived in the same
    push, so it was not run on its own): passed, the job 6 min 21 s with
    no cache yet.
  - https://github.com/KULeuven-MICAS/snax-gvsoc/actions/runs/38757868926,
    a throwaway PR #9 from branch `ry/ci1-break` at `8022f16` (`snax-csr`
    returning one more than its errors): failed at Regress, annotation
    "snax-csr: exit 1, log build/regress/work/snax-csr/run.log", artifact
    `regress-logs` (5.7 KB), the job 6 min 38 s cold (a pull request does
    not read another pull request's cache). PR #9 closed unmerged, the
    branch deleted.
  - The runs gave two notices: the v4 actions run on Node 20, which
    GitHub deprecated, and `ubuntu-latest` moves to Ubuntu 26 from
    2026-10-19. So `actions/checkout` and `actions/upload-artifact` went
    to v7 and `actions/cache/restore` and `actions/cache/save` to v6, all
    on Node 24, with the same inputs (none we use changed meaning in their
    READMEs and release notes at those tags), and the runner is pinned to
    `ubuntu-24.04`: the job runs in the image, the runner only hosts
    Docker and Node. `yaml.safe_load` still reads the workflow (one job,
    8 steps); the new versions are not run yet.

### SG7 step 2: RTL generation

- 2026-10-15. Branch `ry/sg7-sparse` from main `130cc70` (#8);
  `docs/plans/SG7.md`. snax_cluster at the pin `9fbf35d`, submodules
  updated, in `../snax_cluster`; in the snax image `d3d8f5572ff4`
  (`ghcr.io/kuleuven-micas/snax:main`), the parent folder mounted at its
  own path, from `../snax_cluster`:

      make -C target/snitch_cluster clean
      make -C target/snitch_cluster rtl-gen CFG_OVERRIDE=cfg/snax_alu_cluster.hjson

  Exit 0. snaxgen ran `SparseInterconnectGen` with `--NumInp 15 --NumOut 32
  --memAddrWidth 9 --tcdmAddrWidth 17 --dataWidth 64 --strbWidth 8
  --priorityWidth 1 --sparseConfig "[[12, 1], [1, 1], [1, 1], [1, 1]]"`:
  the 12 SNAX ports, the two cores, AXI. `StreamParamGen.scala` is
  rewritten by `rtl-gen`, as always; nothing else tracked changed.
- `target/snitch_cluster/sw/snax/snax-alu/include/streamer_csr_addr_map.h`
  against `sw/generated/snax_alu_cluster_old/streamer_csr_addr_map.h`,
  without the `// Generated at` line: equal.
- The second module, with granularity, from `hw/chisel` in the same image;
  the widths are snaxgen's formulas for this cluster (512 words per bank:
  9 and 17 bits, 64-bit data, 8 strobes):

      sbt 'runMain snax.sparse_interconnect.SparseInterconnectGen --NumInp 23
        --NumOut 32 --memAddrWidth 9 --tcdmAddrWidth 17 --dataWidth 64
        --strbWidth 8 --priorityWidth 1
        --sparseConfig "[[12, 1], [8, 8], [1, 1], [1, 1], [1, 1]]"
        --hw-target-dir <snax-gvsoc>/build/sg7/mixed'

  Exit 0: 23 inputs, 16 per bank.
- The two modules, not committed: `build/sg7/alu/SparseInterconnect.sv`
  (copied from `target/snitch_cluster/generated/`, sha256 `befb96a997bebd81`)
  and `build/sg7/mixed/SparseInterconnect.sv` (`786ffb0cddd09c93`).
- Figures from Claude Code's runs on the MICAS server.

### SG7 step 3: the sparse hjson in sw/

- 2026-10-15. `sw/sync.py`: `target/snitch_cluster/cfg/snax_alu_cluster.hjson`
  in `COPIED`; `SAME_HEADERS` maps `snax_alu_cluster` to
  `snax_alu_cluster_old`: sync makes the sparse cluster's
  `snitch_cluster_cfg.h`, `snitch_cluster_addrmap.h` and
  `snitch_cluster_peripheral.h` with upstream's rule, after the two
  clusters it keeps, and fails unless all three equal the old cluster's.
  No `generated/snax_alu_cluster/` folder and no runtime of its own: its
  programs are the old cluster's ELFs. The streamer header comparison is
  unchanged. The checkout is left on the sparse cluster (`cfg/lru.hjson`).
- `make sync-snax-cluster SNAX_CLUSTER=../snax_cluster` in snax-forge's
  image, at the pin: `9fbf35de -> 9fbf35de`; the diff is `sw/sync.py` and
  the new `sw/cfg/snax_alu_cluster.hjson` (identical to the checkout's),
  no change upstream in the mirrored build files, the streamer header
  equal but for its `Generated at` line. Run again after the README edit:
  the same, plus `sw/README.md`.
- The failure path, with `SAME_HEADERS` pointed at `snitch_cluster` in a
  throwaway call of `generate()`: `snax_alu_cluster: snitch_cluster_cfg.h
  not equal to snitch_cluster's`, exit 1, nothing under `sw/` changed.
- The checkout's `generated/SparseInterconnect.sv` is unchanged by the
  syncs (same sha256 as step 2's copy).
- `sw/README.md`: three cluster configurations; a row in "Generated files"
  for the sparse cluster's headers (made, compared, not kept); the
  hand-copied `streamer_csr_addr_map.h` comes from either hjson; `snax-alu`
  builds the same ELF for both clusters.

### SG7 step 4: the sparse pick in the crossbar

- 2026-10-15. `snax/snax_sparse_arb.hpp`, plain C++ with no GVSoC include,
  so the crossbar and step 5's check run the same code:
  `SnaxSparseConfig` (the ports `[width, granularity]`; `bank_inputs(b)`,
  `get_global_idx_list`'s order; `reaches(input, bank)`, the RTL's
  assertion) and `SnaxSparseArb`, one bank's arbiter: the mask is the
  valid inputs with priority 1 if any, else all valid ones; if locked and
  the last pick is in the mask it wins, else the lowest masked input above
  the last pick, else the lowest masked input; the pick becomes the
  pointer. `pick()` runs only in cycles where the bank has a request, so a
  pick whose last cycle is not the one before restarts the pointer at
  `inputs - 1` and clears the lock (the RTL's selection in an idle cycle).
  `refused()` sets the lock for the next cycle. One priority bit, as
  snaxgen elaborates the module.
- `snax/snax_tcdm_xbar.{cpp,py}`: property `interconnect`, `plain` (the
  `rr_arb_tree` path, unchanged) or `sparse`, and `sparse_config`, whose
  widths must add up to the inputs (checked in Python and C++). In sparse
  mode each bank keeps its arbiter and its inputs in local order; a request
  to a bank its input may not reach is refused with a warning naming the
  input (`IO_REQ_INVALID`, which stops the streamer); `bank_refuses()` is
  the one entry point for a bank refusing its winner, false for now (the
  DMA in round 4): the winner is then dropped with the losers and locked.
  The priority bit is per input, 0 until step 6; the plain path ignores
  it. In the trace a sparse input asking with priority 1 gets a `!`.
- In snax-forge's image, `make build TARGETS="snitch;snax_alu"` on main's
  crossbar, then `make regress` (passed), keeping every `run.log` and a
  `snax_xbar` and `streamer` trace of the 14 SNAX programs; the same after
  the change: `make regress` passed, and all 31 `run.log` files, the 14
  programs' output and both traces (but the lines with port pointers) are
  byte-identical. The sparse path runs from step 7; the granularity
  warning cannot occur on the ALU cluster (every granularity 1) and was not
  exercised in GVSoC.

### SG7 step 5: the winner check

- 2026-10-15. `tests/snax/sparse_arb/` (README there): `tb.cpp` drives an
  elaborated `SparseInterconnect.sv` and `snax/snax_sparse_arb.hpp` with
  the same random stimulus and compares, per bank and cycle, the module's
  request valid and address with the model's pick, and per input its
  `ready` with the model's. Each input's bank-local address is its own
  index, so the address names the selection, also when the bank refuses.
  Phases of 500 cycles with their own load (0.05 to 0.95), bank spread
  (1, 2, 4 or 32 banks), priority rate (0 to 1) and refusal rate (0 to
  0.4); only accesses the granularity allows. `ports.py` writes the port
  accessors; `run.sh` builds and runs. Run by hand, not in regress or CI.
- Simulator: Verilator 5.024 in `d3d8f5572ff4`, which has no Icarus.
  The module's own legality assertion stayed silent.
- Results, 20000 cycles each, seeds 1, 2 and 3; every selection and every
  `ready` equal in all nine runs. Seed 1:

  | Module | Model | Selections | Contested | By priority | After a refusal | After an idle cycle | Refusals | Differences |
  |---|---|---|---|---|---|---|---|---|
  | `alu` (15 inputs) | the same | 56885 | 25073 | 11057 | 2831 | 4582 | 10343 | 0 |
  | `mixed` (23 inputs, `[8, 8]`) | the same | 104766 | 27430 | 9140 | 2498 | 5679 | 12769 | 0 |
  | `alu` (15 inputs, 12 to 14 idle) | `[[12, 1]]` | 42244 | 17035 | 7454 | 2566 | 3149 | 6684 | 0 |

  Seeds 2 and 3: 44361 and 51250, 104523 and 135022, 43757 and 45590
  selections, 0 differences.
- The check fails on a wrong rule: three copies of the header, each with
  one rule broken (no restart after an idle cycle; no lock; priority
  ignored), against `alu` at seed 1: 1534, 1244 and 8248 selection
  differences, exit 1.

### SG7 step 6: the streamer's priority bit

- 2026-10-15. The rule, read from `DataRequestor.scala`,
  `ComplexQueue.scala`, `Reader.scala` and `Writer.scala`, is in
  `SG7.md`, "The priority bit": a request first sent in cycle t carries the
  lane queue's hint of cycle t - 1 (reader `count <= 1`, writer
  `count >= fifo_depth - 1`, the count from the queue's registers), and a
  resent request keeps its bit; `priorityHold` reloads only in a cycle with
  no request or when the request fires.
- `snax/snax_streamer.{cpp,py}`: the template keys `dynamicPriority` and
  `higherStaticPriority` per reader and writer, read as
  `stream_param_gen.scala.tpl` reads them (default dynamic, static 0).
  Each channel takes its bit when it makes a new request, from the count
  during the cycle before (the words visible by then and not popped before
  it; the words popped in the last two cycles are kept for that), and sets
  its wire `tcdm_prio_<i>` before every send and resend.
- The bit is carried on a `wire<bool>` per SNAX port, not in the
  request: `SnaxTcdmXbar`'s `prio_<i>` stores it for the cycle and clears it
  with the cycle's requests, so a port that never sets it (a core through
  routers, round 3) asks with priority 0. `snax_alu_acc.py` and
  `snitch_cluster.py` (`SnitchClusterTcdm`, `SnitchCluster`) bind the
  wires; a row in `UPSTREAM.md`.
- In snax-forge's image, `make build TARGETS="snitch;snax_alu"`, then
  `make regress`: passed; all 31 `run.log` files and, but for the
  configuration lines at time 0 (the new wires' bindings), the 14 SNAX
  programs' output and `snax_xbar` and `streamer` traces equal step 4's
  main baseline: the plain crossbar ignores the bit.
- The bits checked by hand on a sparse run, with step 7's target built
  from the work tree before step 7's commit: `stream-timing`'s
  `ab_same_banks`, start written at 4713. Reader A's lane 0 asks at 4715,
  4716, 4717 and 4718 with priority 1 (its queue counts 0, 0, 0 and 1 in the
  cycle before) and at 4719 with 0 (count 2); reader B's lane 0, held on
  bank 0 at 4715, is resent at 4716 with the same 1, then asks with 1 up to
  4719 and with 0 at 4720. Counter 10, as on the plain target. The writer's
  bit was not looked at here: the writer does not run in `stream-timing`.

### SG7 step 7: the snax_alu_sparse target

- 2026-10-15. `snax/snax_alu_sparse.py`: the `snax_alu` board with
  `interconnect = {'snax_interconnect': 'sparse', 'snax_sparse_config':
  {0: [[12, 1]]}}`, the accelerator's `sparse_interconnect_config` in
  `cfg/snax_alu_cluster.hjson`; target `snax_alu_sparse`. `snax_alu.py`
  takes the interconnect from the board's class attribute (`INTERCONNECT`,
  plain) on both arch paths: `SnitchArchProperties` for `make build`
  (without `USE_GVRUN`), `SnaxAluAttr` for gvrun.
- `snitch_cluster.py`: `ClusterArch` (both paths) takes
  `snax_interconnect` and `snax_sparse_config`; `SnitchCluster` lists the
  accelerators' sparse ports in core order, `[nb_tcdm_ports, 1]` for one
  without a config, as snaxgen does, and passes them to the crossbar only
  for `sparse`, so the plain target's configuration is as before. A row in
  `UPSTREAM.md`.
- `tests/snax/regress.py`: each SNAX ELF runs on `SNAX_TARGETS`
  (`snax_alu`, `snax_alu_sparse`), named `<program>.<target>`; `-k` selects
  by that name. CI builds `snitch;snax_alu;snax_alu_sparse`; the Makefile's
  comment says so. README: the layout, "The snax_alu targets" (build,
  the sparse target, `!` in the crossbar's trace), "Regression", "Continuous
  integration" and "Comparing with the RTL" (one checkout per
  configuration, the commands for the sparse one, the target to run
  against each).
- In snax-forge's image: `make build TARGETS="snitch;snax_alu;snax_alu_sparse"`,
  then `make regress`: `regression passed`, 28 SNAX runs and 17 plain, 1 min
  28 s. The 14 `.snax_alu` and 17 plain `run.log` files equal main's
  (step 4's baseline), and so do the plain target's traces but for their
  time-0 configuration lines. The CI workflow parses (`yaml.safe_load`, one
  job, 8 steps); it was not run on GitHub (nothing is pushed). The
  `.snax_alu_sparse` logs were not read before step 8's predictions.

### SG7 step 8: predictions

- 2026-10-15. Predictions for `stream-timing`, `alu-timing` and
  `snax-alu` on the sparse RTL and the sparse target are in `SG7.md`,
  "Predictions", written before any sparse RTL run and committed before any
  run of the new cases. The sparse target's `run.log` files of step 7's
  regression were not read before.
- How: the rules of `SG7.md` worked through each case's requests. For the
  cases with contention, a throwaway Python restatement of the streamer,
  the ALU, `rr_arb_tree` and the sparse rule (`build/sg7/predict.py`, not
  committed; it reads no C++). Run with the plain rule at the plain
  target's start cycles it gave every grant of the plain target's traces
  (cycle, bank and winner): all 1212 of `alu-timing`, all of the five
  `stream-timing` cases and of `snax-alu` at the five sizes, and every
  counter. Then with the sparse rule. The compared counters stay as they
  are when either start write moves by up to 3 cycles.
- Expected: every compared counter as on the plain RTL but `out_one_bank`'s
  982, 74 against 72, a priority effect (a writer lane with 7 or 8 queued
  wins repeatedly on bank 0, so the ALU fires in bursts of three).
  Non-compared: `stream_first`'s 977 and `snax-alu`'s at 100 one lower (the
  pointer rule gives the writer the second conflict on banks 8 to 11).
  Grants change without a counter effect in `snax-alu` at 128 to 4096 (idle
  restart) and, on the plain RTL against the plain target, in
  `ab_same_banks` (the cores' stores leave `rr_q` 12 in the RTL's plain
  interconnect, where the model has no cores).
- Two new `stream-timing` cases, a first run then the measured run, with
  only CSR instructions between the two start writes (checked in the
  disassembly of both ELFs): `prio_queued` (B with an empty queue against A
  with 4 queued: priority) and `idle_restart` (A against B after B's first
  run on the same banks: the sparse pointer restarts). Predicted 5 on the
  plain RTL and target, 6 on the sparse ones; first runs 5 and 2. The
  program sets up each run in `stream()`; the old five cases keep their
  output line and are otherwise unchanged but for the writer's unused
  pointer, now at +3 KiB. `Makefile` and `regress.py` list the seven
  cases; the app's README has them with both interconnects' counters.
- Built in snax-forge's image (`make -C sw/apps/stream-timing`), not run
  before this commit.

### SG7 step 9: runs and comparison

- 2026-10-15. The same 13 ELFs everywhere (`snax-alu` at five sizes,
  `alu-timing`, seven `stream-timing` cases), built from `sw/` in
  snax-forge's image; their sha256 were taken before the RTL runs and
  checked after.
- SNAX-GVSoC: each ELF on `snax_alu` and `snax_alu_sparse`, with both cores'
  instruction traces and the crossbar, streamer and ALU traces; `snax-alu`
  cut with `phases.py --gvsoc`.
- Sparse RTL, `../snax_cluster` at `9fbf35d` with step 2's `rtl-gen`
  (`generated/SparseInterconnect.sv` still step 2's): `make -C
  target/snitch_cluster vsim_preparation CFG_OVERRIDE=cfg/snax_alu_cluster.hjson`
  in `d3d8f5572ff4`, then `make -C target/snitch_cluster
  bin/snitch_cluster.vsim CFG_OVERRIDE=cfg/snax_alu_cluster.hjson` on the
  host, Questa 2022.4: 755 modules, 0 errors, `TARGET_SPARSE_INTERCONNECT`
  defined. Each ELF run from `target/snitch_cluster`, its `logs/` kept as
  `logs-sparse-<program>`; all 13 end `[SUCCESS]`; 3 min 4 s in all.
  `snax-alu` cut with `phases.py --rtl`.
- Plain RTL for the new cases: `../snax_cluster_plain`, cloned at `9fbf35d`
  with its submodules; `rtl-gen` and `vsim_preparation` with
  `cfg/snax_alu_cluster_old.hjson` in `d3d8f5572ff4`, the binary on the
  host (750 modules, as in SG6, 0 errors); `prio_queued` and
  `idle_restart` only, both `[SUCCESS]`.

`stream-timing`, counter 977 (plain RTL: SG3 step 4 for the first five, this
step for the two new ones):

| Case | Plain RTL | Sparse RTL | Sparse SNAX-GVSoC | Plain SNAX-GVSoC | Prediction |
|---|---|---|---|---|---|
| `zero_bound` | 0 | 0 | 0 | 0 | held |
| `a_alone` | 9 | 9 | 9 | 9 | held |
| `ab_other_banks` | 9 | 9 | 9 | 9 | held |
| `ab_same_banks` | 10 | 10 | 10 | 10 | held (the plain RTL's winner not observed) |
| `a_stride0` | 12 | 12 | 12 | 12 | held |
| `prio_queued` (first run) | 5 (5) | 6 (5) | 6 (5) | 5 (5) | held |
| `idle_restart` (first run) | 5 (2) | 6 (2) | 6 (2) | 5 (2) | held |

`alu-timing`, 977 and 982 (plain RTL: SG4 step 5, Verilator at `b2672f8`;
compared counter in bold), errors 0 on every side:

| Case | Plain RTL | Sparse RTL | Sparse SNAX-GVSoC | Plain SNAX-GVSoC | Prediction |
|---|---|---|---|---|---|
| `alu_first` | **29**, 32 | **29**, 32 | **29**, 34 | **29**, 34 | held |
| `stream_first` | 132, **25** | 131, **25** | 131, **25** | 132, **25** | held, 977 one lower too |
| `out_one_bank` | 210, **72** | 210, **74** | 209, **74** | 209, **72** | held, 977 as plain on each side |
| `len1` | **5**, **1** | **5**, **1** | **5**, **1** | **5**, **1** | held |
| `restart_idle` | **29**, 32 | **29**, 32 | **29**, 34 | **29**, 34 | held |

`snax-alu`, `Accelerator Cycles` and errors: 1, 25, 32, 256, 1024 and 0 on
all four sides (plain RTL: SG5's references). Phases (plain RTL: SG5's
`tests/snax/snax-alu/rtl/<N>.json`, removed in SG6, read from git at
`44453a3`; SG6's run at the pin reproduced them): on the sparse RTL every
phase equals that reference at every size; on the sparse target every
phase equals the plain target's. Prediction held (C4 at 100 did not end a
poll earlier: 5 on both RTLs, 6 on both targets). The RTL against the
model, sparse, the growing phases (as SG5's "Result"):

| Phase | 128 | 1024 | 4096 |
|---|---|---|---|
| C1 barrier | 147 / 154 | 373 / 381 | 1153 / 1169 |
| D2 DMA wait | 45 / 36 | 270 / 262 | 1050 / 1050 |
| C3 ALU poll | 37 / 39 | 262 / 261 | 1032 / 1029 |
| C5 check loop | 5795 / 5698 | 46115 / 45244 | 184355 / 180754 |
| Total up to 982 | 6713 / 6698 | 47495 / 46696 | 187285 / 183755 |

- Gaps. None new: every compared counter is equal on the sparse RTL and
  the sparse target, and the sparse interconnect changes no phase on
  either side. What differs is what differed before, the core's timing:
  the start gap (`alu-timing` -5 against -7, `out_one_bank` 104 against
  103), so the gap-dependent counters (982 with the ALU first: 32 against
  34; `out_one_bank`'s 977: 210 against 209); `polls` and `mcycle`; and
  SG5's phase gaps (C0, C2a, C6, C7, D1 to D3: open items 65 to 67).
- Not verified: grants on the RTL one by one (no grant trace was taken),
  so the plain RTL's other winner in `ab_same_banks` (its `rr_q` left at
  12 by the core's stores) is still a prediction, and so is the order on
  the RTL in `out_one_bank` beyond its counter; the writer's priority bit
  against the RTL's signal (only through the counters); the lock and the
  granularity warning in GVSoC (only the winner check exercises the lock,
  against the RTL module); the plain RTL's `alu-timing` and first five
  `stream-timing` cases at this pin with these ELFs (SG3's and SG4's values
  used); the CI workflow on GitHub (nothing pushed).

### SG7 round 3, step 2: the crossbar, holding inputs and sub-word accesses

- 2026-10-15. `git pull` on main in snax-gvsoc and snax-forge (nothing new;
  main has no commit the branch lacks), `ry/sg7-sparse` checked out and
  pulled. Round 3's plan is in `SG7.md`, "Round 3".
- `snax/snax_tcdm_xbar.{cpp,py}`:
  - Property `holds`, per input (False when not given; its length is
    checked). An input that holds keeps a losing request, with its priority
    bit, for the next cycle's arbitration; while one is held, `held_event`
    at the start of the next cycle queues that cycle's arbitration behind
    the events already queued (an arbitration queued directly for the next
    cycle could come before a streamer's step of that cycle). A request
    arriving after its cycle's arbitration is fatal (it would be arbitrated
    twice in one cycle).
  - The response carries the latency the request brings (a core's router)
    on top of the bank's: due one cycle after the grant plus both; a write
    on an input that holds is answered at its grant. Every response is sent
    with no latency in the request (`prepare()`): its cycle holds it all.
  - Accesses of 1, 2, 4 or 8 bytes inside one bank word, at the bank-local
    address with the byte offset (as before); one that crosses a word is
    refused with a warning naming the input. AMOs and LR/SC go to the bank
    as they come, as on the L1 path; the trace says `amo` for them and
    gives the size of an access smaller than a word, so a full-word read or
    write prints as before.
  - `grant()` is sent at the grant, as before. A router forwards a request
    (`req_forward`), so the grant goes to the master that sent it; for a
    core that is `Lsu::data_grant`, which acts only with
    `CONFIG_GVSOC_ISS_LSU_NB_OUTSTANDING` (unset for Snitch,
    `nb_outstanding` 1): a no-op. The routers on the way have no grant
    callback of their own; `io.hpp`'s default does nothing. Read, not run.
- Nothing wired yet: no input holds. Baseline at the branch's head (round 1)
  and after the change, each with `make build
  TARGETS="snitch;snax_alu;snax_alu_sparse"`, `make regress` and every SNAX
  program traced on both targets (`snax_xbar`, `streamer`) in snax-forge's
  image: `regression passed` both times (32 SNAX runs, 17 plain); all 49
  `run.log` files byte-identical; the 64 traces and 32 outputs equal but for
  the port pointers in the time-0 lines.
- Not exercised by this step: holding, the write answered at its grant, the
  carried latency and sub-word accesses (no master uses them before step 3).

### SG7 round 3, step 3: the cores and AXI into the crossbar

- 2026-10-15. `snitch_cluster.py`, only for a cluster with SNAX ports: the
  crossbar's inputs are the SNAX ports, then `core0`, `core1` (each core's
  TCDM and `tcdm_alias` maps in `pe<i>_ico`, keeping `core_latency['tcdm']`),
  then `axi` (`narrow_axi`'s TCDM map, straight to the crossbar at TCDM
  offsets instead of through `pe0_ico`). These three hold a losing request;
  their priority wires are bound to nothing, so they ask with 0. The plain
  crossbar has 15 inputs as the RTL; the sparse config is `[[12, 1], [1, 1],
  [1, 1], [1, 1]]`, snaxgen's. The `snitch` target builds as before (no SNAX
  ports). `snax_alu.py`, `snax_alu_sparse.py`, the crossbar's docstring,
  `ClusterArch`'s comment and the README say so; a row in `UPSTREAM.md`.
- In snax-forge's image: `make build TARGETS="snitch;snax_alu;snax_alu_sparse"`,
  `make regress`: `regression passed` (32 SNAX runs, 17 plain); no warning
  in any `run.log`. Against step 2, every `run.log` is equal but
  `dma-timing`'s on both targets, whose `l2l1 4x800` line goes from done 82,
  busy 66 to done 96, busy 81 (RTL 84 for done, SG5).
- That line, traced on `snax_alu` (`idma`, `wide_axi`, `narrow_axi`, the
  DRAM, the I-cache), with and without this step's wiring on the same
  build (the installed `snitch_cluster.py` swapped): no core touches the
  banks during the four copies. The DMA core reaches the second run's first
  copy at 227988 instead of 228013, 25 cycles earlier (its loads and stores
  now take the crossbar's timing), and the copies now overlap GVSoC's HTIF
  poll of `tohost`: every 1000 cycles (at ...001) the core's HTIF model reads
  `tohost` byte by byte through the core's data port and `narrow_axi` into
  the DRAM. At 228001 it delays the third copy's DRAM read from 15 to 30
  cycles. A GVSoC artefact of the host model, not of the crossbar; the RTL
  has no such poll. Not changed here.
- `dma-timing` on `snax_alu`, crossbar traced: 3516 grants to `core0` and
  18833 to `core1`, reads and writes of 1 and 4 bytes; a core's request held
  behind the other's twice; no AMO in L1 and no access on `axi` (nothing in
  these programs sends into the cluster's narrow AXI port).

### SG7 round 3, step 4: D125 fitted again

- 2026-10-15. `snax-alu` at the five sizes on both targets with step 3's
  build, `core_latency` unchanged (`tcdm` 2, `narrow` 6), both cores traced,
  phases with `phases.py --gvsoc` and the check loop with `--show 'C5 check
  loop'`; the crossbar traced for one run (`snax_alu`, 100).
- L1 load to the next load, in the check loop at 100 (`lw a4, 4(s0)` on L1,
  then `lw a5, 4(a2)` on DRAM): the L1 load granted on bank 10 at 2892,
  answered at 2895 (one cycle after the grant plus 2), the DRAM load issued
  at 2896: 4, the RTL's. Before round 3: 4 too (2874 to 2878). So `tcdm`
  stays 2; the expected 1 did not hold. The crossbar's cycle took the place
  of the cycle the LSU adds to a synchronous answer (`latency + 1`), and the
  core goes on in the cycle after the response, as it issued the next load
  in the cycle after `load_ready_cycle` before. DRAM load to load: 14, as
  before. The listing stamps a load answered after its grant at the
  response, so its wait shows on the instruction before it (`bne` +4).
- What changed: the core waits for an L1 load's data (`IO_REQ_PENDING`),
  where it went on before and only the register waited. In the check loop
  the 11 instructions after the second L1 load (`lw a7, 0(s0)`), of which
  only one uses it, now start after its data: 47 cycles per element against
  44 (RTL 45), in 3999 of 4096 iterations at 4096 (round 1: 44 in 4034).
  The other iterations take 53 to 65 cycles (96 of them; round 1, 51 to 59,
  61 of them); not looked into.
- `Accelerator Cycles` and errors: 1, 25, 32, 256, 1024 and 0 on both
  targets. Both targets give the same phases at every size. Phases, RTL
  (SG5's plain reference, which the sparse RTL equals at every phase,
  round 1) / round 1 / now; the growing phases, the target's tier 2:

  | Phase | 128 | 1024 | 4096 |
  |---|---|---|---|
  | C1 barrier | 147 / 154 / 157 (+7%) | 373 / 381 / 384 (+3%) | 1153 / 1169 / 1174 (+2%) |
  | D2 DMA wait | 45 / 36 / 36 (-20%, accepted in SG5) | 270 / 262 / 262 (-3%) | 1050 / 1050 / 1052 (0%) |
  | C3 ALU poll | 37 / 39 / 39 (+5%) | 262 / 261 / 261 (0%) | 1032 / 1029 / 1029 (0%) |
  | C5 check loop | 5795 / 5698 / 6098 (+5%) | 46115 / 45244 / 48446 (+5%) | 184355 / 180754 / 193543 (+5%) |
  | Total up to 982 | 6713 / 6698 / 7093 (+6%) | 47495 / 46696 / 49916 (+5%) | 187285 / 183755 / 196571 (+5%) |

  Tiers 1 and 2 hold. Every change against round 1, the same on both
  targets:
  - C5: 3 cycles per element (the blocking L1 load), plus 15, 16, 130 and
    501 at 100, 128, 1024 and 4096 in the slower iterations; +12 at 4.
  - C1 +3 (+5 at 4096) and D1 +3: likely the cores' blocking L1 loads
    before the barrier and in the DMA issue (stack and TLS are in L1); not
    traced.
  - C0 and D0: +3, +6, -8, +15, +22 at 4, 100, 128, 1024, 4096: likely
    boot's L1 loads, and where the I-cache misses fall; not traced.
  - C6: +992, +1683, +612, +787, +191: likely `printf`'s L1 loads, then the
    host's answers on their grid of about 1000 cycles (tier 3); not traced.
  - D2 +2 at 4096; D4 holds C2 to C7 of hart 0.
  - C2a, C2b, C3, C4, C7, D3: unchanged.
  Tier 3 (fixed costs, every phase at 4 and 100) is explained as SG5 did,
  with C5's and C6's growth above.
- `snax_alu.py`'s comment on `CORE_LATENCY` says why 2 still gives 4.

### SG7 round 3, step 5: core-tcdm and its predictions

- 2026-10-15. `sw/apps/core-tcdm` (README there): one ELF per case,
  `subword`, `core_vs_reader`, `after_stores`, on `common.mk`; in
  `regress.py` on both SNAX targets (`subword` returns its error count, the
  other two 0); the README's regression paragraph says so.
- The ELFs' disassembly, built in snax-forge's image: no FP instruction in
  `main`. `subword` uses `sb`, `sh`, `sw`, `lbu`, `lhu`, `lw`, one
  `amoadd.w` and `lr.w` then `sc.w`; the compiler reads the signed byte and
  half with `lbu` and `lhu`, so `lb` and `lh` are not exercised; the
  doubleword is two `sw` and two `lw`. In the two streamer cases the area's
  stores (`sw` pairs, 8 KiB) end with a `fence`, then only CSR
  instructions up to the start write; `core_vs_reader` has `csrw 975`,
  `lw` on bank 16, `lw` on bank 0, in that order.
- Predictions in `SG7.md`, "Predictions of round 3", from source before any
  run of `core-tcdm` (none on SNAX-GVSoC either), with a throwaway
  predictor (`build/sg7/r3/predict3.py`: round 1's plus a core at input 12,
  priority 0, holding, the next L1 load 4 cycles after the previous grant).
  It gives round 1's counters without the core, with 15 inputs as with 12;
  the existing programs' compared counters do not move with the plain
  pointer at 0, 12 or 13. `core_vs_reader` was laid out with it so its
  counter holds for any core offset from 0 to 6 cycles (a first load on
  another bank keeps the core's bank-0 load after the readers' first
  requests; without it a load arriving at s + 2 wins there on the plain
  interconnect and moves the counter).
- On the sparse RTL `subword` is predicted to fail its SC: the sparse
  wrapper does not drive the memory side's user field, so the AMO shim's
  `core_id` is unknown. A prediction from source only.

### SG7 round 3, step 6: runs and comparison

- 2026-10-15. The same 16 ELFs everywhere: `snax-alu` at 4, 100, 128, 1024,
  4096, `alu-timing`, the seven `stream-timing` cases (these 13 are round
  1's, sha256 unchanged) and the three `core-tcdm` cases, built in
  snax-forge's image; their sha256 (`build/sg7/r3/elfs.sha256`) checked
  again after all runs.
- SNAX-GVSoC, step 3's build (step 5 changed no model code): each ELF on
  `snax_alu` and `snax_alu_sparse`, both cores, the crossbar, the streamer
  and the ALU traced, all exit 0; `snax-alu` cut with `phases.py --gvsoc`
  (every phase equal to step 4's on both targets). Then `make regress`:
  `regression passed`, 38 SNAX runs and 17 plain.
- The RTL, round 1's builds at `9fbf35d` (no rebuild needed): the plain one
  in `../snax_cluster_plain` (`cfg/snax_alu_cluster_old.hjson`), the sparse
  one in `../snax_cluster` (`cfg/snax_alu_cluster.hjson`),
  `bin/snitch_cluster.vsim` on the host, Questa 2022.4, each ELF from
  `target/snitch_cluster`, `logs/` kept as `logs-r3-<plain|sparse>-<program>`;
  3 min 21 s and 3 min 38 s. Every run `[SUCCESS]` but `core-tcdm-subword` on
  the sparse RTL, `[FAILURE]` with exit code 2, as predicted. `snax-alu` cut
  with `phases.py --rtl`. This replaces round 1's borrowed plain RTL values
  (SG3's `stream-timing`, SG4's `alu-timing` at `b2672f8`) with runs at the
  pin: every one of them is the same.
- The plain RTL's grants, without editing RTL: the vsim wrapper already runs
  `log -r /*`, so after a run `vsim -view` on `vsim.wlf` with a list of the
  interconnect's `req_q_valid_flat`, `rsp_q_ready_flat` and `bank_select`
  (binary radix, one row per clock edge) gives each input's request and
  grant per bank and cycle (`build/sg7/r3/wlf/`, not committed). Kept for
  `stream-timing-ab_same_banks` and the three `core-tcdm` cases.

`stream-timing`, counter 977 (first run in brackets):

| Case | Plain RTL | Plain target | Sparse RTL | Sparse target | Prediction |
|---|---|---|---|---|---|
| `zero_bound` | 0 | 0 | 0 | 0 | held |
| `a_alone` | 9 | 9 | 9 | 9 | held |
| `ab_other_banks` | 9 | 9 | 9 | 9 | held |
| `ab_same_banks` | 10 | 10 | 10 | 10 | held; plain grants below |
| `a_stride0` | 12 | 12 | 12 | 12 | held |
| `prio_queued` | 5 (5) | 5 (5) | 6 (5) | 6 (5) | held |
| `idle_restart` | 5 (2) | 5 (2) | 6 (2) | 6 (2) | held |

`alu-timing`, 977, 982 and the start gap (compared counter in bold), errors
0 on every side:

| Case | Plain RTL | Plain target | Sparse RTL | Sparse target | Prediction |
|---|---|---|---|---|---|
| `alu_first` | **29**, 32, -5 | **29**, 34, -7 | **29**, 32, -5 | **29**, 34, -7 | held |
| `stream_first` | 132, **25**, 103 | 132, **25**, 103 | 131, **25**, 103 | 131, **25**, 103 | held |
| `out_one_bank` | 210, **72**, 104 | 209, **72**, 103 | 210, **74**, 104 | 209, **74**, 103 | held |
| `len1` | **5**, **1**, -5 | **5**, **1**, -7 | **5**, **1**, -5 | **5**, **1**, -7 | held |
| `restart_idle` | **29**, 32, -5 | **29**, 34, -7 | **29**, 32, -5 | **29**, 34, -7 | held |

`snax-alu`: `Accelerator Cycles` 1, 25, 32, 256, 1024 and 0 errors on all
four sides. Phases: the plain RTL's equal SG5's reference at every size and
phase, the sparse RTL's equal round 1's; on the targets, step 4's table
(tiers 1 and 2 held, C5 +5% from the blocking L1 loads). Prediction held.

`core-tcdm`:

| Case | Compare | Plain RTL | Plain target | Sparse RTL | Sparse target | Prediction |
|---|---|---|---|---|---|---|
| `subword` | errors, `sc` | 0, 0 | 0, 0 | 2, 1 | 0, 0 | held on all four |
| `core_vs_reader` | 977 | 18 | 17 | 17 | 17 | held but on the plain target (18 predicted) |
| `after_stores` | 977 | 5 | 5 | 6 | 6 | held |

- The plain RTL's grants. `ab_same_banks`: core 0's stores are the last
  accesses to banks 0 to 3; at the readers' first requests B wins on all
  four, then A. Round 1's open prediction (B first, from `rr_q` 12) held;
  the plain target now does the same (its trace: `reader1.laneN` first),
  where round 1's gave A. `after_stores`: the same, B first on banks 0 to 3,
  hence 5. `core_vs_reader`: the core's load on bank 16 granted at s + 1,
  its load on bank 0 asks from s + 5 and is granted at s + 11 after the
  eight lanes' first requests, as predicted.
- The sparse RTL's SC, in its waveform: at the `lr.w` and the `sc.w` the
  AMO shim of bank 5 sees `core_id` X and `is_core` 0 (`is_core` is a `bit`,
  so undriven reads 0); on the plain RTL, core 0 and 1. The SC returns 1
  and does not write. Every other access of `subword`, the `amoadd.w`
  included, is right on all four sides.
- In the existing programs the cores' accesses meet no streamer request on
  either target (no grant in any trace with a core and a streamer channel
  on one bank but in `core_vs_reader`); the two cores meet each other once
  or twice in boot. Prediction held.

Gaps, named, not fixed:

- `core_vs_reader` on the plain target, 17 against the plain RTL's 18. On
  SNAX-GVSoC the core's load on bank 16 is granted 10 cycles after the
  start write (RTL: 1): the instruction line holding the start write and
  the loads (0x800002a0) misses in GVSoC's I-cache, about 10 cycles, as
  each new 32 B line of the CSR setup does; snax_cluster's L0 prefetches it
  (open item 65). So the core's bank-0 load asks at s + 14, behind four
  lanes still to go in the round, and is granted at s + 18, after the
  readers: no cycle taken from them. The case was laid out for the core
  asking 4 to 10 cycles after the start write; its counter depends on the
  core's fetch timing beyond that, so it does not meet D123 as it stands. A
  layout that keeps the start write and the loads in a line the core
  fetched before the start would remove it (not done: the case and its
  prediction stay as committed). On the sparse sides the core waits for the
  priority-1 readers either way (17 on both).
- `subword` on the sparse RTL, 2 errors and `sc` 1 against 0 and 0 on the
  sparse target: snax_cluster's sparse wrapper
  (`sparse_interconnect_wrapper.sv.tpl`, "user signal not used") does not
  drive the memory side's user field, so no LR/SC pair can succeed on the
  sparse RTL. An RTL issue, not the model's; SNAX-GVSoC follows the plain
  RTL (the reservation kept by hart).
- As before, the core's own timing: start gaps (-5 against -7, 104 against
  103), so `alu-timing`'s gap-dependent counters (982 with the ALU first, 32
  against 34; `out_one_bank`'s 977, 210 against 209), `polls` and `mcycle`;
  SG5's phase gaps (open items 65 to 67); and now C5's +5% (step 4).
- Not observed: the sparse RTL's grants one by one (its interconnect is the
  Chisel module; the list above reads `snitch_tcdm_interconnect`'s signals,
  so only the plain RTL's were read); `axi` (input 14) on any side, as no
  program here sends into the cluster's narrow AXI port; core 1 against a
  streamer channel.

### SG7 round 3b, step 1: the plan

- 2026-10-16. `git pull` on main in snax-gvsoc and snax-forge (nothing new;
  main has no commit the branch lacks), `ry/sg7-sparse` checked out and
  pulled. Round 3b's plan is in `SG7.md`, "Round 3b".
- `subword` on the sparse RTL: noted in `SG7.md` and in
  `sw/apps/core-tcdm/README.md` as snax_cluster's (the sparse wrapper leaves
  the AMO shim's `core_id` and `is_core` undriven); SNAX-GVSoC keeps a
  reservation per hart, as the plain RTL. No code change.

### SG7 round 3b, step 2: the core goes on after a pending L1 load

- 2026-10-16. What the ISS has, read before the change:
  - `CONFIG_GVSOC_ISS_LSU_NB_OUTSTANDING` (set only for `nb_outstanding` > 1;
    Snitch has 1): a pool of requests, a load's register invalidated
    (`scoreboard_reg_invalidate`, -1) until its response. Not used: it is a
    compile-time path that also makes stores and AMOs non-blocking, and its
    `data_grant` lowers the core's stall count on every grant, which the
    crossbar sends for every request.
  - The -1 timestamp stalls an instruction only through
    `CONFIG_GVSOC_ISS_EXEC_SCOREBOARD`'s check in `exec_inorder.cpp`, which
    only `SnitchFast` is built with; Snitch's `scoreboard_reg_check` treats
    -1 as ready.
  - The Snitch core's own scoreboard, `scoreboard_reg_valid` in
    `SnitchRegfile`: `int_offload_exec` (`src/snitch/decode.cpp`) runs before
    every integer instruction and holds it while an input or output register
    is not valid; today the FP subsystem's results use it. Used: it is the
    RTL scoreboard's place in this ISS, and it is runtime.
- The change (`lsu.hpp`, `lsu_implem.hpp`, `lsu.cpp`, `snitch/decode.cpp`),
  compiled for the Snitch core with its scoreboard and without
  `NB_OUTSTANDING`, active only with `int_loads_in_flight` set (the SNAX
  targets; 0 on `snitch`):
  - A load answered `IO_REQ_PENDING` sets `load_pending` and its register
    not valid; the core goes on.
  - `wait_for_load()`: while a load is pending, the next load, store or AMO,
    and (from `int_offload_exec`) an instruction that reads or writes its
    register stall the core until the response, then run in the cycle
    after. Stall cycles the core already has (a fetch) go first; without
    that, a fetch's cycles were counted again after the wait (seen: a
    dependent load on a new I-cache line 3 cycles after the response, not
    1). `int_offload_exec` does not look at a load's or store's base
    register (an indirect argument); the LSU's wait covers it.
  - The response (`pending_load_response`): sign extension, the register
    valid, its scoreboard time and `load_ready_cycle` the cycle after the
    response, as a load answered at once with latency. A load that would
    run in the response's own cycle (the response's event came first) runs
    again in the next.
  - Stores, AMOs and LR/SC are answered as before (the core waits). The LSU
    keeps its one request (`io_req`), so a store or AMO after a pending load
    waits for the load's data: as in round 3, where the load blocked; the
    RTL can send it (`num_int_outstanding_mem` 4). Not in the measured loops.
- In snax-forge's image: `make build TARGETS="snitch;snax_alu;snax_alu_sparse"`;
  `snax-alu` at five sizes on both targets with both cores traced, phases
  and the C5 listing (`build/sg7/r3/snaxalu.sh`); `snax_alu` at 100 with
  core 0's LSU, the crossbar and core 0's instructions traced at trace
  level.
- Load to load, check loop at 100: `lw a4, 4(s0)` granted on bank 13 at
  3009, answered at 3012, the DRAM load `lw a5, 4(a2)` issued at 3013: L1 4,
  the RTL's. DRAM to the next load 14, as before. So `tcdm` stays 2. An
  instruction on the loaded register runs the cycle after the response,
  4 after the grant (e.g. `jalr` on `lw ra` at +4), as before round 3.
- C5: 44 cycles per element in 4034 of 4096 iterations at 4096 (round 1: 44
  in 4034; round 3: 47 in 3999; RTL 45); the others 47, 48, 56, 60. Errors 0,
  `Accelerator Cycles` 1, 25, 32, 256, 1024 on both targets, which give the
  same phases at every size. Phases, RTL (SG5) / round 1 / round 3 / now,
  growing phases:

  | Phase | 128 | 1024 | 4096 |
  |---|---|---|---|
  | C1 barrier | 147 / 154 / 157 / 154 (+5%) | 373 / 381 / 384 / 381 (+2%) | 1153 / 1169 / 1174 / 1169 (+1%) |
  | D2 DMA wait | 45 / 36 / 36 / 36 (-20%, accepted in SG5) | 270 / 262 / 262 / 262 (-3%) | 1050 / 1050 / 1052 / 1050 (0%) |
  | C3 ALU poll | 37 / 39 / 39 / 39 (+5%) | 262 / 261 / 261 / 261 (0%) | 1032 / 1029 / 1029 / 1029 (0%) |
  | C5 check loop | 5795 / 5698 / 6098 / 5689 (-2%) | 46115 / 45244 / 48446 / 45226 (-2%) | 184355 / 180754 / 193543 / 180754 (-2%) |
  | Total up to 982 | 6713 / 6698 / 7093 / 6674 (-1%) | 47495 / 46696 / 49916 / 46678 (-2%) | 187285 / 183755 / 196571 / 183755 (-2%) |

  Round 3's changes are gone: at 4096 every phase is round 1's again; C1,
  D1, D2 and C0 / D0 at 4, 100, 1024, 4096 too. What is left against round
  1, both targets: C5 -1, -9, -18 at 100, 128, 1024 (fewer slow
  iterations); C6 +1, -2, +24, +18 at 4, 100, 128, 1024 and D4 with it; C0
  and D0 -15 at 128. Where I-cache misses and the host's answers to
  `printf` fall; not traced.
- `make regress`: `regression passed`. The 17 plain tests' `run.log` files
  are byte-identical to round 3's (step 6). Of the SNAX ones, all equal but
  `dma-timing`'s `l2l1 4x800` (done 96, busy 81 to 80, 65 on both targets:
  the core reaches the copies at other cycles of GVSoC's `tohost` poll,
  step 3) and `core_vs_reader`'s `polls` (0 to 1; its counter stays 17).
- Gaps, named, not fixed:
  - A load that waits for a DRAM load's data (D125's wait, stall cycles
    counted at once) sends its request at the start of the wait, so an L1
    load after a DRAM load reaches the crossbar up to 13 cycles early (seen
    in boot, held one cycle behind core 1). The core's timing is right; only
    the crossbar sees the request early. So it was before this step. No
    streamer request meets it in these programs.
  - The instruction trace prints a pending load's register before its data
    (the bank is read at the grant, later in the cycle).

### SG7 round 3b, step 3: GVSoC's tohost poll

- 2026-10-16. Read: `Htif::htif_handler` (`htif.cpp`) reads `tohost` every
  1000 cycles with `Syscalls::user_access`, one byte per request with the
  debug flag, on the core's data port; there it goes through `pe<i>_ico`,
  the cluster's and the SoC's `narrow_axi`, `wide_axi` and the DRAM. The
  DRAM model skips its bandwidth for a debug request; the routers do not:
  each byte moves their bandwidth stamps. Traced on `dma-timing`
  (`snax_alu`, the routers, DRAM, DMA and both LSUs): four pollers, the
  two integer cores and the two FP subsystems (`Snitch_fp_ss`, also built
  with `htif=True`, whose data port is the same `pe<i>_ico`), 359 poll
  requests in the run.
- GVSoC has a zero-time path for this: `vp/debug_mem.hpp`, the out-of-band
  debug access ("no timing, no simulation advance") that routers build into
  a flat map of the memories behind them and `Memory` serves from its
  storage. The poll now uses it when the core property `htif_poll_backdoor`
  is set: `Htif::poll_access` takes the component behind the core's data
  port (`get_final_ports`), here `pe<i>_ico`, and reads or clears `tohost`
  through its `debug_mem_access`. Same value, same period, same clear, so
  programs see the same. Set by `snax_alu.py`'s `SNAX_CORE`, so on both
  SNAX targets, and passed to the FP subsystems; `snitch` keeps the poll on
  the port. A syscall's own accesses (`dispatch`, `fromhost`) stay on the
  port: a syscall's buffers may be in L1, behind the SNAX crossbar, which
  has no backdoor. A failed backdoor access is fatal.
- After: no poll request on the port (the 46 accesses near `tohost` left
  are the program's own stores to it, one per `printf`, as on the RTL).
- `dma-timing`, both targets, before (step 2) and after: every line equal,
  and equal to SG2 step 7's on every line; `busy` equal to the RTL on every
  line, `done` 2 to 6 under it (SG5's core cost), `l2l1 4x800` done 80,
  busy 65 (RTL 84, 65; round 3 96, 81; SG5 82). After step 2 the poll no
  longer fell on a copy here; now no copy can meet it.
- `snax-alu`, both targets, the same phases on both. C6 before / after (RTL):
  7604 / 7605 (6899), 7029 / 7037 (7130), 7716 / 7719 (6855), 7015 / 7131
  (7075), 7715 / 7192 (7088) at 4, 100, 128, 1024, 4096: C6 still waits on
  the host's 1000-cycle grid (tier 3). The poll also cost core 0's own DRAM
  loads, which share `pe0_ico` with it, about every 1000 cycles: C5 now 44
  cycles per element in 4094 of 4096 iterations (one of 60), where step 2
  had 30 of 56 and 29 of 48. Those are round 3 step 4's slower iterations
  ("not looked into"): the poll. Other phases that moved: C5 -14, -6,
  -119, -479 at 100, 128, 1024, 4096; C0 and D0 -11, -4, -7, -7 at 4, 100,
  128, 1024 (boot's DRAM fetches and loads); C1 and D2 -8 at 4096; D4 with
  C2 to C7. Errors 0, `Accelerator Cycles` as before.
- `make regress`: `regression passed`; the 17 plain `run.log` files
  byte-identical to round 3's, every SNAX one equal to step 2's.

### SG7 round 3b, step 4: core_vs_reader

- 2026-10-16. The arbitration first, from round 3's traces (`build/sg7/r3`,
  the plain target's crossbar trace and the plain RTL's waveform list):
  - Plain target: start write at s = 7290; the core's bank-16 load granted
    at s + 10; its bank-0 load first asks at s + 14, behind reader0.lane3
    and reader1.lanes 1 to 3, and wins at s + 18. Each cycle the winner is
    the next requester above the last pick, the core (input 12) after the
    readers' inputs 3, 5, 6, 7.
  - Plain RTL: bank-16 load at s + 1; the bank-0 load asks from s + 5 (edge
    3 from the readers' first requests), wins at s + 11 after A3, B0 to B3,
    then A0's second beat: the same rule.
  - Up to the core's arrival the readers' grants are the same on both
    sides; with the RTL's arrival the plain target's rule gives the RTL's
    grants. So the arbitration is not the cause; the arrival is.
- The change (`sw/apps/core-tcdm/src/core-tcdm.c`): the start write and the
  two loads in `start_and_load`, not inlined, its block behind `.balign 32`
  (one line, 0x80000380 to 0x8000038c), returning the two words in a0 and
  a1; main configures and calls it twice, prints the measured run's counter
  and the first run's. The compiler unrolls the two runs, but the line is
  one copy. Between the runs core 0 makes no TCDM access (only CSRs; read in
  the disassembly). `after_stores` and `subword` ELFs unchanged (sha256).
- Prediction, before any run (in `SG7.md`; `build/sg7/r3b/predict3b.py`,
  round 3's predictor with the arbiters' state carried from the first run):
  measured 18 plain, 17 sparse on both sides; first run 18, 17, 17, 17.
- Runs: the new ELF (sha256 checked after the RTL runs) on `snax_alu` and
  `snax_alu_sparse` (this branch, steps 2 and 3 in) and on both RTLs, round
  1's builds at `9fbf35d`, Questa 2022.4, `[SUCCESS]` both, `logs/` kept as
  `logs-r3b-<plain|sparse>-core-tcdm-core_vs_reader`, the plain one's
  waveform read with round 3's list.

  | | Plain RTL | Plain target | Sparse RTL | Sparse target |
  |---|---|---|---|---|
  | 977, measured run | 18 | 18 | 18 | 18 |
  | 977, first run | 18 | 17 | 17 | 17 |

  `loaded 16 768` and `polls 0` on all four.
- Measured run, plain: the core's loads at s + 1 (bank 16) and s + 5 (bank
  0) on both sides, the bank-0 load granted at s + 11 on both, as
  predicted. The readers' order differs from the first grant: B3 first on
  the RTL, B0 on the target, each the rule's pick from the bank-0 pointer
  the first run left (7 on the RTL after B3; 12 on the target, whose core
  came last in its cold first run); the predictor's tree gives the same
  from 7 and 12. First run: the target's core at s + 10 and s + 14 as in
  round 3.
- Sparse, not held (17 predicted): in the measured run the readers ask with
  0. Each lane's queue still holds the first run's two words (the ALU is
  off, as in `stream-timing`'s `prio_queued`), so its count is at least 2;
  the core asks with 0 too, and the pick is round robin from the restarted
  pointer: the core at s + 10 on the target, 18. The predictor emptied the
  queues between the runs. The sparse RTL gives 18 too, so the model and
  the RTL agree; its grants are not read (Chisel module, no list).
- The four sides agree, so the layout stays. The cost: the compared counter
  no longer shows the core waiting behind priority-1 readers on the sparse
  interconnect; the first run still shows it (17 on both sparse sides) but
  is not compared, and on the plain sides it differs with the fetch (18
  against 17). Getting both in one compared run would need a second change
  (e.g. emptying the queues between runs); not done.

### SG7 round 3b, step 5: runs and comparison

- 2026-10-16. SNAX-GVSoC only, this branch with steps 2 to 4, in snax-forge's
  image: `make build TARGETS="snitch;snax_alu;snax_alu_sparse"`, then the 17
  ELFs (`snax-alu` at five sizes, `alu-timing`, the seven `stream-timing`
  cases, the three `core-tcdm` cases, `dma-timing`) on `snax_alu` and
  `snax_alu_sparse`, both cores, the crossbar, the streamer and the ALU
  traced (`build/sg7/r3b/gv/`), all exit 0; `snax-alu` cut with
  `phases.py --gvsoc`. The ELFs are round 3's (sha256 checked) but
  `core_vs_reader` (step 4). The RTL columns are round 3 step 6's runs at
  `9fbf35d`, `core_vs_reader`'s step 4's.

`stream-timing`, 977 (first run): RTL / round 3 / now, plain and sparse.
Equal everywhere, and `polls` and `mcycle` equal to round 3's on both
targets:

| Case | Plain | Sparse |
|---|---|---|
| `zero_bound` | 0 / 0 / 0 | 0 / 0 / 0 |
| `a_alone` | 9 / 9 / 9 | 9 / 9 / 9 |
| `ab_other_banks` | 9 / 9 / 9 | 9 / 9 / 9 |
| `ab_same_banks` | 10 / 10 / 10 | 10 / 10 / 10 |
| `a_stride0` | 12 / 12 / 12 | 12 / 12 / 12 |
| `prio_queued` | 5 (5) / 5 (5) / 5 (5) | 6 (5) / 6 (5) / 6 (5) |
| `idle_restart` | 5 (2) / 5 (2) / 5 (2) | 6 (2) / 6 (2) / 6 (2) |

`alu-timing`, 977, 982 and the start gap (compared counter in bold), RTL /
now; now equal to round 3 on both targets, errors 0 everywhere:

| Case | Plain | Sparse |
|---|---|---|
| `alu_first` | **29**, 32, -5 / **29**, 34, -7 | **29**, 32, -5 / **29**, 34, -7 |
| `stream_first` | 132, **25**, 103 / 132, **25**, 103 | 131, **25**, 103 / 131, **25**, 103 |
| `out_one_bank` | 210, **72**, 104 / 209, **72**, 103 | 210, **74**, 104 / 209, **74**, 103 |
| `len1` | **5**, **1**, -5 / **5**, **1**, -7 | **5**, **1**, -5 / **5**, **1**, -7 |
| `restart_idle` | **29**, 32, -5 / **29**, 34, -7 | **29**, 32, -5 / **29**, 34, -7 |

`snax-alu`: `Accelerator Cycles` 1, 25, 32, 256, 1024 and 0 errors on all
four sides. Phases, the same on both targets (and equal to step 3's), RTL
(SG5's reference, which both RTLs give) / round 3 / now:

| Phase | 128 | 1024 | 4096 |
|---|---|---|---|
| C1 barrier | 147 / 157 / 154 (+5%) | 373 / 384 / 381 (+2%) | 1153 / 1174 / 1161 (+1%) |
| D2 DMA wait | 45 / 36 / 36 (-20%, accepted in SG5) | 270 / 262 / 262 (-3%) | 1050 / 1052 / 1042 (-1%) |
| C3 ALU poll | 37 / 39 / 39 (+5%) | 262 / 261 / 261 (0%) | 1032 / 1029 / 1029 (0%) |
| C5 check loop | 5795 / 6098 / 5683 (-2%) | 46115 / 48446 / 45107 (-2%) | 184355 / 193543 / 180275 (-2%) |
| Total up to 982 | 6713 / 7093 / 6661 (-1%) | 47495 / 49916 / 46552 (-2%) | 187285 / 196571 / 183268 (-2%) |

Tiers 1 and 2 hold.

`core-tcdm`, RTL / round 3 / now:

| Case | Compare | Plain | Sparse |
|---|---|---|---|
| `subword` | errors, `sc` | 0, 0 / 0, 0 / 0, 0 | 2, 1 / 0, 0 / 0, 0 (the sparse RTL's wrapper) |
| `core_vs_reader` | 977 (first run) | 18 (18) / 17 / 18 (17) | 18 (17) / 17 / 18 (17) |
| `after_stores` | 977 | 5 / 5 / 5 | 6 / 6 / 6 |

`dma-timing`, done / busy, both targets the same; RTL SG2 step 3's: every
line as round 3 but `l2l1 4x800`, 96 / 81 to 80 / 65 (RTL 84 / 65), so every
line now equals SG2 step 7's; `busy` equal to the RTL on every line.

- Every compared counter matches: on the plain RTL and the plain target,
  and on the sparse RTL and the sparse target, but `subword` on the sparse
  RTL (snax_cluster's wrapper, step 1). `core_vs_reader` now matches on both
  (round 3: 17 on the plain target against 18).
- What depends on the core's timing and moved, all on both targets:
  - `snax-alu` phases against round 3: C5 -12, -330, -415, -3339, -13268 at
    4, 100, 128, 1024, 4096 (the core goes on after an L1 load, step 2: 3
    cycles per element; and the poll off `pe0_ico`, step 3: the slower
    iterations); C6 -990, -1677, -585, -653, -714 (C6 waits on the host's
    1000-cycle grid; it starts earlier); C0 and D0 -14, -10, -14, -22, -22
    and C1 -3, -3, -3, -3, -13, D1 -3 at every size (the cores' L1 loads in
    boot, the barrier and the DMA issue, step 2; the poll's DRAM reads in
    boot, step 3); D2 -10 at 4096 (step 3); D4 and the totals with them.
    C2a, C2b, C3, C4, C7, D3 unchanged.
  - `dma-timing`'s `l2l1 4x800`: 96 / 81 to 80 / 65 (step 2 moved the core
    against the poll, step 3 took the poll off the bus).
  - `core_vs_reader`'s first run 17 on both targets (round 3's single run;
    the line misses in the first run), the measured run 18 (step 4).
  - Unchanged: `stream-timing`'s `polls` and `mcycle`, `alu-timing`'s start
    gaps and non-compared counters, `after_stores`' and `subword`'s lines.
- `make regress`: `regression passed`, 38 SNAX runs and 17 plain; the 17
  plain `run.log` files byte-identical to round 3's; of the SNAX ones only
  `dma-timing`'s and `core_vs_reader`'s differ, as above.
- Not verified: the sparse RTL's grants in `core_vs_reader` (no list for the
  Chisel module); the RTL's priority bits in that case's measured run (the
  counter only); a store or AMO right after a pending load against the RTL
  (no program here does it in a measured window); the effect of the early
  crossbar request of an L1 load after a DRAM load (step 2) on any program
  with a streamer request in that window.

### SG7 round 4, step 1: the plan

- 2026-10-16. `git pull` on main in snax-gvsoc and snax-forge (nothing new;
  main has no commit the branch lacks), `ry/sg7-sparse` checked out and
  pulled. Round 4's plan is in `SG7.md`, "Round 4": the RTL's superbank mux
  and both interconnects' lock on a refusal, read at `9fbf35d` and common_cells
  v1.40.0; GVSoC's DMA path (`IDmaBeTcdm`, `DmaInterleaver`); the design, a
  `dma` port on the crossbar; the call order within a cycle.
- Read, not run: the DMA back-ends' enqueues (`idma_be_tcdm.cpp`,
  `idma_be_axi.cpp`, `idma_be.cpp`, `idma_me_2d.cpp`): all at delay 1 or
  more but `IDmaBeTcdm::read_line`'s `enqueue(latency)` with latency 0, for a
  read line whose destination is not ready; the event it queues sends a TCDM
  line only if a TCDM write chunk is pending, i.e. in an L1-to-L1 copy.
  The streamer's commit is queued with delay 0 after its requests and relies
  on running after the arbitration, so the arbitration cannot simply be
  moved to the end of the cycle.

### SG7 round 4, step 2: the plain path's lock

- 2026-10-16. The plain pick moves from `snax_tcdm_xbar.cpp` into
  `snax/snax_plain_arb.hpp` (`SnaxPlainArb`, one per bank), so the crossbar
  and the check run the same code, as the sparse pick in round 1. Added:
  `rr_arb_tree`'s `LockIn`. A winner the bank refuses (`refused()`, reached
  only through `bank_refuses()`) leaves `rr_q` where it is and locks the
  bank: in the next cycle it arbitrates the vector it arbitrated then, of
  which the inputs still asking (the RTL's `req_q`; equal to it while the
  masters hold their requests), which gives the same winner while that
  winner still asks; `granted()` then moves `rr_q` over that vector. A
  request that comes during the lock is not seen until the locked one is
  granted. Without a refusal the pick is round 3b's.
- The check, `tests/snax/plain_arb/` (README there): `rr_arb_tree.sv` at
  v1.40.0 (`1281545`, with `lzc.sv` and `cf_math_pkg.sv`) wrapped with
  `stream_xbar`'s parameters (`FairArb`, `LockIn`, `AxiVldRdy`, no external
  priority), against `SnaxPlainArb`, per cycle: `req_o` and `idx_o` against
  the model's pick, each requesting input's `gnt_o` against the model's.
  Inputs hold their requests until granted; new requests and `gnt_i` at
  random, in phases of 500 cycles. Verilator 5.024 in `d3d8f5572ff4`, with
  common_cells' assertions on (`lock` and `lock_req` compiled in, none
  fired). 100000 cycles, seeds 1 to 3, each with 0 differences:

  | Inputs | Selections (seed 1) | Contested | After a refusal | Of them with a request new in the lock |
  |---|---|---|---|---|
  | 15 (the targets') | 91149 | 84497 | 28762 | 5276 |
  | 12 | 88182 | 80075 | 31635 | 4978 |
  | 16 | 93158 | 86975 | 30920 | 5780 |
  | 5 | 75014 | 58130 | 25637 | 2911 |

- Broken copies (`build/sg7/r4/broken*/`, through `MODEL_DIR`), 15 inputs,
  20000 cycles: a refused winner losing its turn (`rr_q` moved, no lock),
  27128 differences, the first at cycle 11; the lock kept but new requests
  seen during it, 11605. Both exit 1.
- In snax-forge's image: `make build TARGETS="snitch;snax_alu;snax_alu_sparse"`,
  `make regress`: `regression passed`; every `run.log` byte-identical to
  round 3b step 5's. Nothing refuses yet.
