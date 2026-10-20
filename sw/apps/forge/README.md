# forge

GEN2a (`docs/plans/GEN2a.md`): the generic app for a generated accelerator.
It builds the program snax-forge writes for a design point
(`forge/<design>/main.c`, snax-forge's C backend, its D135) with the
fixture's own headers and data; nothing here is written by hand per design.

    make -C sw/apps/forge DESIGN=vecadd

- `DESIGN` (default `vecadd`): the fixture, `forge/$(DESIGN)/`
  (`forge/README.md`). The ELF goes to `build/sw/apps/forge/$(DESIGN)/forge.elf`.
- `FORGE` (default `forge/$(DESIGN)`): the folder to build from, for a
  bundle of the same form elsewhere (snax-forge's `out/gvsoc/<design>/`).

The fixture's folder (for `data.h`) and its `include/` (for
`streamer_csr_addr_map.h` and `<instance>_csr.h`) come before
`sw/generated/`, as in the other forge apps. There is no datagen: `data.h`
holds the inputs, the zeroed outputs and their goldens. The ELF depends on
every file of the fixture, so a refreshed fixture rebuilds it.

## What the program does

The design point's task list on snRuntime (snax-forge `lower/c.py`): one
function per core, `main` calling its core's through a table, each step on
the core that owns its component in the cluster file (the DMA on the core
with `xdma`, the accelerator on the one holding the slot), a barrier where
another core goes on, and each accelerator task's counter stored after its
wait; no task marks. `main` reads `mcycle` first, and on the accelerator's
core calls `forge_check()` after its function, which reads `mcycle` first
and prints the window between the two, then checks:

    forge cycles: <n>
    forge data: <e> errors (<words> words)
    forge counter <task>: <c>          (one per accelerator task)
    forge errors: <err>

and returns `err`: the data errors, plus 1 per counter below its task's
beats. `make regress` runs every folder of `forge/` with it and checks each
counter against the unit's run line for that task (`check_counter`).

## Run

In the container, from snax-gvsoc, with GVSoC built and the program made:

    source sourceme.sh
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

It warns that the platform tree does not match (LNK2a), prints the unit's
`run 0: firings 16 busy 16 stall_in 3 stall_out 0 flush 0`, then
`forge data: 0 errors (64 words)`, `forge counter add_acc: 19` (busy +
stall_in + stall_out + flush of that line) and `forge errors: 0`, and exits 0.
