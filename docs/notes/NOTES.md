# SNAX-GVSoC notes

What SNAX-GVSoC was measured to do against snax_cluster's RTL and against GVSoC itself, only what still holds; each component's rules are in its comments, open items in snax-forge's `docs/STATUS.md`.

## Versions compared against

GVSoC in `UPSTREAM.md`; snax_cluster (the `sw/` copy and the RTL) in `sw/README.md`; common_cells, the TCDM arbiter, `v1.40.0` in the RTL build's `Bender.lock`.

## The core and its timing

- **CSRs.** The cluster base and {core count, index} are read-only CSRs 0xBC1 to 0xBC3, as on the RTL. SNAX CSRs 0x3C0 to 0x5FF go out as 32-bit IO requests on port `snax_csr`, at 4 × the CSR number; an accelerator's stop at 0x5FD, 0x5FE and 0x5FF go to the cluster's CSR port. `csrrw` and `csrrwi` read only when `rd` is not `x0`; the set and clear forms read, then write, as on the RTL (`snax-csr`: 0 errors). A pending write stalls until its answer; a pending read is fatal.
- **Loads.** One integer load in flight; load to next load 4 cycles from L1, 14 from DRAM, as on the RTL (`core_latency` `tcdm` 2, `narrow` 6). A pending load lets the core go on until its next memory access or a use of its register.
- **Instruction fetch** (open item 65). The RTL's L0 cache prefetches the next line and taken branches' targets, GVSoC's `Hierarchical_cache` does not: more misses here, fewer cycles each. A start write and its loads in one cache line (`.balign 32`) give `core-tcdm`'s `core_vs_reader` the RTL's 18.
- **Other core timing** (open items 66, 67, 70, 71), hit by no measured loop: `dmstati` is polled every 2 cycles here, every 5 on the RTL; a SNAX CSR poll every 6 here, 5 there; atomics to DRAM are one access here, a read-modify-write on the RTL testbench (the exit barrier about 50 cycles shorter); a store or AMO after a pending L1 load waits for its data; an L1 load after a DRAM load reaches the crossbar up to 13 cycles early.
- **The host.** HTIF polls `tohost` every 1000 cycles, in zero time (`htif_poll_backdoor`); a `printf` waits on that grid. snRuntime zeroes `.bss` before `main`, so a larger `.bss` moves the program's start.

## The DMA

