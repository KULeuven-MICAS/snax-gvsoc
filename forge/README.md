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

One folder per integration feature (snax-forge's D195), each at the smallest size that shows it; types and ops are left to the datapath testbench (`tests/snax/datapath/`).

| Folder | What it carries |
|---|---|
| `vecadd_v1` | one accelerator of one group of one unit (`SimdLanes`, add, int64), at N = 64 so B lies on A's banks; the snax_hjson target's default and the cluster tests' |
| `vecadd_v1_1_w1` | one lane at int32: inputs sliced 2 from a word (`d_in`), the output packed 2 to one (`d_out`) |
| `axpy_v1` | a CSR scalar (`K1`, pinned to the unit's `k1`) and a padded tail |
| `rowsum_v2_padded` | `LaneAccumulate` over the `padded_rows` layout, 4 rows of 8 |
| `dot_v4` | a linked group, `Mac` into `TreeAccumulate` over a wire (depth 0), `JOB_BEATS` |
| `matvec_acc_v2` | two groups in one accelerator, a seeded `SerialAccumulate` fold, two tasks |
| `mvt_v1_2_2` | two groups (`mvt`, a link of depth 1, and `vadd`) on one streamer set whose movers they share, the port mux, four tasks |
| `mvt_v4_1_1_sequential` | A copied transposed by the DMA one element a burst, int8 in and int32 out, every start waited on at once (`sequential`) |
| `mvt_v5_sequential` | two accelerators in two streamer sets, a seeded `Mac` with y2 broadcast, A read a strip of 8 columns at a time |
| `mvt_v6` | the one pass over A: one reader forked to two chains, a seeded `Mac` bank of R = 8 rows (`ROWS`), y2 read once a row and held |
| `bicg_v4_1` | the one pass in two strips of a bank of R = 4 rows, q's seed carried from the first strip to the second (`CARRY`), A and p sliced 2 from a word, q packed 2 to a word |
| `atax_v4` | atax's one group at M = 4, N = 8, W = 4: t = A x from the sum over a held link into the `Mac` bank's broadcast `b` (R = 2 rows, `ROWS`), A read once and forked to `mul.a` and through a fork link of depth 4 to `mac.a` (`fork_links`), y = Aᵀ t; A and x sliced 2 from a word |

## Refreshing a folder

snax-forge's `tests/gen/test_fixture.py` makes each folder from its recipe and `--set` values, `FORGE_FIXTURES` in snax-forge's `tests/helpers.py`. By hand, from a snax-forge checkout next to this one, with the folder cleared first (gen-gvsoc leaves a file it no longer writes in place):

    pixi run sandbox recipes/elementwise/vecadd_v1.json
    pixi run design out/sandbox/vecadd_v1/2_bind.snaxdfg --platform platforms/snax_forge.json
    pixi run gen-gvsoc out/design/vecadd_v1/design_point.json --out ../snax-gvsoc/forge/vecadd_v1

- The design step reads the sandbox's last step, `out/sandbox/<design>/<n>_<transform>.snaxdfg`.
- A recipe param (`M=`, `N=`, `W=`, `R=`) goes to the sandbox step, a `memory.` or `design.` path to the design step; the sandbox's `--out out/sandbox/<folder>` names the design point after the folder.
- Commit the folder as written, then bump snax-forge's submodule so its test compares against it.
- `make regress` runs every folder through the generic app, so a new folder needs nothing else.

## How it runs

`make regress` runs every folder twice (`tests/snax/regress.py`):

- `forge.<design>`: the generic app builds `main.c` (`make -C sw/apps/forge DESIGN=<design>`), `snax_hjson` runs it on the folder's cluster file with the traces `manifest.json` names, and each `forge counter` line must equal its unit's run line.
- `forge_quiet.<design>`: the quiet build, `forge_quiet.elf`, a plain run that must exit 0.

No model is compiled for a design point: `vecadd_v1` runs on the build's platform tree, the others on their JSON config, with gvrun's warning that the platform tree does not match.
