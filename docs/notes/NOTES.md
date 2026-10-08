# SNAX-GVSoC notes

Working notes for the SNAX-GVSoC exploration (X1, D115 in snax-forge).
One entry per step: what was run, what came out, what was learned.

## Pins

| What | Commit | Date |
|---|---|---|
| `gvsoc/gvsoc` (submodule `gvsoc/`) | `93cedc4cb2970a28ff38aef4393d8d69eae503a4` | 2026-09-25 |
| `pulp-platform/snitch_cluster` (submodule `snitch_cluster/`) | `4652c6b05886757c5cbe3dfe77c196dcd71e08e7` | 2024-08-02 |

Toolchains, all prebuilt downloads (see `container/Dockerfile`):

| Tool | Version | Used for |
|---|---|---|
| RISC-V GCC | 14.2.0, riscv-gnu-toolchain release 2025.01.17 | GVSoC tutorial programs (rv64) |
| Snitch LLVM | 0.12.0 (clang 12.0.1), pulp-platform/llvm-project | snitch_cluster runtime and programs (rv32) |
| Bender | 0.27.1 | snitch_cluster header generation |

### Why this snitch_cluster commit

- GVSoC's `make snitch_cluster` clones a `gvsoc-ci` branch that no longer
  exists in pulp-platform/snitch_cluster, so there is no official pin.
- GVSoC's cluster peripheral register file
  (`pulp/pulp/snitch/snitch_cluster/snitch_cluster_peripheral_reg.hjson`) is
  byte-identical to snitch_cluster from `a5af779` (2023-09-15) up to, not
  including, `96e34a2` (2024-08-09). `4652c6b` is the last commit in that range.
- snitch_cluster `c7eb9c2` (2025-01-28, native bootrom) moves the peripherals
  up by 0x1000 and `CL_CLINT_SET` from 0x180 to 0x1a0. Programs built from
  that commit or later fail on GVSoC with
  `Accessing invalid register (offset: 0x11a0 ...)`. Reproduced with `c4861da`.

## Layout

```
snax-gvsoc/
  gvsoc/            submodule, pinned
  snitch_cluster/   submodule, pinned
  container/        Dockerfile and requirements.txt
  snax/             module root for the SNAX components (added when needed)
  tutorials/        working copies of the GVSoC tutorials (added in GVS1)
  sw/               C programs (GVS3)
  build/            GVSoC build, install and run output; not tracked
  docs/             notes (this file), plans, and one page per tutorial in
                    docs/tutorials/
```

SNAX models stay outside the GVSoC tree. GVSoC picks up an external module
root with `make build MODULES=/abs/path` and finds its generators with
`gvrun --target-dir`.

## Container

- Image: `ghcr.io/kuleuven-micas/snax-gvsoc:gvs1`, built from `container/`.
- It holds compilers, Python packages and toolchains only. The repo is
  mounted at `/work`; `GVSOC_WORKDIR=/work/build` sends all GVSoC output to
  `build/`.

Build and push (local machine, Docker):

    docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:gvs1 container
    docker push ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

Run (MICAS server, Podman), from the repo root:

    podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

## Commands already tried

Run inside the container on a 2-core machine, from a clean image and a clean
repo, before step 1 was handed over. They are the starting point for GVS1
steps 2 to 4; times are for 2 cores.

Build GVSoC for the `snitch` target (8 min 21 s, first build):

    make -C gvsoc build TARGETS=snitch
    source gvsoc/sourceme.sh

Run the bundled program (exit code 0, prints nothing):

    gvrun --target snitch --work-dir build/work/snitch \
        --param chip/soc/binary=$PWD/gvsoc/pulp/examples/snitch/fp32_computation_vector.elf run

Build the snitch_cluster tests (47 ELFs, 4 s). `APPS=` skips the
applications, whose data generators need numpy and torch, which are not in
the image:

    cd snitch_cluster/target/snitch_cluster
    make DEBUG=ON APPS= tests