- **On the RTL:** `busy = L_rd + N_beats + 2`, with `L_rd` 11 from DRAM and 5 from L1, one 64 B beat a cycle. `busy_o` (`DMA_BUSY`, `dmstati 2`) drops before the write response. A 3-deep request FIFO, at most 3 bursts in flight per direction, a 3-beat buffer between reads and writes, bursts cut at 4 KiB boundaries; the testbench DRAM takes 2 reads and 2 writes in flight. `DMA_BUF_W_STALL` and `DMA_BUF_R_STALL` are never set.
- **The wide port.** The DMA reaches L1 through one 512-bit port per superbank (snax_cluster's `mem_wide_narrow_mux.sv` lines 81 to 93): while it is selected, all 8 banks of the superbank get its `q_valid`, only data and strobes cut per bank. A one-element burst is thus 8 bank reads and 8 bank writes; at gate level the DMA's transposed copy of a 64 × 64 matrix (4096 one-element bursts, int8 and int64 alike) reads and writes each of L1's 32 banks 1024 times.
- **The way into L1** (`idma_backend_rw_axi`, `dma-timing`'s short bursts), over AXI even within L1:
  1. A burst is one AXI transaction: AR, R, then AW, W, B.
  2. At most 3 bursts are in flight; a slot frees at the burst's last W: AR(k + 3) = W(k) + 1. B gates nothing.
  3. The write is coupled to its read (`rw_coupling_avail`): AW(k) in R(k)'s cycle, W(k) one cycle later.
  4. L1 has one DMA port (`axi_to_mem_interleaved` with `NumBanks(1)`), one read or one write a cycle. A read asks for it 2 cycles after its AR and returns 3 after its grant (the 5 of `L_rd`); a write asks 2 cycles after its W. One priority bit: a side asking alone is granted and takes it; when both ask, the holder goes first and the bit passes; the write holds it at reset (61 970 grants of a run predicted, 0 wrong).
- **So** a long copy pays the latency once: a beat a cycle between DRAM and L1, one per 2 cycles inside L1. The RTL's W channel stops taking beats while 3 wait for the port, which the rule leaves out: `l1l1 1x4096` is 129 there, 128 here, a cycle `dma-timing` allows. Short bursts inside L1 run 3 per 8 cycles, for any size of 1 to 64 B (`t-l1l1`, `s-l1l1`: busy 173 for 64 bursts, 10 925 for 4096).
- **Short bursts into DRAM** are paced by the testbench's memory, which the model leaves out: B returns 2 per 7 cycles, at most 8 writes wait (`s-l1l2 64x1 B p64` busy 211 on the RTL, 155 here, open item 146).
- **The model** (`snax/snax_hjson.py`, `idma_be_tcdm.cpp`) has the rule's four parts without AXI channels; a beat reaches L1 16 cycles after its `dmcpyi` on both sides (`l2l1 1x64`).
- **Measured** (`dma-timing`): `busy`, `r` and `w` of its 17 pinned cases equal the RTL's, `l1l1 1x4096` within its one cycle; `done` is 2 to 6 cycles under, from the core's issue and polling. `t-l1l1 1x1 B p64`'s 64 bursts have the RTL's R and W cycles; 19 take their AR a cycle late, while the port is busy. A cycle more on either read stage puts 15 cases off, on `coupled_write_latency` 7. Its copies inside L1 count 25 088 `copy_reads` and `copy_writes` each (12 544 per pass, each case run twice).
- **Counters.** `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and `DMA_BUSY` come from the iDMA's `busy`, `r_beats` and `w_beats`.

## The crossbar and the sparse interconnect

- **The RTL's layout.** snaxgen's `sparse_config` lists ports `[width, granularity]`: the accelerators' per core, `[1, 1]` per core, `[1, 1]` for AXI. Bank of an address: `(addr >> 3) & 31`, 32 banks of 64 bit; input `j` of granularity `g` reaches only banks with `b % g == j % g`. 4 superbanks of 8 banks, `(addr >> 6) & 3`; a DMA beat takes its superbank's banks, and a narrow winner there is refused and keeps its turn.
- **The pick** (`snax/snax_sparse_arb.hpp`), per bank and cycle: (1) only the valid requests at the highest priority count; (2) the last pick wins again if its bank refused it; (3) else the lowest input above the last pick, else the lowest; (4) an idle bank cycle restarts from the last input. Read data comes a cycle after the grant.
- **Checked against the RTL** (`tests/snax/sparse_arb/`, Verilator on the elaborated `SparseInterconnect.sv`, 20000 cycles, seeds 1 to 3): 15 and 23 inputs, 0 differences in nine runs (no idle restart, no lock, priority ignored: 1534, 1244, 8248); `m100`, `m128`, `n128`, 0 in twelve, thousands of selections at inputs 64 and above (a 64-bit mask: 83017 on `n128`). `tests/snax/sparse_pick/` checks the pick on 1 to 256 inputs against a plain loop; above 128 the model is checked only against itself.
- **Measured against the RTL**, every compared counter equal: `stream-timing`'s `prio_queued` and `idle_restart` 6; `core-tcdm`'s `after_stores` 6 and `core_vs_reader` 18; `dma-tcdm`'s `dma_vs_reader` 264, its DMA beats 3 to 7 cycles before the RTL's, all from the core's DMA issue (open item 67).
- **Not used yet:** the AXI input (open item 69); granularity above 1 (75); the iDMA as sparse ports (74).

## The streamer

- **Matches the RTL:** start, AGU pace, end rule and round-robin order (`stream-timing`'s counters 0, 9, 9, 10, 12, equal).
- **CSRs.** Per set, the streamer's CSRs, then its accelerator's, packed from 960 (dot 1: `vmul`'s streamer 960–977 and CSRs 978–981, `vsum`'s 982–994 and 995–999).
- **The queue count.** A writer's push and pop share a cycle, so its queue holds two words where the RTL counts one; `qmax` reports the RTL's count.
- **Configurable channels** are checked against the RTL only through the shared-mover fixtures.

## The group and its datapaths

- **One rule on three sides:** `SnaxGroupRule`, its Python twin and snax-forge's Chisel, checked by the same cases.
- **Arithmetic** (the int32 and int8 fixtures, `forge data: 0 errors`): an elementwise op runs at NumPy's result type of its inputs, then is cast to the output's; a fold's lanes are cast to its output's type before its tree; a signed type with uint64 is refused (NumPy gives float64).
- **The counter** on every forge variant at W = 4 and 8: the control rule's cycles plus the streamers' fill, 3 cycles (2 for a unit with one input).

## Events and traces

- `--trace` patterns into one file land in simulation order, `stop()` messages last; a trace file's name is relative to the work directory.
- The SNAX targets build `pulp/pulp/idma/`; `pulp/models/ips/pulp/idma_v2/` is unused.
- `--vcd --event-tags=snax` names 98 SNAX signals on vecadd; `--vcd` changes neither `events.log` nor stdout.
- Vecadd at level `stall`: a grant is 180 B in `events.log`, 222 B in `trace.jsonl`; GVSoC's header is 55 % of the beat lines' bytes.
- An exit code is not the error count (`forge errors: 2`, exit 1); snax-forge reads the printed counts.

## The comparison with snax_cluster's RTL

Each accelerator's `forge counter` and `forge data: 0 errors` must be equal, the window (`forge cycles`) within about 10 % (per bundle: snax-forge's open item 95); the gap is in the cores and the DMA; on vecadd the RTL is a fixed 13 to 14 cycles longer at N = 64 and 512.

## GVSoC itself

- **Targets.** GVSoC reads a target twice, at `make build` and under gvrun, with different arch classes. The install's `gvrun` puts its own `targets` and `generators` first on `sys.path`, so a generated target never takes an installed one's name. Without its platform tree a target runs on the JSON config; a property reaches the C++ through `gvsoc_config.json`, nothing compiled.
- **The TCDM's** size, banks and bank width come from the hjson; L1's size and base reach the program through `sw/generated/` (a change needs it rebuilt, the banks alone not).
- **The build.** `make build` recompiles `cluster_registers` every time. CMake refuses a build folder from another checkout. gvrun needs the image's `/opt/venv` Python (under `pixi run` it lacks `rich`). `werror: true`: any `force_warning` ends the run.
