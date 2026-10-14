# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what was learned. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the programs and the RTL reference | `d7dd78967b86dae5c7d149f420dd69681714dac9` (2026-10-14): `b2672f8` plus the DMA wait in `snax-alu.c` (SG5 P2), the RTL unchanged; SG0 used `8ebd422`, SG1 to SG4 `b2672f8` |
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