Run one (`printf_simple` prints `Hello, World!` nine times, exit code 0):

    gvrun --target snitch --work-dir /work/build/work/printf_simple \
        --param chip/soc/binary=$PWD/sw/tests/build/printf_simple.elf run

Tutorial 0 from a copy outside the GVSoC tree (build 2 min, prints `Hello`):

    mkdir -p tutorials && cd tutorials
    T=/work/gvsoc/engine/docs/developer_manual/tutorials
    cp -r $T/utils $T/0_how_to_build_a_system_from_scratch .
    cd 0_how_to_build_a_system_from_scratch
    export GVSOC_ROOT=/work/gvsoc
    make prepare gvsoc all run

The tutorial build shares `build/` with the `snitch` build; the `snitch`
target still ran afterwards.

Differences from the GVSoC website docs: the tutorials are in
`gvsoc/engine/docs/developer_manual/tutorials`, the launcher is `gvrun` with
`--parameter binary=<elf>`, and tutorials 13 and 18 have no directory.

## Log

### GVS1 step 1: repo and container

- 2026-10-07. Repo created on micaseb19; image built with Docker on WSL
  (x86), pushed to ghcr.io, pulled and run with Podman on micaseb19.
- Image: `ghcr.io/kuleuven-micas/snax-gvsoc:gvs1`, 4.73 GB unpacked, about
  2.0 GB to pull. Contents: RISC-V GCC 2.1 GB, Snitch LLVM 1.6 GB, Ubuntu
  base and build packages 0.7 GB, Python packages 0.4 GB.
- `git submodule status --recursive` shows gvsoc at 93cedc4 and
  snitch_cluster at 4652c6b.
- Version check in the container: gcc 13.3.0, cmake 3.28.3, Python 3.12.3,
  riscv64-unknown-elf-gcc 14.2.0, clang 12.0.1, bender 0.27.1,
  GVSOC_WORKDIR=/work/build. `/work` is writable.
- Plain `podman run --rm -it -v "$PWD":/work <image>` works; no extra
  mount or user flags needed.
- Learned: `git add` the submodules after checking out the pins and before
  `git submodule update --init --recursive`, or the update resets them to
  the commit recorded by `submodule add`.

### GVS1 step 2: GVSoC built, bundled program runs

- 2026-10-07, micaseb19, in the container.
- `make -C gvsoc build TARGETS=snitch` builds into `build/`.
- `gvrun --target snitch ... fp32_computation_vector.elf run` prints nothing
  and exits 0. With `--trace=pe0/insn`: 484 lines, first instruction at
  cycle 7909 (boot ROM, 0x1000), last one an `ebreak` at cycle 23862.
- Every new container needs `source gvsoc/sourceme.sh` again.
- `gvrun` creates its own `--work-dir`, but a `>` redirect into a directory
  that does not exist yet fails before `gvrun` starts.

### GVS1 step 3: Snitch tests built from source and run

- 2026-10-07, micaseb19, in the container.
- `make DEBUG=ON APPS= tests -j8` in `snitch_cluster/target/snitch_cluster`
  builds 47 test ELFs. `APPS=` skips the applications, whose data
  generators need numpy and torch (not in the image). The first build needs
  internet: Bender fetches one dependency into `snitch_cluster/.bender`.
- Ran 11 tests on `gvrun --target snitch`: simple, printf_simple, barrier,
  dma_simple, interrupt_local, fp32_computation_vector, openmp_parallel,
  perf_cnt, zero_mem, tls all exit 0 with no "invalid register" warning.
  non_null_exitcode exits 1, as intended (its main returns 14).
- This confirms the pin pair gvsoc 93cedc4 + snitch_cluster 4652c6b.
- Each run leaves its full system description in
  `build/work/<name>/gvsoc_config.json`.

### GVS1 step 4: tutorial 0, system from scratch

