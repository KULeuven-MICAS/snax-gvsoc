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
| element-wise, int64 | `vecadd_v1`, `vecmul_v1`, `vecadd_v1_3` (a padded tail) |
| element-wise, narrow types | `vecadd_v1_1`, `vecmul_v1_1`, `vecmul_v1_1_1`, `vecadd_v1_2`, `matadd_v1` (int32, the first 2-D bind), `vecadd_v1_1_w1` (one lane: inputs sliced 2 from a word, the output packed 2 to one) |
| one stream and scalars | `relu_v1`, `axpy_v1` (a CSR scalar), `axpy_v1_1` (the scalar baked in) |
| reductions | `vsum_v1`, `vsum_v1_1`, `vsum_v1_1_1`, `vsum_v1_1_2`, `vsum_v1_1_3`, `rowsum_v1`, `rowsum_v3`, `rowsum_v1_1`, `rowsum_v2`, `rowsum_v2_padded` (`padded_rows` layout) |
| dot, the six variants | `dot_v1` (two accelerators), `dot_v1_1` (one accelerator of two groups), `dot_v2` to `dot_v6` (one group of linked units) |
| matvec | `matvec_v1` to `matvec_v6`, `matvec_acc_v1` and `matvec_acc_v2` (a seeded fold) |
| shared movers | `dot_v1_2`, `mvt_v1_2_2` (W = 8) |
| a copy in L1, one step at a time | `mvt_v4_1_sequential` (mvt_v4 at W = 8 whose half 2 reads `A_T`, A copied transposed by the DMA one element a burst; every start waited on at once), `mvt_v4_1_1_sequential` (the same at int8 in, int32 out: x sliced 2 from a word, its output packed 2 to one) |
| the column form, no copy | `mvt_v5_sequential` (mvt_v4 at int8 whose half 2 is one seeded `Mac` of 8 lanes on n, y2 broadcast to every lane and x2 its seed, A read a strip of 8 columns at a time; sequential), `mvt_v5_2_sequential` (the same with an unseeded `Mac` whose 8 sums go through the link `tmp2` into a `SimdLanes` `vadd_x2` adding x2; one group, sequential) |
| bicg | `bicg_v2_1_sequential` (bicg at int8 in, int32 out: q in the row form on `matvec`, s in the column form, one unseeded `Mac` of 8 lanes on its own accelerator with r broadcast to every lane, A read a strip of 8 columns at a time; sequential), `bicg_v3` (bicg's one pass over A at M = 64, N = W = 32, int8 in, int32 out: one group of two chains on one reader of A forked to both (D189), q's `SimdLanes` `mul` linked into a `TreeAccumulate` `sum` whose output is packed 2 to a word, s's `Mac` of 32 lanes with r sliced 8 from a word and broadcast; a JOBS per chain, `JOBS_SUM` and `JOBS_MAC`), `bicg_v4` (the one pass at 64 × 64, W = 4: s's 64 sums in the `Mac`'s bank of R = 16 rows of 4 (D191), its output drained a row at a time at the job's end, r read once a row and held (D190), A and p sliced 2 from a word; `ROWS`), `bicg_v4_1` (the same in two strips of R = 8 rows, q's seed carried from the first strip to the second through L1, 0 on the first (D192); `ROWS` and `SUM_CARRY`) |

## Refreshing a folder

From a snax-forge checkout next to this one, with the folder cleared first (gen-gvsoc leaves a file it no longer writes in place):

    pixi run sandbox recipes/elementwise/vecadd_v1.json
    pixi run design out/sandbox/vecadd_v1/2_bind.snaxdfg --platform platforms/snax_forge.json
    pixi run gen-gvsoc out/design/vecadd_v1/design_point.json --out ../snax-gvsoc/forge/vecadd_v1

- The design step reads the sandbox's last step, `out/sandbox/<design>/<n>_<transform>.snaxdfg`.
- `rowsum_v2_padded` is `rowsum_v2` with `--set memory.passes.layout=padded_rows` on the design step; `mvt_v1_2_2` is its recipe with `--set W=8` on the sandbox step; `mvt_v4_1_sequential` is `mvt_v4_1` with `--set design.schedule=sequential` on the design step, and each `_sequential` folder likewise.
- Commit the folder as written, then bump snax-forge's submodule so its test compares against it.
- `make regress` runs every folder through the generic app, so a new folder needs nothing else.

## How it runs

`make regress` runs every folder twice (`tests/snax/regress.py`):

- `forge.<design>`: the generic app builds `main.c` (`make -C sw/apps/forge DESIGN=<design>`), `snax_hjson` runs it on the folder's cluster file with the traces `manifest.json` names, and each `forge counter` line must equal its unit's run line.
- `forge_quiet.<design>`: the quiet build, `forge_quiet.elf`, a plain run that must exit 0.

No model is compiled for a design point: `vecadd_v1` runs on the build's platform tree, the others on their JSON config, with gvrun's warning that the platform tree does not match.
