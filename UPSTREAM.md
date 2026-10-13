# Upstream

This repository is a detached copy of [GVSoC](https://github.com/gvsoc/gvsoc)
at `93cedc4`, made on 2026-10-12. It is developed on its own and is never
merged or rebased from upstream (D116 in
[snax-forge](https://github.com/KULeuven-MICAS/snax-forge)).

## Upstream commits

| Path | Upstream | Commit | Date |
|---|---|---|---|
| `/` | [gvsoc/gvsoc](https://github.com/gvsoc/gvsoc) | `93cedc4cb2970a28ff38aef4393d8d69eae503a4` | 2026-09-25 |
| `config_tree/` | [gvsoc/config_tree](https://github.com/gvsoc/config_tree) | `d134f4100bffdc0de196f6672e005ff3b58ad083` | 2026-06-30 |
| `core/` | [gvsoc/gvsoc-core](https://github.com/gvsoc/gvsoc-core) | `731f80406b24653ea908f1f25a548cbe03bf5de7` | 2026-09-25 |
| `engine/` | [gvsoc/gvsoc-engine](https://github.com/gvsoc/gvsoc-engine) | `df1011495fc040615a81c4b2b061064a08e46acc` | 2026-09-22 |
| `gvrun/` | [gvsoc/gvrun](https://github.com/gvsoc/gvrun) | `84a40e04fd96af749bed31bc28a38f01de518718` | 2026-09-05 |
| `gvtest/` | [gvsoc/gvtest](https://github.com/gvsoc/gvtest) | `99db3b5bc5f8f5483558a655f87325e8044c0668` | 2026-07-28 |
| `pulp/` | [gvsoc/gvsoc-pulp](https://github.com/gvsoc/gvsoc-pulp) | `1af311ae1ab92f90a196a5236dddb0bb750d28f9` | 2026-09-24 |
| `pulpos/` | [gvsoc/pulpos](https://github.com/gvsoc/pulpos) | `4a4f9f2aaf244bcb4e4bb7fe276ebcf481213342` | 2026-09-24 |

## How the copy was made

GVSoC was cloned and checked out at `93cedc4`. One commit removed the seven
submodules and `.gitmodules`, then each submodule was folded in with
`git subtree add --prefix=<path> <upstream> <commit>`, keeping its history.
Only `main` was pushed. A folded file's older history uses paths without the
prefix, so it is read through the pin:
`git log 731f804 -- models/cpu/iss/src/csr.cpp`.

## License

GVSoC is Apache 2.0: the root `LICENSE`, and `core/`, `engine/`, `gvrun/`
and `pulp/` each carry the same license. `config_tree/`, `gvtest/` and
`pulpos/` ship no LICENSE file of their own. Upstream has no NOTICE file.
Files with a header of their own (e.g. `.gitlab-ci.yml`, SHL-0.51) keep it.
Files we add are Apache 2.0 too.

## Changed files

Every upstream file we edit gets one comment line near its top,
`Modified for SNAX-GVSoC (KU Leuven MICAS), see UPSTREAM.md`, and a row here
(Apache 2.0, section 4(b)). A replaced or removed file only gets a row.

| File | Change | Step |
|---|---|---|
| `README.md` | Replaced with a short SNAX-GVSoC README | SG0 P1 |
| `.github/workflows/build.yml` | Removed: upstream CI that builds every target on each push | SG0 P1 |
| `.github/CODEOWNERS` | Removed: named the upstream maintainer as owner of every file | SG0 P1 |
| `core/models/cpu/iss/include/cores/snitch/class.hpp` | Three CSR registers for snax_cluster's 0xBC1 to 0xBC3 | SG0 P3 |
| `core/models/cpu/iss/src/snitch/snitch.cpp` | 0xBC1 to 0xBC3 declared read-only, values from the core's properties | SG0 P3 |
| `pulp/pulp/snitch/snitch_core.py` | `Snitch` takes the cluster base, core count and core index as properties | SG0 P3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | Passes them to each Snitch core | SG0 P3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` takes `misa` and passes it to each Snitch core; `None` keeps the value the ISA string gives | SG1 P3 |
| `Makefile` | `snax/` added to `GVSOC_MODULES` | SG1 P3 |
| `core/models/cpu/iss/include/cores/snitch/class.hpp` | `SnaxCsr` and the `snax_csr` port: snax_cluster's accelerator CSRs 0x3C0 to 0x5FF | SG1 P4 |
| `core/models/cpu/iss/src/snitch/snitch.cpp` | The 0x3C0 to 0x5FF CSRs declared in a loop and sent out as IO requests | SG1 P4 |
| `pulp/pulp/snitch/snitch_core.py` | `Snitch.o_SNAX_CSR` binds that port | SG1 P4 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` takes `snax_acc`; `SnitchCluster` builds each accelerator and binds it to its core's `snax_csr` port | SG1 P5 |
| `core/models/cpu/iss/src/snitch/snitch.cpp` | `SnaxCsr::handle()` tests `rd = x0` against `ISS_NB_REGS`, the index the decoder gives it | SG1 P5 |
| `pulp/pulp/idma/fe/idma_fe_xdma.hpp`, `.cpp` | Wires `busy` (the state `dmstat 2` returns) and `r_beats` / `w_beats` (the AXI beats of each queued copy); unbound wires are not driven | SG2 P3 |
| `pulp/pulp/idma/snitch_dma.py` | `SnitchDma` takes `beat_size` (64) and gains `o_BUSY`, `o_R_BEATS`, `o_W_BEATS` | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/cluster_registers.cpp` | The perf counters of `snitch_cluster_peripheral.sv` count `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and `DMA_BUSY`; the other events count nothing | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/cluster_registers.py` | `ClusterRegisters` gains `i_DMA_BUSY`, `i_DMA_R_BEATS`, `i_DMA_W_BEATS` | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchCluster` binds the iDMA's wires to the cluster registers (not with Spatz) | SG2 P3 |
