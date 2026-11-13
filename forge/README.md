# forge/

One folder per snax-forge design point, as SNAX-GVSoC reads it. Each folder is snax-forge's generator output, checked in untouched, so this repository's regression can run a design point without snax-forge.

- Never edit a folder by hand: snax-forge's `tests/gen/test_fixture.py` generates each again and compares it byte for byte.
- That test's `DESIGNS` list is the list of folders; it fails when a folder is missing or extra.

## What a folder holds

| File | What it is |
|---|---|
| `snax_forge.hjson` | the cluster file: snax-forge's base cluster with the platform's values, one core holding the slot and the DMA, the slot `snax_forge_<design>` with one streamer set per accelerator |
| `snax_forge_<design>_streamer_<set>.hjson` | a set's streamer: readers for its accelerator's inputs, writers for its outputs, spatial bounds in 64-bit words |
| `accelerator.json` | the accelerators' one description: per accelerator its groups, units, links and CSR offsets; `snax/snax_cfg.py` reads and checks it |
| `include/` | the headers a program drives it with: the streamer CSR map and `<set>_csr.h` per set, and the runtime's cluster headers |
| `main.c` | the program: the design point's task list on snRuntime, then the self-check (`forge cycles`, `forge data`, one `forge counter` per task) |
| `obs_marks.json` | the quiet build's sections (`-DFORGE_QUIET`): the value each section writes to CSR `0x7C5` |
| `data.h` | the inputs (seed 0) and each output's golden, padded to whole DMA beats |
| `manifest.json` | the design, its files, its trace paths, its CSR layout and each task's beats and CSR values |

Every hjson and C file starts with a comment naming the design point.

## The fixtures

| Kind | Folders |
|---|---|
| element-wise, int64 | `vecadd`, `vecmul`, `vecadd_n7` (a padded tail) |
| element-wise, narrow types | `vecadd_i32`, `vecmul_i32`, `vecmul_i32_i64`, `vecadd_i8`, `matadd` (int32, the first 2-D bind) |
| one stream and scalars | `relu`, `axpy` (a CSR scalar), `axpy_baked` (the scalar baked in) |
| reductions | `vsum`, `vsum_tree`, `vsum_tree_i32`, `vsum_tree_i8`, `vsum_tree_n21`, `rowsum`, `rowsum_serial`, `rowsum_3x7`, `rowsum_2`, `rowsum_2_padded` (`padded_rows` layout) |
| dot, the six variants | `dot_1` (two accelerators), `dot_1_enc` (one accelerator of two groups), `dot_2` to `dot_6` (one group of linked units) |
| matvec | `matvec_1` to `matvec_6`, `matvec_seed` and `matvec_seed_serial` (a seeded fold) |
| shared movers | `dot_1_shared`, `mvt_1_dot2_shared` (W = 8) |

## Refreshing a folder

From a snax-forge checkout next to this one, with the folder cleared first (gen-gvsoc leaves a file it no longer writes in place):

    pixi run sandbox recipes/elementwise/vecadd.json
    pixi run design out/sandbox/vecadd/2_bind.snaxdfg --platform platforms/snax_forge.json
    pixi run gen-gvsoc out/design/vecadd/design_point.json --out ../snax-gvsoc/forge/vecadd

- The design step reads the sandbox's last step, `out/sandbox/<design>/<n>_<transform>.snaxdfg`.
- `rowsum_2_padded` is `rowsum_2` with `--set memory.passes.layout=padded_rows` on the design step; `mvt_1_dot2_shared` is its recipe with `--set W=8` on the sandbox step.
- Commit the folder as written, then bump snax-forge's submodule so its test compares against it.
- `make regress` runs every folder through the generic app, so a new folder needs nothing else.

## How it runs

`make regress` runs every folder twice (`tests/snax/regress.py`):

- `forge.<design>`: the generic app builds `main.c` (`make -C sw/apps/forge DESIGN=<design>`), `snax_hjson` runs it on the folder's cluster file with the traces `manifest.json` names, and each `forge counter` line must equal its unit's run line.
- `forge_quiet.<design>`: the quiet build, `forge_quiet.elf`, a plain run that must exit 0.

No model is compiled for a design point: `vecadd` runs on the build's platform tree, the others on their JSON config, with gvrun's warning that the platform tree does not match.
