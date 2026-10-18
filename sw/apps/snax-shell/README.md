# snax-shell

GEN3 step 2 (`docs/plans/GEN3.md`): `SnaxShell` and `SnaxUnit` on the
`snax_tiled_add` target (`snax/snax_tiled_add_acc.py`, a lockstep add of 4
lanes of 64 bit behind `snax_alu`'s streamer). snax-alu's DMA and streamer
setup (`snax-alu-lib.h`, `streamer_csr_addr_map.h`); the shell's CSRs by
hand in the source: `loopCount` 978, start 979, busy 980, the counter 981.
`data.h` is snax-alu's `datagen.py` (add) at 128 words, NumPy seed 0. It runs
only on `snax_tiled_add` (snax_cluster has no such accelerator yet).

One streamer run of 32 beats feeds two unit runs of 16 beats. It checks, and
returns the number of checks failed plus the data errors:

| Line | Check |
|---|---|
| `data` | O = A + B over both runs |
| `counter` | the counter after run 2 is run 2's busy cycles |
| `held start` | start 2, written right after start 1, is held until run 1 is done: the `mcycle` span from before start 1 to after start 2 is at least run 1's busy cycles |
| `loopCount 0` | a start with `loopCount` 0: busy 0 and the counter 0 |

The busy cycles are the unit's `busy + stall_in + stall_out` of its trace
line per run (`--trace=snax_acc0/unit`), read by hand: 16 and 16 in this
build (`docs/notes/NOTES.md`, GEN3 step 2), written in the source as
`RUN0_BUSY_CYCLES` and `RUN1_BUSY_CYCLES`. Run 1's count depends on the
core's timing (a fetch before start 1 gives the streamer a head start: 17 in
another layout of the same source), so a change to the program can move it.

## Build and run

In the container, from snax-gvsoc, with GVSoC built for `snax_tiled_add`:

    make -C sw/apps/snax-shell
    source sourceme.sh
    gvrun --target snax_tiled_add --work-dir build/work/snax-shell \
        --trace=snax_acc0/unit --param chip/soc/binary=$PWD/build/sw/apps/snax-shell/snax-shell.elf run

It prints

    snax-shell data: 0 errors (128 words)
    snax-shell counter: 16 (run 2's busy cycles 16)
    snax-shell held start: mcycle span 19 (run 1's busy cycles 16)
    snax-shell loopCount 0: busy 0, counter 0
    snax-shell errors: 0

with the unit's `run 0: firings 16 busy 16 stall_in 0 stall_out 0` and
`run 1: ...` the same, and exits 0.