- 2026-10-07. Working copy in
  `tutorials/0_how_to_build_a_system_from_scratch`, with `tutorials/utils`
  beside it; write-up in `docs/tutorials/0_system_from_scratch.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `export GVSOC_ROOT=/work/gvsoc`, then `make prepare gvsoc all run` prints
  `Hello`. The GVSoC build for `my_system` takes 1 min 43 s after a `snitch`
  build. No `BUILDDIR=`, so the build shares `/work/build`; the `snitch`
  target still runs afterwards.
- `--trace=insn`: 231 lines, first instruction at cycle 3 (`_start`,
  0xc04), last one an `ebreak` at cycle 298. 100 MHz clock, 10000 ps per
  cycle, one instruction per cycle.
- The generator (`my_system.py`) runs twice. At build time
  `gapy ... components` writes `build/build/gvsoc/configs/my_system.config`
  (the C++ models to build, one `.so` each in `build/install/models`, named
  by a hash of sources and flags) and `my_system.tree.cpp` (instances,
  bindings and some parameter values, compiled into
  `libplatform_tree_my_system.so`). At run time `gvrun` runs the script
  again and writes `build/work/gvsoc_config.json` with the per-instance
  properties.
- The loader writes the ELF through the router as a normal IO request, then
  drives the entry and fetch-enable wires of the core. `printf` and `exit`
  use semihosting; there is no UART.
- `cpu/iss` is the instruction set simulator, GVSoC's CPU model: it executes
  each instruction's effect and adds a cycle count, with no pipeline model.
  The Snitch cores are variants of it (`iss/src/snitch*`). An `iss_v2`
  directory exists next to it; not looked at.
- Ports are declared in the C++ model (`new_master_port`, `new_slave_port`).
  The `i_X` / `o_Y` methods of the Python generator wrap those names with a
  type signature and are the nearest thing to a module header. List them
  with `grep -n "def [io]_[A-Z_]*(" <generator>.py`, or at run time with
  `--trace=<instance>` and the `New ... port` lines. The Python list can be
  incomplete: `memory.cpp` has `power_ctrl` and `meminfo`, `memory.py` only
  `i_INPUT`.
- What GVSoC checks on a binding, tried on this system: a misspelled method
  is a Python `AttributeError`; a type mismatch is `Invalid signature`; a
  port name unknown to the C++ model is `Binding from invalid slave port`;
  a missing `o_DATA` is `Data master port is not connected` (a check in the
  core model). A missing `o_DATA_DEBUG` runs fine. A missing `o_START` or
  `o_ENTRY` gives no message and the simulation never ends.
- The tutorial text in `tutorials.rst` at the pin is out of date (`parser`
  and `options` arguments, `remove_offset`, `gvsoc --binary`). The file in
  `solution/` is the working reference: `TargetParameter`, `rm_base=True`,
  and a `Target` class with `model` and `name` attributes.
- Every tutorial writes its program to `build/test/test` and its run output
  to `build/work/`, so each one overwrites the previous.
- GDB skipped: the server starts, but the toolchain's
  `riscv64-unknown-elf-gdb` needs libpython3.10, which Ubuntu 24.04 does
  not have. Seen on the check machine; not tried in the container.
- A run leaves `__pycache__/` next to the generator; it should be ignored
  by git.

### GVS1 step 5: tutorial 1, component from scratch

- 2026-10-08. Working copy in
  `tutorials/1_how_to_write_a_component_from_scratch`; write-up in
  `docs/tutorials/1_component_from_scratch.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `make prepare gvsoc all run` prints
  `Received request at offset 0x0, size 0x4, is_write 0` then
  `Hello, got 0x12345678 from my comp`. The tutorial text matches
  `solution/`, except one handler declaration with `void *__this` instead
  of `vp::Block *__this`.
- The first `make gvsoc` takes 4 min 1 s (197 files), as long as a first
  build of tutorial 0. The tutorial directory is a module root and an
  include path of every model, so switching tutorials recompiles all models
  of `my_system`, the RV64 core included, in four variants (`optim`,
  `debug`, `asserts`, `profile`). Expect this once per tutorial. Editing
  `my_comp.cpp` and rebuilding: 7 to 14 s.
- The library name `gen_my_comp_cpp_<hash>` hashes the source names and
  flags, not the file content; it stays the same across edits.
