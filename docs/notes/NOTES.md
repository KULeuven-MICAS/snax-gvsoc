# SNAX-GVSoC notes

What SNAX-GVSoC was measured to do against snax_cluster's RTL and against GVSoC itself: the facts that still hold, each with the commit, program or fixture it was measured on. The step log they came from (SG0 to PACK0) is in git history; the decisions are snax-forge's (`docs/DECISIONS.md`), the events and traces `docs/EVENTS.md`, each component's rules its own comments.

## Pins

| What | Commit |
|---|---|
| GVSoC and its folded submodules | `UPSTREAM.md` |
| snax_cluster: the copy in `sw/`, and the RTL compared against | `sw/README.md`, "Pin" |
| common_cells, the TCDM arbiter | `v1.40.0` (`1281545`), in the RTL build's `Bender.lock` |

## The core and its timing

- **The cluster CSRs.** snax_cluster's start-up code reads the cluster base and {core count, index} from CSRs 0xBC1 to 0xBC3; the Snitch model declares them read-only, as the RTL (core 8 reads 0xBC3 = 0x00090008; snax_cluster `8ebd422`'s 17 plain tests).
- **SNAX CSRs.** 0x3C0 to 0x5FF go out as 32-bit IO requests on port `snax_csr` at 4 × the CSR number; an accelerator's stop at 0x5FD, as 0x5FE and 0x5FF go to the cluster's top-level CSR port (snax_cluster `cf4b0002`). `csrrw` / `csrrwi` read only when `rd` is not `x0`; the set and clear forms are a read then a write, as on the RTL since snax_cluster #657 (`9fbf35d`; `snax-csr`: 110 accesses, 0 errors). A pending write stalls the instruction until its answer (the shell's held start); a pending read is fatal, a refused access ends the run.
- **Loads (D125).** One integer load in flight (`int_loads_in_flight` 1, the RTL's `num_int_outstanding_loads: 1`); load to next load 4 cycles from L1 and 14 from DRAM (`core_latency` `tcdm` 2, `narrow` 6). A load answered pending lets the core go on until the next memory access or a use of its register, on the Snitch core's own scoreboard. On `snax-alu`'s check loop: 44 cycles per element against the RTL's 45 (snax_cluster `9fbf35d`).
- **Instruction fetch (open item 65).** The RTL's L0 cache prefetches the next line and taken branches' targets, GVSoC's `Hierarchical_cache` does not: SNAX-GVSoC misses more lines, for fewer cycles each. A start write and the loads after it in one cache line (`.balign 32`) took `core-tcdm`'s `core_vs_reader` from 17 to the RTL's 18.
- **The core's other timing (open items 66, 67, 70, 71).** `dmstati` polled every 2 cycles against the RTL's 5 (`snax-alu`'s DMA wait at 128 elements −20%, 0% to −3% from 1024); a SNAX CSR poll 6 against 5; atomics to DRAM one access here, a read-modify-write through the RTL testbench's `axi_riscv_atomics_wrap` (the exit's barrier about 50 cycles shorter). A store or AMO after a pending L1 load waits for its data; an L1 load after a DRAM load reaches the crossbar up to 13 cycles early. No measured loop has either.
- **The host.** GVSoC's HTIF polls `tohost` every 1000 cycles, a byte per request on four pollers' data ports; with `htif_poll_backdoor` (the SNAX targets) the poll is zero-time through `debug_mem_access`, same value and period (`dma-timing`'s `l2l1 4x800`: done 80, busy 65; RTL 84, 65). A `printf` waits on the host's answer, on that 1000-cycle grid.
- **Boot.** snRuntime zeroes `.bss` before `main`: a larger `.bss` moves the program's start (about 470 of 500 cycles when snax-forge's generated program replaced vecadd's hand-written one).
- **`snax-alu`, the baseline** (snax_cluster `9fbf35d`; the program and its target are gone since CLN1, the core's parameters above stay). RTL / SNAX-GVSoC, up to the read of CSR 982: 6713 / 6661 at 128 elements, 47495 / 46552 at 1024, 187285 / 183268 at 4096 (−1%, −2%, −2%); check loop −2%; barrier +1% to +5%.

## The DMA

- **On the RTL** (snax_cluster `b2672f8`, iDMA `e859ffc`): `busy = L_rd + N_beats + 2`, `L_rd` 11 from DRAM and 5 from L1, one 64 B beat a cycle. `busy_o` (`DMA_BUSY`, `dmstati 2`, which `snrt_dma_wait_all` polls) drops before the write response. A 3-deep request FIFO, at most 3 bursts in flight per direction, a 3-beat buffer between reads and writes, bursts ending at the nearer 4 KiB boundary; the testbench DRAM takes 2 reads and 2 writes in flight. `DMA_BUF_W_STALL` and `DMA_BUF_R_STALL` are never set.
- **The model** (D121, `DMA_TIMING` in `snax/snax_hjson.py`): `read_latency` 5 and `hbm_latency` 6 (DRAM 11 on both), DRAM 64 B a cycle; `tcdm_write_latency` 2, a beat in L1 2 cycles after it leaves the DMA, which is done at the send; `one_cycle_per_stage`, the midend, backend and AXI read a cycle each. A beat reaches L1 16 cycles after its `dmcpyi` on both (`l2l1 1x64`).
- **Measured** (`dma-timing`, eight copies): `busy`, `r` and `w` equal the RTL's on every line (busy 14, 17, 26, 77, 141, 39, 65, 20); `done` 2 to 6 cycles under it, the core's issue and polling. `dma-timing` fails when the DMA's own timing moves (`read_latency` 6 gives 8 lines off).
- **Counters.** `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and `DMA_BUSY` from the iDMA's `busy`, `r_beats` and `w_beats`.
- **Not verified:** an L1-to-L1 copy, whose read and delayed write reach the crossbar in one cycle where the RTL's `axi_to_mem` takes one a cycle (open item 72); the DMA reading L1 (open item 73).

## The crossbar and the sparse interconnect

- **On the RTL** (snax_cluster `9fbf35d`, `sparse_interconnect/` and `sparse_interconnect_wrapper.sv.tpl`). snaxgen's `sparse_config` lists ports as `[width, granularity]`: each accelerator's ports per core, then `[1, 1]` per core, then `[1, 1]` for AXI; snax-alu's cluster `[[12, 1], [1, 1], [1, 1], [1, 1]]` is 15 inputs (SNAX 0 to 11, cores 12 and 13, AXI 14) on 32 banks of 64 bit. Bank `(addr >> 3) & 31`; input `j` of granularity `g` reaches only banks `b % g == j % g`.
- **The pick** (`snax/snax_sparse_arb.hpp`), per bank and cycle: the valid requests at the highest priority; the last pick again if it was refused by its bank (the lock); else the lowest above the last pick, else the lowest; an idle bank cycle restarts from the last input. Read data one cycle after the grant.
- **Checked against the RTL** (`tests/snax/sparse_arb/`, Verilator 5.024 in image `d3d8f5572ff4` on the elaborated `SparseInterconnect.sv`): 20000 cycles, seeds 1 to 3, on `[[12, 1], [1, 1], [1, 1], [1, 1]]`, `[[12, 1], [8, 8], [1, 1], [1, 1], [1, 1]]` and the model on the first ports only: 0 differences in nine runs (seed 1: 56885, 104766 and 42244 selections). Copies with one rule broken (no idle restart, no lock, priority ignored): 1534, 1244 and 8248 differences.
- **The priority bit.** A new request carries its lane queue's hint of the cycle before (a reader's count ≤ 1, a writer's ≥ `fifo_depth` − 1) and keeps it while resent; without `dynamicPriority` it is `higherStaticPriority`. A wire per SNAX port (`prio_<i>`); an unbound wire asks with 0, as the cores and AXI.
- **Inputs.** The SNAX ports drop a losing request and send it again; the cores and AXI hold it for the next cycle's arbitration. A read, AMO or LR/SC is answered a cycle after its grant plus the request's latency, a write at its grant; 1 to 8 bytes inside one bank word, one crossing a word refused; LR reservations per hart. LR/SC on the sparse RTL needed snax_cluster #658 (`05615e4`), which carries the user field to the banks' AMO shims.
- **The DMA's superbank.** 512 / 64 = 8 banks a superbank, 4 superbanks, `(addr >> 6) & 3`. On the RTL `mem_wide_narrow_mux` gives the DMA's beat every bank of its superbank for its cycle, granted at once, and refuses the narrow winner there, which keeps its turn. Here the `dma` port does the same, and a beat crossing a superbank line is refused. A cycle's arbitration runs after every event queued before the cycle, and the DMA's beats come from events queued a cycle or more ahead, so a beat comes first; a later one on a superbank already granted to a narrow request is fatal (no program has one).
- **Measured** (SG7, both targets against the RTL at `9fbf35d`): every compared counter equal. `stream-timing`'s `prio_queued` and `idle_restart` 6; `core-tcdm`'s `after_stores` 6 and `core_vs_reader` 18; `dma-tcdm`'s `dma_vs_reader` 264 (260 on its first run). In `dma_vs_reader` the DMA's beats land 3, 4, 6 and 7 cycles before the RTL's, all of it the DMA core's issue (open item 67).
- **Not used yet:** the AXI input (wired, no program sends through it on either side, open item 69); granularity above 1 (checked above, no target, open item 75); the iDMA as sparse ports (open item 74).

## The streamer

- **From the hjson** (`snax_cfg.py`): the streamer's CSRs first, from 960, then the accelerator's. Start, AGU pace, end rule and the round-robin order match the RTL: `stream-timing`'s five counters 0, 9, 9, 10, 12 equal (snax_cluster `b2672f8`, common_cells 1.40.0).
- **Per mover** a class each cycle, `busy` > `stall_xbar` > `stall_fifo` > `idle`.
- **The queue count.** A writer's push and pop share a cycle, push first, so its data queue holds two words where the RTL counts one; `qmax` reports the RTL's count.
- **Widths** (PACK0): a b-bit input port takes lanes × b / 64 words; each mover's spatial bounds multiply to its `num_channel`, and each datapath port's words equal its mover's `num_channel` (`snax_cfg.py` refuses the rest at load).

## The group and its datapaths

- **One rule on three sides.** The group control rule (`snax/snax_group.hpp`'s `SnaxGroupRule`, `snax/snax_group_rule.py`, snax-forge's Chisel `GroupRule`) is checked by the 23 group cases (`tests/snax/group/`), the unit cases (`tests/snax/unit/`) and the shell cases (`tests/snax/shell/`); the datapath classes (`snax/snax_datapath.hpp`) against NumPy's vectors (`tests/snax/datapath/`).
- **The shell.** A start while busy is answered pending and sent in E + 1; the counter is reset by an accepted start and counts the busy cycles (`snax-shell`: counter 17, the held start's span 19).
- **The arithmetic** (PACK0, on forge/'s int32 and int8 fixtures, `forge data: 0 errors`): an elementwise op at NumPy's result type of its inputs, then cast to the output's; a fold's lanes cast to its output's type before its tree; a signed type with uint64 refused (NumPy gives float64).
- **The counter** (B1x, every forge/ variant at W = 4 and 8): C§17's cycles plus the streamers' fill, 3 cycles, 2 for a unit with one input. `make regress` checks each forge/ run's counters against its tasks.

## The events and traces

`docs/EVENTS.md` has the lines; measured about them:

- **One file in simulation order.** Several `--trace` patterns into one file land in it in order, and a component's message from `stop()` lands last, so end-of-run counters go there. A trace file's name is relative to the work directory; on stdout a `printf` can split a trace line.
- **The core** writes `func` with the function's name without the instruction trace (all 31 of vecadd's SNAX CSR accesses resolved, FLOW3); its `state` and `func` lines are behind `CONFIG_GVSOC_ISS_SNAX_EVENTS`, on `snitch` only. The window snax-forge reports is the program's two `mcycle` reads, each of which the core writes as a line.
- **The iDMA** the SNAX targets build is `pulp/pulp/idma/` (`idma_fe_xdma.cpp`); `pulp/models/ips/pulp/idma_v2/` is an unused copy.
- **VCD.** `--vcd --event-tags=snax` named 98 SNAX signals on vecadd (FLOW3), each value set in its own cycle; `--vcd` changes neither `events.log` nor stdout.
- **Sizes** (vecadd at trace level `stall`, snax-forge open item 39): a grant is 180 B in `events.log` and 222 B in `trace.jsonl`; per output element 1.7 KB and 1.1 KB; GVSoC's line header is 55% of the beat lines' bytes.
- **Exit codes.** A program's exit code is not its error count (two wrong goldens: `forge errors: 2`, exit 1); snax-forge reads the counts from the printed lines.

## The comparison with snax_cluster's RTL

- **What is compared** (D123): each accelerator's `forge counter` and `forge data: 0 errors`, equal; the window (`forge cycles`) within about 10%. Questa gives Verilator's lines (GEN2b, snax_cluster #660: vecadd at N 64 and 512, 239 and 500 cycles, counters 19 and 131; vsum, 259 and 739, counters 67 and 515).
- **Where the window's gap lies.** Every counter is equal, so the accelerator's busy span is the same on both sides; the gap is in the cores and the DMA (the sections above). In GEN2b's runs, vecadd's RTL was 13 cycles longer at N 64 and 14 at 512, a fixed cost; vsum's +4 at 64 and −16 at 512.
- **The current set** of thirteen bundles, measured on vsim (snax_cluster #666, snax-forge #43): snax-forge's open item 95.

## GVSoC itself

- **Targets.** GVSoC reads a target twice, at `make build` and under gvrun, with different arch classes. The install's `gvrun` puts its own `targets` and `generators` first on `sys.path`, so an installed module shadows a `--target-dir` one: a generated target never takes an installed target's name. A target without its platform tree runs on the JSON config, with gvrun's warning (UPSTREAM.md); a property reaches the C++ through `gvsoc_config.json` with nothing compiled.
- **The TCDM** size, banks and bank width come from the hjson (`ClusterArch.Tcdm`); L1's size and base reach the program through `sw/generated/`, so changing them needs the program rebuilt, while banks alone keep the ELF.
- **The build.** `make build` recompiles `cluster_registers` every time (not looked into); CMake refuses a build folder made from another checkout. gvrun needs the image's `/opt/venv` Python (under `pixi run` it lacks `rich`). GVSoC runs with `werror: true`: any `force_warning` ends the run.
