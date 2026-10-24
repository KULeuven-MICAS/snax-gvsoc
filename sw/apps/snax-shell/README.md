# snax-shell

`SnaxShell` and `SnaxUnit` (a lockstep add of 4 lanes of 64 bit behind
the streamer), driven by hand on `snax_hjson` with
`forge/vecadd/snax_forge.hjson`. snax_cluster's `snax-alu` DMA and streamer
setup, written out with the CSRs of `forge/vecadd/include/`
(`streamer_csr_addr_map.h`, `acc_csr.h`): `loopCount` 978, start 979, busy
980, the counter 981. `data.h` is `data/datagen.py` at 192 words, seed 0:
the data snax_cluster's `snax-alu` `datagen.py` gives for an add. snax_cluster has
no such accelerator yet, so there is no RTL run to compare with.

One streamer run of 48 beats feeds three unit runs of 16 beats
(`RUN_BEATS`). It checks only what does not depend on code layout, and
returns the number of checks failed plus the data errors:

| Line | Check |
|---|---|
| `data` | O = A + B over the three runs |
| `first run` | run 1, started alone: the counter once busy is 0 is at least `RUN_BEATS` |
| `held start` | start 3, written right after start 2, is held until run 2 is done: the `mcycle` span from before start 2 to after start 3 is at least `RUN_BEATS` |
| `loopCount 0` | a start with `loopCount` 0: busy 0 and the counter 0 |

It prints run 1's counter on its own line, `snax-shell counter: <n>`.
`make regress` runs it with `--trace=snax_acc0/unit` and checks that `n` is
the unit's first run line's busy + stall_in + stall_out + flush, and that
the run fired 16 times (`check_counter` in `tests/snax/regress.py`). How
many cycles a run takes beyond its beats follows the core's and the
streamer's timing, so a change to the program can move `n`.

## Build and run

In the container, from snax-gvsoc, with GVSoC built for `snax_hjson`:

    make -C sw/apps/snax-shell
    source sourceme.sh
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/snax-shell --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-shell/snax-shell.elf run

It prints gvrun's warning that the platform tree does not match (the
cluster file's accelerator is not the build's default file's, so gvrun runs
it on the JSON config), the unit's lines per run (`docs/EVENTS.md`), among
them `run index=0 firings=16 busy=B stall_in=SI stall_out=SO flush=0` (B +
SI + SO the counter), then those of runs 1 and 2, and

    snax-shell data: 0 errors (192 words)
    snax-shell counter: N
    snax-shell first run: counter N, at least 16 beats
    snax-shell held start: mcycle span S, at least 16 beats
    snax-shell loopCount 0: busy 0, counter 0
    snax-shell errors: 0

and exits 0. N and S follow the core's timing: 17 (`run index=0 firings=16
busy=16 stall_in=1 stall_out=0 flush=0`) and 19.
