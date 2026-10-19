# forge/

Accelerators from snax-forge's design points, one folder per design point,
as SNAX-GVSoC reads them since LNK2a (`docs/plans/LNK2a.md`): two hjson
files in snax_cluster's form, the hjson being the contract, run on the
installed `snax_hjson` target. A folder is the fixture of snax-forge's D128:
it lets this repo's regression run a design point without snax-forge.

In LNK2a round 1 the two hjson files and the manifest's edit are written by
hand, from GEN3's generated folders; snax-forge's writer replaces them in
round 2, after which snax-forge's tests compare a fresh run with the folder
byte for byte again. `include/` is still GEN3's generator's output,
untouched.

| Folder | Design point | Slot |
|---|---|---|
| `vecadd/` | `recipes/vecadd.json` (W = 4, N = 64) on `platforms/snax_alu.json` | 12 TCDM ports, `loopCount` |
| `vecmul/` | `recipes/vecmul.json` (W = 4, N = 64, `elementwise_mul`) on `platforms/snax_alu.json` | 12 TCDM ports, `loopCount` |
| `vsum/` | `recipes/vsum.json` (W = 1, N = 64, `accumulate`'s `chisel_accumulator`, T = N) on `platforms/snax_alu.json` | 2 TCDM ports, `loopCount`, `len` |

Each folder holds:

- `snax_alu.hjson`, the cluster file, named after the base platform:
  `sw/cfg/snax_alu_cluster.hjson` (the sparse interconnect) with the compute
  core's slot set for the design: `snax_tcdm_ports`,
  `sparse_interconnect_config`, `snax_num_rw_csr` (the shell's fields and
  start), `snax_num_ro_csr` (busy and the counter), and two `$ref`s into the
  accelerator file, `snax_streamer_cfg` and `snax_datapath_cfg`. The slot
  keeps `snax_acc_name: snax_alu`.
- `snax_alu_acc.hjson`, the accelerator file, named after its slot:
  `snax_streamer_cfg` (readers the input ports in the BRM's port order,
  writers the output ports) and `datapath`, the block the standard composite
  takes (`snax/snax_cfg.py` lists its fields, `snax/snax_unit_acc.py` builds
  it).
- `include/`: the headers a program drives it with
  (`streamer_csr_addr_map.h` and `<instance>_csr.h`).
- `manifest.json`: the design, the design point, the bound graph's symbols,
  the cluster file (`cluster`), the files, the unit's trace path, the CSR
  layout and each accelerator task's beats.

## How it runs

Never through `TARGETS`: nothing here is compiled (D128). gvrun runs the
installed `snax_hjson` on the cluster file:

    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson ...

The reader resolves the cross-file `$ref`s (relative to the cluster file),
the slot's datapath block gets the standard composite on the installed
components, and since its components are not those of the target's default
file, gvrun warns that the platform tree does not match and runs it on the
JSON config.
