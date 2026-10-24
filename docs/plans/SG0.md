# SG0 plan: the repository, the image and the probe

SG0 is the first task of M16 in snax-forge (SNAX-GVSoC aligned with
snax_cluster, D116). It set up this repository, the development image and
the probe of snax_cluster's tests on GVSoC. Acceptance: the probe result and
the chosen GVSoC commit are logged, and the development image builds and
runs on the MICAS server. Closed 2026-10-13; the log is
`docs/notes/NOTES.md` (SG0 steps 1 to 8).

## Steps

Step 1 (detached copy of GVSoC `93cedc4`, submodules folded in), step 2 (P1:
`UPSTREAM.md`, short README, upstream CI and CODEOWNERS removed, this plan
and the notes), step 4 (P2: image `snax-gvsoc:main` with snax_cluster's
toolchain, clang-format 21.1.6, bender 0.28.2; replaced in step 7) and step
5 (the probe: snax_cluster `8ebd4229` tests built with its own flow, run on
`gvrun --target snitch`) on 2026-10-12; step 3 folded into step 4. Step 6
(P3: the cluster CSRs 0xBC1 to 0xBC3 in the Snitch core, commit chosen),
step 7 (P4a/P4b: one image, `snax-forge:main` from snax-forge's
`container/` with pixi 0.41.4, D118; `container/` removed here) and step 8
(P5: closed) on 2026-10-13.

## Decided

- Probe: snax_cluster's plain tests stop in their start-up code, which reads
  the cluster CSRs 0xBC1 to 0xBC3 that snax_cluster added to Snitch and
  GVSoC lacks. With them (P3) all 17 tests pass. Nothing else differed:
  boot address, memory map and peripheral registers match.
- Chosen GVSoC commit: `93cedc4` (latest) with P3. No older commit has these
  CSRs, so going back would not help.

## Later

- snax-forge's CI rebuilds `snax-forge:main` on every push to `main`, as
  snax_cluster's `build-docker.yml` does; until then it is built and pushed
  by hand.
- One pixi version for both locks: the toolchain lock (format 7) needs pixi
  0.81.0, snax-forge's CI and lock use 0.41.4.

## SG2 starts from

- snax_cluster's Snitch sends every CSR instruction with an address in
  0x3C0 to 0x5FF (`hw/snitch/src/csr_snax_def.sv`) out on its accelerator
  port (`acc_qreq_o.addr = SNAX_CSR` in `snitch.sv`); 0x5FE and 0x5FF are
  the task-ready and task-done queues. The SNAX barrier CSRs 0x7C3 and 0x7C4
  lie outside that range.
- GVSoC's Snitch core claimed no CSR in 0x3C0 to 0x5FF (PMP, which would
  put `pmpaddr16` to `pmpaddr63` at 0x3C0 to 0x3EF, is off for Snitch).
