# forge/

Generated accelerators from snax-forge (GEN3, `docs/plans/GEN3.md`): one
folder per design point, each holding exactly what snax-forge's GVSoC
generator (`pixi run gen-gvsoc`, snax-forge `snax_forge/gen/`) wrote for it,
untouched. A folder is the fixture of snax-forge's D128: it lets this repo's
regression run a generated accelerator without snax-forge, and snax-forge's
tests generate the same design point again and compare it with the folder
byte for byte, so neither repo's CI needs the other.

| Folder | Design point | Target |
|---|---|---|
| `vecadd/` | `recipes/vecadd.json` (W = 4, N = 64) on `platforms/snax_alu.json` | `forge_vecadd` |

Each folder holds the composite (`forge_<design>_acc.py`), the target
(`forge_<design>.py`: `snax_alu`'s board with the composite in its
accelerator slot), the headers a program drives it with (`include/`:
`streamer_csr_addr_map.h` and `<instance>_csr.h`) and `manifest.json` (the
target, the files, the `--target-dir`s, the unit's trace path, the bound
graph's symbols, the CSR layout and each accelerator task's beats). Every
file names the design point by its path from snax-forge's root.

## Refreshing a folder

By hand, when snax-forge's generator or the design point changes; the diff
is the check. In snax-forge's image, from snax-forge checked out next to
this repo, with snax-gvsoc built and installed at snax-forge's
`out/snax-gvsoc/install` (`make -C gvsoc build`), so the install check runs:

    pixi run sandbox recipes/vecadd.json
    pixi run design out/sandbox/vecadd/2_bind.snaxdfg --platform platforms/snax_alu.json
    pixi run gen-gvsoc out/design/vecadd/design_point.json --out ../snax-gvsoc/forge/vecadd \
        --install out/snax-gvsoc/install

Then commit the folder as written, and bump snax-forge's submodule so its
fixture test compares against it.

## How it runs

Never through `TARGETS`: nothing here is compiled (D128). gvrun reads a
folder with `--target-dir=<folder>` (each of the manifest's `target_dirs`,
relative to the folder), after the install's own target dirs, and runs the
generated target on the installed components. The target has no platform
tree, so gvrun warns `no platform tree, using the JSON config` and runs it
on the JSON config path.
