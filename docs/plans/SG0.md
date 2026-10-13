# SG0 plan: the repository, the images and the probe

SG0 is the first task of M16 in snax-forge (SNAX-GVSoC aligned with
snax_cluster, D116). Acceptance: the probe result and the chosen GVSoC commit
are logged, and both images build and run on the MICAS server.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply`; commits and pushes
  are done by hand.
- Anything not verified is said so.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | Detached copy of GVSoC `93cedc4`, submodules folded in, pushed | done 2026-10-12 |
| 2 | P1: `UPSTREAM.md`, short README, upstream CI and CODEOWNERS removed, container imported from the experiment, this plan and the notes | done 2026-10-12 |
| 3 | Image built from P1's `container/` | folded into step 4 |
| 4 | P2: two-stage image `snax-gvsoc:main` with snax_cluster's toolchain (clang, lld, llvm-tools, clang-format 21.1.6, bender 0.28.2) and zsh; rv64 GCC and Snitch LLVM 12 dropped; built, pushed and run on micaseb19 | done 2026-10-12 |
| 5 | Probe: snax_cluster `8ebd4229` tests built with its own flow (`cfg/snitch_cluster.hjson`, generic LLVM, `rtl-generic`) and run on `gvrun --target snitch` | done 2026-10-12 |
| 6 | P3: snax_cluster's cluster CSRs 0xBC1 to 0xBC3 in the Snitch core; the probe run again, commit chosen | wip |
| 7 | P4: snax-forge's image FROM `snax-gvsoc:main`, pixi last | todo |
| 8 | P5: SG0 closed here, and the STATUS.md update for snax-forge | todo |

## Later

- CI rebuilds `snax-gvsoc:main` on every push to `main`, as snax_cluster's
  `build-docker.yml` does. Until then it is built and pushed by hand.

## Decided

- Probe result: snax_cluster's plain tests stop in their start-up code,
  which reads the cluster CSRs 0xBC1 to 0xBC3 that snax_cluster added to
  Snitch and GVSoC lacks. With them (P3) all 17 tests pass. Nothing else
  differed: boot address, memory map and peripheral registers match.
- Chosen GVSoC commit: `93cedc4` (latest) with P3. No older commit has these
  CSRs, so going back would not help.

## SG2 starts from

- snax_cluster's Snitch sends every CSR instruction with an address in
  0x3C0 to 0x5FF (`hw/snitch/src/csr_snax_def.sv`) out on its accelerator
  port (`acc_qreq_o.addr = SNAX_CSR` in `snitch.sv`); 0x5FE and 0x5FF are
  the task-ready and task-done queues. The SNAX barrier CSRs 0x7C3 and 0x7C4
  lie outside that range.
- GVSoC's Snitch core claims no CSR in 0x3C0 to 0x5FF (PMP, which would put
  `pmpaddr16` to `pmpaddr63` at 0x3C0 to 0x3EF, is off for Snitch), so
  today these accesses end in the "unsupported CSR" branch of `csr.cpp`.
- The Snitch core's constructor (`core/models/cpu/iss/src/snitch/snitch.cpp`)
  already has an offload request port pair (`acc_req...`): the place to start
  reading.
