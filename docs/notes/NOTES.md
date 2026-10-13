# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what was learned. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the probe and the RTL reference | `8ebd42299c1db2ab26006f68f76896097b64b278` (2026-09-16) |

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
