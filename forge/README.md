# forge/

Accelerators from snax-forge's design points, one folder per design point,
as SNAX-GVSoC reads them since LNK2a (`docs/plans/LNK2a.md`, snax-forge
D134): three hjson files in snax_cluster's form, the hjson being the
contract, run on the installed `snax_hjson` target. A folder is the fixture
of snax-forge's D128: it lets this repo's regression run a design point
without snax-forge. Each is snax-forge's generator's output, checked in
untouched; snax-forge's `tests/gen/test_fixture.py` writes it again and
compares it byte for byte.

| Folder | Design point | Slot |
|---|---|---|
| `vecadd/` | `recipes/vecadd.json` (W = 4, N = 64) on `platforms/snax_alu.json` | 12 TCDM ports, `loopCount` |
| `vecmul/` | `recipes/vecmul.json` (W = 4, N = 64, `elementwise_mul`) on `platforms/snax_alu.json` | 12 TCDM ports, `loopCount` |
| `vsum/` | `recipes/vsum.json` (W = 1, N = 64, `accumulate`'s `chisel_accumulator`, T = N) on `platforms/snax_alu.json` | 2 TCDM ports, `loopCount`, `len` |
| `vsum_tree/` | `recipes/vsum_tree.json` (W = 4, N = 64, `accumulate`'s `chisel_adder_tree`, T = N) on `platforms/snax_alu.json` | 5 TCDM ports, `loopCount`, `len` |

Each folder holds:

- `snax_alu.hjson`, the cluster file, named after the base platform: its
  source (snax-forge's `platforms/snax_alu.hjson`, a copy of
  `sw/cfg/snax_alu_cluster.hjson`, the sparse interconnect) with the
  platform's values written back and the compute core's slot set for the
  design: `snax_tcdm_ports`, `sparse_interconnect_config`,
  `snax_num_rw_csr` (the shell's fields and start), `snax_num_ro_csr` (busy
  and the counter), and two `$ref`s to the whole of the other two files.
  The slot keeps `snax_acc_name: snax_alu` (the platform's
  `accelerator_slot`).
- `snax_alu_streamer.hjson`, the streamer file, named after the slot: the
  streamer template lowered for the design point (readers the input ports
  in the BRM's port order, writers the output ports).
- `snax_alu_acc.hjson`, the accelerator file: the datapath block the
  standard composite takes (`snax/snax_cfg.py` lists its fields,
  `snax/snax_unit_acc.py` builds it).
- `include/`: the headers a program drives it with
  (`streamer_csr_addr_map.h` and `<instance>_csr.h`).
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
  unit's trace path, the CSR layout and each accelerator task's beats.

Every hjson and C file starts with a comment naming the design point; the
rest of an hjson file is JSON, which hjson reads.

## Refreshing a folder

From a snax-forge checkout next to this one (snax-forge README, "Refreshing
a fixture"), the folder cleared first:

    pixi run sandbox recipes/vecadd.json
    pixi run design out/sandbox/vecadd/2_bind.snaxdfg --platform platforms/snax_alu.json
    pixi run gen-gvsoc out/design/vecadd/design_point.json --out ../snax-gvsoc/forge/vecadd

(the same with `vecmul`, `vsum` or `vsum_tree`), then commit the folder as written and
bump snax-forge's submodule so its test compares against it. `make regress`
runs every folder with the generic app, so a new folder needs nothing else.

## How it runs

Never through `TARGETS`: no model is compiled (D128). The program is built
by the generic app, and gvrun runs the installed `snax_hjson` on the cluster
file:

    make -C sw/apps/forge DESIGN=vecadd
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

The reader resolves the `$ref`s (relative to the cluster file), the slot's
datapath block gets the standard composite on the installed components, and
since its components are not those of the target's default file, gvrun
warns that the platform tree does not match and runs it on the JSON config.
