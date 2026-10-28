# forge/

Accelerators from snax-forge's design points, one folder per design point,
as SNAX-GVSoC reads them since LNK2a (`docs/plans/LNK2a.md`, snax-forge
D134): three files, the cluster and streamer files in snax_cluster's hjson
form and `accelerator.json` (snax-forge C§17, D145), the contract, run on
the installed `snax_hjson` target. A folder is the fixture of snax-forge's
D134: it lets this repo's regression run a design point without snax-forge.
Each is snax-forge's generator's output, checked in untouched; snax-forge's
`tests/gen/test_fixture.py` writes it again and compares it byte for byte.
All seventeen are snax-forge's branch `ry/blk1-2` at `a81a9d2` (M13 B1 R3:
`accelerator.json` with the per-group CSRs START, JOBS, JOB_BEATS, STATUS,
COUNTER, a TreeAccumulate's `params.op` `add`, and `dot_1/`, one
accelerator of two groups).

| Folder | Design point | Slot |
|---|---|---|
| `vecadd/` | `recipes/vecadd.json` (W = 4, N = 64, int64) on `platforms/snax_forge.json` | 12 TCDM ports, `START`, `JOBS` |
| `vecmul/` | `recipes/vecmul.json` (W = 4, N = 64, `elementwise_mul`) on `platforms/snax_forge.json` | 12 TCDM ports, `START`, `JOBS` |
| `vsum/` | `recipes/vsum.json` (W = 1, N = 64, `accumulate`'s `chisel_accumulator`, T = N) on `platforms/snax_forge.json` | 2 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `vsum_tree/` | `recipes/vsum_tree.json` (W = 4, N = 64, `accumulate`'s `chisel_adder_tree`, T = N) on `platforms/snax_forge.json` | 5 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `matadd/` | `recipes/matadd.json` (W = 4, M = 8, N = 16, int32 since PACK0 R3, two per word, the first 2-D bind: the row loop and the column beats, two temporal loops per streamer) on `platforms/snax_forge.json` | 6 TCDM ports, `START`, `JOBS` |
| `rowsum/` | `recipes/rowsum.json` (W = 4, M = 8, N = 64, `accumulate`'s `chisel_adder_tree`, T = N / W = 16: a restart every row, eight sums) on `platforms/snax_forge.json` | 5 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `rowsum_serial/` | `recipes/rowsum_serial.json` (W = 1, M = 4, N = 16, `accumulate`'s `chisel_accumulator`, T = N = 16: four sums of 16) on `platforms/snax_forge.json` | 2 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `vecadd_i32/` | `recipes/vecadd_i32.json` (W = 4, N = 64, A, B, C int32: two per word) on `platforms/snax_forge.json` | 6 TCDM ports, `START`, `JOBS` |
| `vecmul_i32/` | `recipes/vecmul_i32.json` (W = 4, N = 64, A, B, C int32, `elementwise_mul`) on `platforms/snax_forge.json` | 6 TCDM ports, `START`, `JOBS` |
| `vecmul_i32_i64/` | `recipes/vecmul_i32_i64.json` (W = 4, N = 64, A, B int32 into C int64, `elementwise_mul`: the product at int32, the op type, sign-extended into C) on `platforms/snax_forge.json` | 8 TCDM ports (2 + 2 + 4), `START`, `JOBS` |
| `vsum_tree_i32/` | `recipes/vsum_tree_i32.json` (W = 4, N = 64, A int32 into out int64, `chisel_adder_tree`, T = N) on `platforms/snax_forge.json` | 3 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `vecadd_i8/` | `recipes/vecadd_i8.json` (W = 8, N = 64, A, B, C int8: eight per word) on `platforms/snax_forge.json` | 3 TCDM ports, `START`, `JOBS` |
| `vsum_tree_i8/` | `recipes/vsum_tree_i8.json` (W = 8, N = 64, A int8 into out int64, `chisel_adder_tree`, T = N) on `platforms/snax_forge.json` | 2 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `vecadd_n7/` | `recipes/vecadd_n7.json` (W = 4, N = 7, int64: a tail, two firings, A, B and C padded to 8, D144) on `platforms/snax_forge.json` | 12 TCDM ports, `START`, `JOBS` |
| `vsum_tree_n21/` | `recipes/vsum_tree_n21.json` (W = 4, N = 21, int64, `chisel_adder_tree`: six firings, A padded to 24 with zeros) on `platforms/snax_forge.json` | 5 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `rowsum_3x7/` | `recipes/rowsum_3x7.json` (W = 4, M = 3, N = 7, int64, `chisel_adder_tree`, T = 2: each row padded to 8) on `platforms/snax_forge.json` | 5 TCDM ports, `START`, `JOBS`, `JOB_BEATS` |
| `dot_1/` | `recipes/dot_1.json` (W = 4, N = 64, int64: `elementwise_mul` into `tmp0` in L1, then `chisel_adder_tree` over it, T = N / W; `encapsulate` puts both into the accelerator `dot`, snax-forge D148) on `platforms/snax_forge.json` | 17 TCDM ports (readers mul.a, mul.b, sum.a, writers mul.out, sum.out); groups `mul` (`START`, `JOBS`, `STATUS`, `COUNTER`) and `sum` (with `JOB_BEATS`), a task each, the other group's movers at temporal bound 0 |

Each folder holds:

- `snax_forge.hjson`, the cluster file, named after the base platform: its
  source (snax-forge's base cluster `platforms/snax_forge_cluster.hjson`,
  from snax_cluster's `cfg/snax_alu_cluster.hjson`, its names snax-forge's,
  the sparse interconnect) with the
  platform's values written back, the cluster renamed `snax_forge_cluster`
  (`name` and its entry in `bender_target`) and the compute core's only
  slot set for the design: `snax_acc_name: snax_forge` (the platform's
  `accelerator_slot`, so a generated accelerator takes no name of
  snax_cluster's own), the slot's `bender_target` dropped,
  `snax_tcdm_ports`, `sparse_interconnect_config`, `snax_num_rw_csr` (the
  accelerator's read-write CSRs), `snax_num_ro_csr` (its read-only ones,
  STATUS and COUNTER per group), then
  `snax_disable_csr_manager: true` and `snax_forge_rtl: "rtl/files.f"`
  (the RTL's file list in snax-forge's bundle, for snax_cluster; this repo
  ignores both), and two `$ref`s to the whole of the other two files
  (`snax_datapath_cfg`: `accelerator.json`).
- `snax_forge_streamer.hjson`, the streamer file, named after the slot: the
  streamer template lowered for the design point (readers the input ports
  in the BRM's port order, writers the output ports), each mover's
  `spatial_bounds` in 64-bit words (`[S_0 / k, S_1, ...]`, k the elements
  of the port's dtype a word holds) and its `num_channel` their product.
- `accelerator.json`, the accelerator's one description: its groups, each
  with START, JOBS, STATUS, COUNTER, its unit (datapath `ElementwiseLanes`
  or `TreeAccumulate`, each port's dtype and lanes, `opType`, `params`,
  latency and II, a fold's JOB_BEATS) and the CSRs' offsets, which the
  standard composite takes (`snax/snax_cfg.py` reads and checks it,
  `snax/snax_unit_acc.py` builds a shell per group and a unit per unit).
- `include/`: the headers a program drives it with
  (`streamer_csr_addr_map.h` and `<name>_csr.h`, every CSR by its C§17
  name, `ACC_RW_START`, `ACC_RW_JOBS`, `ACC_RW_JOB_BEATS`, `ACC_RO_STATUS`,
  `ACC_RO_COUNTER`; with several groups the group's name after the access,
  `DOT_RW_MUL_START` ... `DOT_RO_SUM_COUNTER`), and the runtime's
  view of the cluster (`snitch_cluster_cfg.h` and
  `snitch_cluster_addrmap.h`, as snax_cluster's templates render them from
  the cluster file).
- `main.c` (GEN2a, FLOW3, snax-forge D135): the program, the design point's
  task list on snRuntime: `mcycle` read at main's entry, each step on the
  core that owns its component, a barrier where another core goes on, each
  accelerator task's counter stored after its wait, then `forge_check()` on
  the accelerator's core: `mcycle` read first and `forge cycles:` printed
  (the program's window), then the self-check, every output against its
  golden and one `forge counter <task>:` line per accelerator task; main
  returns the error count. No task marks. The generic app `sw/apps/forge/`
  builds it.
- `data.h`: its data, from snax-forge's datagen: the inputs from the
  kernel's `make_inputs` (seed 0), each output zeroed with its
  `<name>_golden` from the reference executor, each array padded to whole
  DMA beats and aligned to one.
- `manifest.json`: the design, the design point, the bound graph's symbols,
  the cluster file (`cluster`), the files, the program (`main.c`), the
  unit's trace path (`snax_acc0/unit`; with several groups the
  accelerator's, `snax_acc0`), the CSR layout (each CSR's header name -> its
  number) and each accelerator task's beats and CSR values (its group's
  JOBS, JOB_BEATS), with several groups also its unit's trace path
  (`snax_acc0/unit_<unit>`).

Every hjson and C file starts with a comment naming the design point; the
rest of an hjson file is JSON, which hjson reads. `accelerator.json` is
plain JSON, its `design_point` key naming the source.

## Refreshing a folder

From a snax-forge checkout next to this one (snax-forge README, "Refreshing
a fixture"), the folder cleared first (gen-gvsoc leaves a file it no longer
writes in place):

    pixi run sandbox recipes/vecadd.json
    pixi run design out/sandbox/vecadd/2_bind.snaxdfg --platform platforms/snax_forge.json
    pixi run gen-gvsoc out/design/vecadd/design_point.json --out ../snax-gvsoc/forge/vecadd

(the same with every folder's recipe; the design step reads the sandbox's
last step, `out/sandbox/<design>/<n>_<transform>.snaxdfg`: the recipes of
`matadd`, `rowsum`, `rowsum_serial` and `rowsum_3x7` have three steps,
`dot_1`'s five, the last `5_encapsulate.snaxdfg`), then commit the
folder as written and
bump snax-forge's submodule so its test compares against it. `make regress`
runs every folder with the generic app, so a new folder needs nothing else.

## How it runs

Never through `TARGETS`: no model is compiled (D134). The generic app
builds the program and its own runtime (`libsnRuntime.a`, beside the ELF)
against the folder's two cluster headers, so the stacks sit at the end of
the design's L1; gvrun runs the installed `snax_hjson` on the cluster file:

    make -C sw/apps/forge DESIGN=vecadd
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

The reader resolves the `$ref`s (relative to the cluster file), the slot's
`accelerator.json` gets the standard composite on the installed components.
The target's default file is `vecadd/`'s cluster (installed from here,
snax-forge D126), so
`vecadd/` runs on the build's platform tree; for the others gvrun warns that
the platform tree does not match and runs them on the JSON config.