- Changing `value` in `my_system.py` needs no rebuild and gives no platform
  tree warning: the property is only in `gvsoc_config.json`, and the tree
  node of `my_comp` has no compiled config.
- `get_child_int` returns 0 with no message when the property is missing,
  so a misspelled property name is silent.
- Without `extern "C" gv_new` the build passes and the run aborts with
  `couldn't find gv_new loaded module`.
- An IO request is a direct function call through pointers copied at bind
  time (`IoMaster::bind_to`); router, model and the core's `c.lw` all show
  in cycle 158. For a load, `get_data()` points to the core's destination
  register. `lw` does not clear it first and `lbu` does, so an unanswered
  4-byte read returns the old register value and a 1-byte one returns 0.
- The model answers `IO_REQ_OK` to everything. Returning `IO_REQ_INVALID`,
  or reading an unmapped address, makes the RV64 core take a load fault;
  the runtime exits 1 and `gvrun` prints
  `Input error: Platform returned an error (exitcode: 1)`, with no message
  naming the address. Not checked on the Snitch target.
- Nothing in the pinned tree reads `GAPY_TARGET`; tutorial 1's
  `my_system.py` has none and works. The tutorial 0 page was corrected.
- Tutorial 1's `my_system.py` creates no `Gdbserver`; the runner adds one
  at the top level (`gvsoc/engine/python/gvsoc/runner_gvrun2.py`).
- Questions answered. `vp` is the engine's C++ namespace and headers
  (`gvsoc/engine/engine/include/vp/`): base classes, port types, clocks,
  traces, registers; the source never spells it out, the docs call GVSoC a
  virtual platform. `testset.cfg` is GVSoC's own regression test for the
  tutorial (`gvtest`): it builds `solution/` in its own build directory,
  runs it and checks the two output lines; not used here.
- The page has a commented `my_comp.cpp` and a line-by-line explanation of
  step 3. Both tutorial pages draw the system in Mermaid.

### GVS1 step 6: tutorial 2, components communicating

