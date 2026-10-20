# Upstream

This repository is a detached copy of [GVSoC](https://github.com/gvsoc/gvsoc)
at `93cedc4`, made on 2026-10-12. It is developed on its own and is never
merged or rebased from upstream (D116 in
[snax-forge](https://github.com/KULeuven-MICAS/snax-forge)).

`sw/` is a pinned copy of snax_cluster's software, not of GVSoC: its pin,
licences and sync are in `sw/README.md`.

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
| `core/models/cpu/iss/src/snitch/snitch.cpp` | The 0x3C0 to 0x5FF CSRs declared in a loop and sent out as IO requests; a refused access (`IO_REQ_INVALID`) ends the run with its own message, a pending or denied answer with another | SG1 P4, housekeeping after SG6 |
| `pulp/pulp/snitch/snitch_core.py` | `Snitch.o_SNAX_CSR` binds that port | SG1 P4 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` takes `snax_acc`; `SnitchCluster` builds each accelerator and binds it to its core's `snax_csr` port | SG1 P5 |
| `core/models/cpu/iss/src/snitch/snitch.cpp` | `SnaxCsr::handle()` tests `rd = x0` against `ISS_NB_REGS`, the index the decoder gives it | SG1 P5 |
| `pulp/pulp/idma/fe/idma_fe_xdma.hpp`, `.cpp` | Wires `busy` (the state `dmstat 2` returns) and `r_beats` / `w_beats` (the AXI beats of each queued copy); unbound wires are not driven | SG2 P3 |
| `pulp/pulp/idma/snitch_dma.py` | `SnitchDma` takes `beat_size` (64) and gains `o_BUSY`, `o_R_BEATS`, `o_W_BEATS` | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/cluster_registers.cpp` | The perf counters of `snitch_cluster_peripheral.sv` count `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and `DMA_BUSY`; the other events count nothing | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/cluster_registers.py` | `ClusterRegisters` gains `i_DMA_BUSY`, `i_DMA_R_BEATS`, `i_DMA_W_BEATS` | SG2 P3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchCluster` binds the iDMA's wires to the cluster registers (not with Spatz) | SG2 P3 |
| `pulp/pulp/chips/snitch/snitch.py` | `Soc` takes `hbm_latency` from the arch when a target sets it; the default stays 100 (0 with Spatz) | SG2 P4 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` takes `dma`, `SnitchDma` arguments that replace the cluster's defaults | SG2 P4 |
| `pulp/pulp/idma/be/idma_be_axi.hpp`, `.cpp` | `read_latency` (0 when absent) added to each read burst's latency | SG2 P5 |
| `pulp/pulp/idma/be/idma_be_tcdm.hpp`, `.cpp` | `read_latency` (0 when absent) paid once per read stream: a line read on the cycle after the previous one does not pay it again | SG2 P5 |
| `pulp/pulp/idma/snitch_dma.py` | `SnitchDma` takes `read_latency` (0) | SG2 P5 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchClusterTcdm` takes `nb_snax_ports` and builds `SnaxTcdmXbar` (`snax/`) in front of the same banks; `SnitchCluster` counts the accelerators' `nb_tcdm_ports` and binds each one's ports to it | SG3 P3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchClusterTcdm` takes `snax_port_names`; `SnitchCluster` names each SNAX port `snax_acc<core>.<name>` from the accelerator's `tcdm_port_names` | SG3 P5 |
| `core/models/cpu/iss/include/lsu.hpp`, `include/lsu_implem.hpp`, `src/lsu.cpp` | `Lsu` takes `int_loads_in_flight` from the core's properties (0, no limit, when absent; only 0 and 1 modelled): with 1, a load stalls the core until the previous load's data is back (`load_wait`, `load_issued` in `load` and `load_signed`) | SG5 P5 |
| `pulp/pulp/snitch/snitch_core.py` | `Snitch` takes `int_loads_in_flight` (0) as a property | SG5 P5 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` takes `core`, `Snitch` arguments that replace the cores' defaults, and `core_latency`, cycles added on each core's data path to the TCDM (`tcdm`) and out of the cluster (`narrow`, the map to `narrow_axi`) | SG5 P5 |
| `Makefile` | `regress` (runs `tests/snax/regress.py`: every program exits 0, SG6); `sw` (`make -C sw`) and `sync-snax-cluster` (`sw/sync.py`), which replace `regress-plain` and the snax_cluster checkout | SG5 P6, CI1 |
| `core/models/cpu/iss/include/isa/priv.hpp` | `csrrc` with `rs1` = `x0`, and `csrrsi` / `csrrci` with `uimm` = 0, write nothing (Zicsr), as `csrrs` already did; for every core | SG6 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchClusterTcdm` binds a priority wire per SNAX port to `SnaxTcdmXbar`; `SnitchCluster` binds an accelerator's `o_TCDM_PRIORITY` to it when the accelerator has one | SG7 step 6 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` (both arch paths) takes `snax_interconnect` (`plain`) and `snax_sparse_config`; `SnitchCluster` lists the accelerators' sparse ports in core order (`[nb_tcdm_ports, 1]` by default, as snaxgen) and `SnitchClusterTcdm` passes both to `SnaxTcdmXbar` | SG7 step 7 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | With SNAX ports, `SnitchCluster` sends each core's TCDM and `tcdm_alias` maps (with their latency) to the SNAX crossbar's input after the SNAX ports, in core order, and `narrow_axi`'s TCDM map straight to its last input (AXI), not through `pe0_ico`; these inputs hold a losing request and are `[1, 1]` each in the sparse config. `SnitchClusterTcdm` takes `snax_holds` | SG7 round 3 step 3 |
| `core/models/cpu/iss/include/lsu.hpp`, `include/lsu_implem.hpp`, `src/lsu.cpp`, `src/snitch/decode.cpp` | With `int_loads_in_flight` set on the Snitch core, a load answered `IO_REQ_PENDING` no longer stalls the core: its register is marked not ready in the core's `scoreboard_reg_valid`, and an instruction on that register (`int_offload_exec`), the next load, store or AMO stall until the response (`wait_for_load`); the response sets the register's and the next load's ready cycle (`pending_load_response`) | SG7 round 3b step 2 |
| `core/models/cpu/iss/include/htif.hpp`, `src/htif.cpp` | With the core property `htif_poll_backdoor`, the host's `tohost` poll (the read every 1000 cycles and its clear) goes through the zero-time debug backdoor behind the core's data port (`vp/debug_mem.hpp`), not as requests on the port | SG7 round 3b step 3 |
| `pulp/pulp/snitch/snitch_core.py` | `Snitch` and `Snitch_fp_ss` take `htif_poll_backdoor` (False) as a property | SG7 round 3b step 3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `SnitchCluster` gives each FP subsystem the `htif_poll_backdoor` of `ClusterArch.core` | SG7 round 3b step 3 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` (both arch paths) takes `snax_dma_data_width`; with SNAX ports and it, `SnitchClusterTcdm` sends the DMA input (the iDMA's TCDM port, `wide_axi`'s TCDM and `tcdm_alias` maps) to the SNAX crossbar's `dma` port with `superbank_banks` = `dma_data_width / (8 * bank_width)` instead of `DmaInterleaver`, and `SnitchCluster` checks the DMA's `tcdm_width` is one superbank | SG7 round 4 step 3 |
| `pulp/pulp/idma/be/idma_be_tcdm.hpp`, `.cpp` | `tcdm_write_latency` (0 when absent): a line written to the local memory reaches it that many cycles after it leaves the DMA, and is acknowledged when it leaves | SG7 round 4 follow-up |
| `pulp/pulp/idma/me/idma_me_2d.hpp`, `.cpp`, `be/idma_be.hpp`, `.cpp`, `be/idma_be_axi.hpp`, `.cpp` | `one_cycle_per_stage` (false when absent): the midend takes a transfer, the backend splits it and the AXI back-end sends a read burst from the cycle after it arrived, also when the stage's event is already queued for that cycle | SG7 round 4 follow-up |
| `pulp/pulp/idma/snitch_dma.py` | `SnitchDma` takes `tcdm_write_latency` (0) and `one_cycle_per_stage` (False) | SG7 round 4 follow-up |
| `core/models/cpu/iss/src/snitch/snitch.cpp`, `include/cores/snitch/class.hpp` | A SNAX CSR write answered `IO_REQ_PENDING` stalls the core until the block's response (`snax_csr_response`: `stalled_dec`, `insn_terminate`, as the LSU's pending store); the request's data is a member (`snax_csr_data`), not a local; a pending read still ends the run | GEN3 step 2 |
| `engine/python/gvsoc/runner_gvrun2.py` | A target without `libplatform_tree_<target>.so` (one no build made, e.g. read from `--target-dir`) runs on the JSON config path with one warning line on stderr, as on a signature mismatch, instead of stopping (`Missing platform_tree library`) | GEN3 round 1b F1 |
| `pulp/pulp/snitch/snitch_cluster/snitch_cluster.py` | `ClusterArch` (both arch paths) takes the TCDM's size, bank count and bank width and the peripherals' and zero memory's sizes (`tcdm_size`, `tcdm_banks`, `tcdm_bank_width`, `periph_size`, `zero_mem_size`; the build path reads them from its properties), today's values as defaults; `ClusterArch.Tcdm` takes the first three and holds `nb_banks` instead of the superbank split; the peripherals and the zero memory (and their aliases) follow the TCDM by size | LNK2a step 1 |
| `pulp/pulp/snitch/snitch_cluster/cluster_registers.py` | `gen` writes the `cluster_periph` headers beside the old ones and replaces them only when they differ, so a build with nothing changed recompiles nothing | housekeeping 2 |
| `Makefile` | Every `cmake` is `$(CMAKE)`, so a caller names the CMake the build uses (snax-forge's `gvsoc/Makefile` from pixi) | FLOW3 step 1 |
| `gvrun/bin/gvrun` | Without the venv, runs `gvrun` on `$GVRUN_PYTHON` (default `python3`), so a caller whose `python3` lacks GVSoC's packages (pixi's) names the Python | FLOW3 step 1 |
