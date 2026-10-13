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
- `snax-alu` uses both paths: 18 `csrw` and 2 `csrwi` (`csrrw`, `csrrwi`)
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
  one read only when `rd` is not `x0`. The other CSR instructions go through
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
  throwaway edit, every `csrw` was one write and the `csrr` reads returned
  the memory's contents, so the busy loop never ended (P5's stub answers
  0).