- 2026-10-08. Working copy in
  `tutorials/2_how_to_make_components_communicate_together`; write-up in
  `docs/tutorials/2_components_communicating.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `make prepare gvsoc all run` prints `Received request ...`,
  `Received value 1`, `Received results 11111111 22222222`, then
  `Hello, got 0x12345678 from my comp`. Build 4 min 25 s (201 files), again
  a full rebuild because the tutorial directory changed. The text in
  `tutorials.rst` uses the old `gsystree` alias and `void *__this`;
  `solution/` is the reference.
- A wire (`vp::WireMaster<T>` / `vp::WireSlave<T>`, `vp/itf/wire.hpp`) is a
  direct function call, like an `io` request: binding copies the slave's
  handler into the master, `sync(value)` calls it. No event, no delay, no
  stored value. The whole exchange (`my_comp` -> `my_comp2` -> back into
  `my_comp`) runs inside the core's `c.lw` at cycle 158, with the calls
  nested.
- The signature string is only a label both ends must match
  (`Invalid signature` otherwise); GVSoC never compares it with the C++
  types. Same signature with different C++ types builds and binds, then
  crashes (`Segmentation fault`, exit 139).
- `sync()` on an unbound `WireMaster` crashes with a segmentation fault;
  checked with a print to `stderr` showing `is_bound()` = 0 just before the
  call. Unlike tutorial 0's unbound `o_DATA_DEBUG`, this is not harmless.
  Models' `printf` output is lost in such a crash (stdout is buffered).
- One master can be bound to several slaves; each receives the value in
  turn (`next` chain in `WireMaster`). Tried with two `MyComp2`.
- A pointer sent on a wire is only valid during the receiver's handler when
  it points to the sender's stack, as in the tutorial.
- The two classes are both called `MyComp`; this is fine because each
  model is its own library with its own `gv_new`.
- The working copy keeps the `solution/` files; the page shows the same
  code with comments, which was built and run on the check machine.
- Impression after tutorial 2: GVSoC is more involved than expected and
  its documentation is weak (out-of-date text, few comments, behaviour found
  by experiment). An input for GVS4.

## Findings for later tasks

### GVS2

- The GVSoC Snitch model matches snitch_cluster as of August 2024.
- The `perf_cnt` test runs but every counter reads 0.
- The `snitch` target has a `soc/nb_cluster` parameter.
- Changing the L1 bank count (16, 32, 64) left the `dma_simple` cycle count
  unchanged at 23460. One core and a plain DMA copy, so this does not yet
  say whether bank contention is modelled.
- GVSoC's docs say `pulp.snitch.snitch_cluster_single` and the default slow
  core are to be deprecated in favour of `snitch:core_type=fast`.
- The `Router` is not the TCDM crossbar. TCDM path in the Snitch target
  (read from `snitch_cluster.py` and the C++, not yet measured): per-core
  `Router` (address decode, `bandwidth=8`) -> `L1_interleaver` (bank select
  from the low address bits, no arbitration) -> `Memory` bank. Per-bank
  contention is in the bank model: `width_log2=3` and a `next_packet_start`
  cycle, so a request to a busy bank gets extra latency. No priority or
  round-robin. The DMA reaches the same banks through `DmaInterleaver`, so
  a non-core port (a streamer) could be added the same way. `narrow_axi`
  and `wide_axi` are plain `Router` instances. To measure: two masters
  hitting the same bank in the same cycle.

### GVS3

- Editing one C++ model and rebuilding takes 5 to 20 s; a run of a small
  test takes 1 to 3 s (2 cores).
- The bank count is hard-coded in the stock generator. For sweeps, our own
  target should expose such values as `gvrun` parameters, so that a design
  point needs no edit of the generator. Not tried yet.
- Generator changes need no rebuild as long as every C++ model variant is
  already compiled. Checked: values (tutorial 0 memory size) and shape
  (Snitch L1 with 16, 32 and 64 banks, edited in the installed generator
  `build/install/generators/pulp/snitch/snitch_cluster/snitch_cluster.py`).
  GVSoC warns that the installed platform tree does not match and builds
  the system from `gvsoc_config.json`; traces are identical and run time is
  unchanged (1.6 s for the bundled ELF, 2 cores). A variant with other
  sources or flags (e.g. `Router(..., synchronous=False)`) fails with
  `Couldn't find component` until rebuilt.
- Caveat from `runner_gvrun2.py`: the JSON path only works for models that
  read their parameters from JSON. `Memory` and the clock have that
  fallback and the router reads JSON only; these are the only compiled
  configs in the stock `snitch` target. Other models with a config class
  (snitch fast core, iDMA v2/v3, `iss_v2`) are not checked.
- GVSoC does not check that a component's ports are all bound, unless the
  model does it itself. Our SNAX components should check their mandatory
  ports in C++, as the core does for `data`.
- A model reads its parameters from `gvsoc_config.json` with
  `get_js_config()`, so a value that only goes through `add_properties` can
  be swept with no rebuild (tutorial 1). Our components should read their
  sizes and latencies that way, and check that each one is present, since
  a missing property reads as 0 with no message.
- Our module root (`snax/`) should stay at one path: moving it, like
  switching tutorial directories, recompiles every model of the target.
- A register window should return `IO_REQ_INVALID` for offsets and sizes it
  does not serve, so a wrong access from the program traps instead of
  reading stale data (checked on the RV64 core, not on Snitch).
- GVSoC's `gvtest` with a `testset.cfg` and a `Checker` on the output is a
  ready pattern for regression tests of our components.
- `start` / `busy` / interrupt lines map to `WireMaster<bool>` /
  `WireSlave<bool>`, but a wire call takes zero time and nests inside the
  caller. An accelerator model that should react a cycle later must
  schedule a clock event in its wire handler (tutorial 6), and must have
  its state consistent before it drives any wire, since the callee may call
  back into it.
- Optional output wires of our components should be guarded with
  `is_bound()`; `sync()` on an unbound wire crashes.
- An interrupt line to several cores can be one master bound to several
  slaves.
