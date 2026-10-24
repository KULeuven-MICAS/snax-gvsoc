# forge-reduce

Kept only for `forge-reduce.vsum-r16` in `make regress`. Since GEN2a,
`forge/vsum/` itself runs snax-forge's generated program with the generic
app (`sw/apps/forge/`). `vsum-r16` overrides the derived task list by hand
(`RATE_OVERRIDE=16`: one run, four sums of 16-element chunks), the only run
with more than one sum per run (T < n): no kernel gives one yet. The 1-D
form `out[i // 16] += A[i]` has a non-affine index; making it affine splits
i into two temporal loops, ND1's split-and-tag transform (snax-forge open
item 81). It retires once ND1 or tier A gives a real T < n.

GEN3 step 6b (`docs/plans/GEN3.md`): the program for a generated one-lane
reduction, a fixture in `forge/<design>/` (`forge/README.md`) whose unit is
a fold (SnaxUnit with one input and a `rate`, snax-forge's Accumulator). It
uses only the fixture's headers, `streamer_csr_addr_map.h` and `acc_csr.h`
(its `include/` comes before `sw/generated/`), and snRuntime's `csrw_ss`
and `csrr_ss`.

It follows the design point's derived task list (snax-forge
`snax_forge/lower/derive.py`), with the bases replaced by L1 pointers:

1. The DMA core loads A into L1 (`load_A`); barrier.
2. The compute core configures the two streamer tasks, reader 0 = A
   (temporal bound `BEATS`) and writer 0 = O (temporal bound
   `BEATS / RATE`), both spatial stride 8 and temporal stride 8. Then
   `ACC_RW_LOOP_COUNT`, the task's `n` (`BEATS`), and `ACC_RW_LEN`, its `T`
   (`RATE`).
3. The starts in the task list's order: the streamer (one start CSR for its
   two movers), then the accelerator.
4. Busy polled, the accelerator's, then the streamer's.
5. `ACC_RO_PERF_COUNT` read, and the `BEATS / RATE` sums checked against
   `OUT`.

It prints

    forge-reduce data: <e> errors (<k> sums)
    forge-reduce counter: <n>
    forge-reduce errors: <err>

and returns `err`: the data errors, plus 1 when the counter is below the
beats. `make regress` checks the counter against the unit's first run line
(`check_counter`, the manifest's beats).


## DESIGN, N, BEATS, RATE and RATE_OVERRIDE

    make -C sw/apps/forge-reduce DESIGN=vsum

- `DESIGN` (default `vsum`): the fixture, `forge/$(DESIGN)/`. The ELF goes
  to `build/sw/apps/forge-reduce/$(DESIGN)/`.
- `N`: the manifest's `symbols.N` (vsum's 64).
- `BEATS`: the manifest's `tasks[0].beats` (vsum's 64); a make error when
  it is not `N` (one lane).
- `RATE`: the manifest's `tasks[0].csrs.len`, inputs per sum (vsum's 64,
  T = N: one sum); a make error when it does not divide `BEATS`.
- `RATE_OVERRIDE` (default unset): replaces the manifest's len, so the
  golden, the writer's bound and the unit's `len` follow it (still a
  divisor of `BEATS`); the ELF goes to
  `build/sw/apps/forge-reduce/$(DESIGN)-r$(RATE_OVERRIDE)/`. It overrides
  the derived task list by hand, to run more than one sum per run until a
  kernel gives T < N: `make regress` runs vsum with 16
  (`forge-reduce.vsum-r16`, 4 sums).

None of the first four is set by hand. `BEATS` and `RATE` reach the
program as `-DBEATS` and `-DRATE`, and the ELF depends on the manifest, so a
change rebuilds it.
`data.h` is `data/datagen.py` at `--length=N --rate=RATE --seed=0`: A int64
in [-1000, 1000) from NumPy's `default_rng(0)`, as snax-forge's `vsum.py`
draws it, and `OUT` the sums; it depends on the manifest and the Makefile.

## Run

In the container, from snax-gvsoc, with GVSoC built and the program made
(`make -C sw/apps/forge-reduce DESIGN=vsum`; `make regress` builds only
`vsum-r16`):

    source sourceme.sh
    gvrun --target snax_hjson --param hjson=$PWD/forge/vsum/snax_forge.hjson \
        --work-dir build/work/forge-reduce --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge-reduce/vsum/forge-reduce.elf run

It warns that the platform tree does not match (LNK2a: the cluster file's
components are not `snax_hjson`'s default's), prints the unit's lines,
among them `run index=0 firings=64 busy=64 stall_in=2 stall_out=0 flush=1`
(the core's timing can move the stalls), then
`forge-reduce data: 0 errors (1 sums)`, the counter (67, busy + stall_in +
stall_out + flush of that line) and `forge-reduce errors: 0`, and exits 0.
`vsum-r16` prints `forge-reduce data: 0 errors (4 sums)` and counter 67.
