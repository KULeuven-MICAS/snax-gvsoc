# forge-elementwise

GEN3 step 5 (`docs/plans/GEN3.md`): the program for a generated elementwise
accelerator, a fixture in `forge/<design>/` (`forge/README.md`). It uses only
the fixture's headers, `streamer_csr_addr_map.h` and `acc_csr.h` (its
`include/` comes before `sw/generated/`), and snRuntime's `csrw_ss` and
`csrr_ss`; no snax-alu library.

It follows the design point's derived task list (snax-forge
`snax_forge/lower/derive.py`), with the bases replaced by L1 pointers:

1. The DMA core loads A and B into L1 (`load_A`, `load_B`); barrier.
2. The compute core configures the three streamer tasks, reader 0 = A,
   reader 1 = B, writer 0 = O: spatial stride 8, temporal bound `BEATS`,
   temporal stride `8 * LANES`. Then `ACC_RW_LOOP_COUNT`, the accelerator
   task's `n` (`BEATS`).
3. The starts in the task list's order: the streamer (one start CSR for its
   three movers), then the accelerator.
4. Busy polled, the accelerator's, then the streamer's.
5. `ACC_RO_PERF_COUNT` read, and the data checked against `OUT`.

It prints

    forge-elementwise data: <e> errors (<n> words)
    forge-elementwise counter: <c>
    forge-elementwise errors: <err>

and returns `err`: the data errors, plus 1 when the counter is below the
beats. `make regress` checks the counter against the unit's first run line
(`check_counter`, the manifest's beats).

It stays hand-written until GEN2a, when snax-forge's lowering writes the
program from the task list.

## DESIGN, MODE, DATA_LEN, BEATS and LANES

    make -C sw/apps/forge-elementwise DESIGN=vecadd MODE=0

- `DESIGN` (default `vecadd`): the fixture, `forge/$(DESIGN)/`. The ELF goes
  to `build/sw/apps/forge-elementwise/$(DESIGN)/`.
- `MODE` (default 0): snax-alu's `datagen.py` mode, which gives `OUT`: 0
  add, 2 mul. It must match the design's op; a change of `MODE` makes
  `data.h` again.
- `DATA_LEN`: not set by hand, read from the manifest's `symbols.N`
  (vecadd's 64). `data.h` is `datagen.py` at `MODE` and `--length=DATA_LEN`,
  NumPy seed 0, as snax-shell's; it depends on the manifest and the Makefile.
- `BEATS`: the manifest's `tasks[0].beats` (vecadd's 16), and `LANES` =
  `DATA_LEN / BEATS` (4); a make error when `BEATS` does not divide
  `DATA_LEN`. Both reach the program as `-DBEATS` and `-DLANES`, and the
  ELF depends on the manifest, so a change of either rebuilds it.

datagen's `LOOP_ITER` (from its `SPATIAL_PAR` 4) is not used, so the program
follows the design point's lanes. Every fixture so far is at W = 4; W = 8
has none, so a run at 8 lanes is not tried.

## Run

In the container, from snax-gvsoc, with GVSoC built and the program made:

    source sourceme.sh
    gvrun --target forge_vecadd --target-dir=$PWD/forge/vecadd \
        --work-dir build/work/forge-elementwise --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge-elementwise/vecadd/forge-elementwise.elf run

It warns that `forge_vecadd` has no platform tree, prints the unit's line
`run 0: firings 16 ...`, then `forge-elementwise data: 0 errors (64 words)`,
the counter (busy + stall_in + stall_out + flush of that line; 19 in GEN3
round 3b's build, which the core's timing can move) and
`forge-elementwise errors: 0`, and exits 0.
