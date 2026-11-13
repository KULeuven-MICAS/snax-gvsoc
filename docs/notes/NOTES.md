# SNAX-GVSoC notes

What SNAX-GVSoC was measured to do against snax_cluster's RTL and against GVSoC itself: only the facts that still hold. The events and traces are in `docs/EVENTS.md`, each component's rules in its own comments, the decisions in snax-forge's `docs/DECISIONS.md`. Open items are snax-forge's (`docs/STATUS.md`).

## Versions compared against

| What | Where it is pinned |
|---|---|
| GVSoC and its folded submodules | `UPSTREAM.md` |
| snax_cluster: the copy in `sw/` and the RTL compared against | `sw/README.md` |
| common_cells, the TCDM arbiter | `v1.40.0`, in the RTL build's `Bender.lock` |

## The core and its timing

- **Cluster CSRs.** snax_cluster's start-up code reads the cluster base and {core count, index} from CSRs 0xBC1 to 0xBC3. The Snitch model declares them read-only, as the RTL does.
- **SNAX CSRs.**
  - 0x3C0 to 0x5FF go out as 32-bit IO requests on port `snax_csr`, at 4 × the CSR number. An accelerator's range stops at 0x5FD; 0x5FE and 0x5FF go to the cluster's top-level CSR port.
  - `csrrw` and `csrrwi` read only when `rd` is not `x0`; the set and clear forms are a read, then a write, as on the RTL (`snax-csr`: 0 errors).
  - A pending write stalls the instruction until its answer (the shell's held start). A pending read is fatal; a refused access ends the run.
- **Loads.**
  - One integer load in flight, as the RTL's `num_int_outstanding_loads: 1`.
  - Load to next load: 4 cycles from L1, 14 from DRAM (`core_latency` `tcdm` 2, `narrow` 6).
  - A load answered pending lets the core go on until its next memory access or a use of its register.
- **Instruction fetch** (open item 65). The RTL's L0 cache prefetches the next line and taken branches' targets; GVSoC's `Hierarchical_cache` does not. So SNAX-GVSoC misses more lines, for fewer cycles each. Putting a start write and the loads after it in one cache line (`.balign 32`) brought `core-tcdm`'s `core_vs_reader` to the RTL's 18.
- **Other core timing** (open items 66, 67, 70, 71), none of which a measured loop hits:
  - `dmstati` is polled every 2 cycles here, every 5 on the RTL; a SNAX CSR poll every 6 here, 5 there.
  - Atomics to DRAM are one access here, a read-modify-write on the RTL testbench (the exit barrier is about 50 cycles shorter here).
  - A store or AMO after a pending L1 load waits for its data; an L1 load after a DRAM load reaches the crossbar up to 13 cycles early.
- **The host.** GVSoC's HTIF polls `tohost` every 1000 cycles. With `htif_poll_backdoor` (the SNAX targets) the poll takes zero time, same value and period. A `printf` waits on the host's answer, on that 1000-cycle grid.
- **Boot.** snRuntime zeroes `.bss` before `main`, so a larger `.bss` moves the program's start (about 470 cycles for snax-forge's generated program against vecadd's old hand-written one).

## The DMA

- **On the RTL:**
  - `busy = L_rd + N_beats + 2`, with `L_rd` 11 from DRAM and 5 from L1, and one 64 B beat a cycle.
  - `busy_o` (`DMA_BUSY`, `dmstati 2`, which `snrt_dma_wait_all` polls) drops before the write response.
  - A 3-deep request FIFO, at most 3 bursts in flight per direction, a 3-beat buffer between reads and writes, and bursts that end at the nearer 4 KiB boundary. The testbench DRAM takes 2 reads and 2 writes in flight.
  - `DMA_BUF_W_STALL` and `DMA_BUF_R_STALL` are never set.
- **The model** (`DMA_TIMING` in `snax/snax_hjson.py`):
  - `read_latency` 5 and `hbm_latency` 6, so DRAM is 11 on both sides; DRAM moves 64 B a cycle.
  - `tcdm_write_latency` 2: a beat is in L1 2 cycles after it leaves the DMA, which is done at the send.
  - `one_cycle_per_stage`: the midend, the backend and the AXI read take a cycle each.
  - A beat reaches L1 16 cycles after its `dmcpyi` on both sides (`l2l1 1x64`).
- **Measured** (`dma-timing`, eight copies): `busy`, `r` and `w` equal the RTL's on every line; `done` is 2 to 6 cycles under it, from the core's issue and polling. `dma-timing` fails when the DMA's own timing moves (`read_latency` 6 puts 8 lines off).
- **Counters.** `CYCLE`, `DMA_R_DONE`, `DMA_W_DONE` and `DMA_BUSY` come from the iDMA's `busy`, `r_beats` and `w_beats`.
- **Not verified:** an L1-to-L1 copy, whose read and delayed write reach the crossbar in one cycle where the RTL's `axi_to_mem` takes one a cycle (open item 72); the DMA reading L1 (open item 73).

## The crossbar and the sparse interconnect

- **The RTL's layout.**
  - snaxgen's `sparse_config` lists ports as `[width, granularity]`: each accelerator's ports per core, then `[1, 1]` per core, then `[1, 1]` for AXI.
  - Bank of an address: `(addr >> 3) & 31`, on 32 banks of 64 bit.
  - Input `j` of granularity `g` reaches only banks with `b % g == j % g`.
- **The pick** (`snax/snax_sparse_arb.hpp`), per bank and cycle:
  1. only the valid requests at the highest priority count;
  2. the last pick wins again if its bank refused it (the lock);
  3. else the lowest input above the last pick, else the lowest;
  4. an idle bank cycle restarts from the last input.

  Read data comes one cycle after the grant.
- **Checked against the RTL** (`tests/snax/sparse_arb/`, Verilator on the elaborated `SparseInterconnect.sv`, 20000 cycles, seeds 1 to 3):
  - 15 and 23 inputs: 0 differences in nine runs. Copies with one rule broken (no idle restart, no lock, priority ignored) give 1534, 1244 and 8248 differences.
  - 100 and 128 inputs (`m100`, `m128`, `n128`): 0 differences in twelve runs, with thousands of selections at arbiter inputs 64 and above. A copy limited to a 64-bit mask gives 83017 selection differences on `n128`.
- **Up to 128 inputs.** The request masks are `std::bitset<128>` (`SnaxInputMask`, `kMaxInputs`); a crossbar or a bank with more inputs is refused. `tests/snax/sparse_pick/` checks the pick on 1 to 128 inputs against a plain loop of the rule. The fixtures' forge lines did not change when the 128-input mask replaced the 64-bit one.
- **The priority bit.** A new request carries its lane queue's hint of the cycle before (a reader's count ≤ 1, a writer's ≥ `fifo_depth` − 1) and keeps it while it is resent. Without `dynamicPriority` it is `higherStaticPriority`. There is a wire per SNAX port (`prio_<i>`); an unbound wire asks with 0, as the cores and AXI do.
- **Inputs.**
  - The SNAX ports drop a losing request and send it again; the cores and AXI hold theirs for the next cycle.
  - A read, AMO or LR/SC is answered a cycle after its grant plus the request's latency; a write at its grant.
  - An access is 1 to 8 bytes inside one bank word; one crossing a word is refused. LR reservations are per hart.
- **The DMA's superbank.**
  - 8 banks a superbank, 4 superbanks: `(addr >> 6) & 3`.
  - On the RTL the DMA's beat gets every bank of its superbank for its cycle, granted at once, and the narrow winner there is refused and keeps its turn. The `dma` port does the same here; a beat crossing a superbank line is refused.
  - The DMA's beats come from events queued a cycle or more ahead, so a beat always comes first. A later one on a superbank already granted to a narrow request is fatal (no program has one).
- **Measured against the RTL:** every compared counter equal. `stream-timing`'s `prio_queued` and `idle_restart` 6; `core-tcdm`'s `after_stores` 6 and `core_vs_reader` 18; `dma-tcdm`'s `dma_vs_reader` 264. In `dma_vs_reader` the DMA's beats land 3 to 7 cycles before the RTL's, all of it the core's DMA issue (open item 67).
- **Not used yet:** the AXI input (wired, but no program sends through it, open item 69); granularity above 1 (open item 75); the iDMA as sparse ports (open item 74).

## The streamer

- **From the hjson** (`snax_cfg.py`):
  - one streamer per streamer set, one set per accelerator of `accelerator.json`;
  - the slot's TCDM ports are the sets' channels, in set order;
  - per set its streamer's CSRs come first, then its accelerator's, packed from 960 (dot 1: `vmul`'s streamer 960–977 and CSRs 978–981, `vsum`'s 982–994 and 995–999).
- **Matches the RTL:** start, AGU pace, end rule and the round-robin order (`stream-timing`'s counters 0, 9, 9, 10, 12, equal).
- **Cycle classes per mover:** `busy` > `stall_xbar` > `stall_fifo` > `idle`.
- **The queue count.** A writer's push and pop share a cycle, push first, so its data queue holds two words where the RTL counts one; `qmax` reports the RTL's count.
- **Widths.** A b-bit input port takes lanes × b / 64 words. Each mover's spatial bounds multiply to its `num_channel`, and each datapath port's words must equal its mover's `num_channel`; `snax_cfg.py` refuses the rest at load.
- **Configurable channels:**
  - a mover with `configurable_channel` has ENABLED_CHANNEL after its temporal strides: `ceil(num_channel / 32)` CSRs, bit l for lane l, taken at the start;
  - it reads 0 after reset, so every lane is off until the program writes it;
  - a lane that is off sends no request; a reader's lane puts a 0 word in its queue instead, and a writer's lane drops its address and data;
  - not checked against the RTL on its own; the shared-mover fixtures run it.
- **Shared movers:**
  - `SnaxPortMux` (`snax_port_mux.cpp`, its rule in `snax_port_mux.hpp`) sits between the groups' ports and the movers, combinational, no cycle;
  - PORT_MUX_SEL, the accelerator's last CSR, picks the group;
  - fatal: a beat from a group not selected, a select write while the streamer is busy, and a select past the last group;
  - `tests/snax/port_mux/` checks the rule on `mvt_1_dot2`'s mux.

## The group and its datapaths

- **One rule on three sides.** The group control rule exists as `SnaxGroupRule` (`snax/snax_group.hpp`), its Python twin (`snax/snax_group_rule.py`) and snax-forge's Chisel. The group, unit and shell cases check it; NumPy's vectors check the datapath classes (`tests/snax/datapath/`).
- **The shell.** A start while busy is answered pending and taken in E + 1. The counter is reset by an accepted start and counts the busy cycles.
- **Arithmetic** (the int32 and int8 fixtures, `forge data: 0 errors`):
  - an elementwise op runs at NumPy's result type of its inputs, then is cast to the output's type;
  - a fold's lanes are cast to its output's type before its tree;
  - a signed type with uint64 is refused (NumPy gives float64).
- **The counter** on every forge variant at W = 4 and 8: the control rule's cycles plus the streamers' fill, 3 cycles (2 for a unit with one input). `make regress` checks each forge run's counters against its tasks.

## Events and traces

`docs/EVENTS.md` has the lines. What was measured about them:

- **One file in simulation order.** Several `--trace` patterns into one file land in order, and a component's message from `stop()` lands last, so end-of-run counters go there. A trace file's name is relative to the work directory; on stdout a `printf` can split a trace line.
- **The core** writes `func` with the function's name without the instruction trace. Its `state` and `func` lines are behind `CONFIG_GVSOC_ISS_SNAX_EVENTS`, on `snitch` only. The window snax-forge reports is the program's two `mcycle` reads.
- **The iDMA** the SNAX targets build is `pulp/pulp/idma/` (`idma_fe_xdma.cpp`); `pulp/models/ips/pulp/idma_v2/` is an unused copy.
- **VCD.** `--vcd --event-tags=snax` names 98 SNAX signals on vecadd, each value set in its own cycle; `--vcd` changes neither `events.log` nor stdout.
- **Sizes** (vecadd at trace level `stall`): a grant is 180 B in `events.log` and 222 B in `trace.jsonl`; GVSoC's line header is 55 % of the beat lines' bytes.
- **Exit codes.** A program's exit code is not its error count (two wrong goldens: `forge errors: 2`, exit 1); snax-forge reads the counts from the printed lines.

## The comparison with snax_cluster's RTL

- **What is compared:** each accelerator's `forge counter` and `forge data: 0 errors` must be equal; the window (`forge cycles`) within about 10 %.
- **Where the window's gap lies.** Every counter is equal, so the accelerator's busy span is the same on both sides; the gap is in the cores and the DMA (the sections above). On vecadd the RTL is a fixed 13 to 14 cycles longer at N = 64 and 512.
- **The current numbers** per bundle are in snax-forge's open item 95.

## GVSoC itself

- **Targets.**
  - GVSoC reads a target twice, at `make build` and under gvrun, with different arch classes.
  - The install's `gvrun` puts its own `targets` and `generators` first on `sys.path`, so an installed module shadows a `--target-dir` one: a generated target never takes an installed target's name.
  - A target without its platform tree runs on the JSON config, with gvrun's warning; a property reaches the C++ through `gvsoc_config.json`, nothing compiled.
- **The TCDM's** size, banks and bank width come from the hjson. L1's size and base reach the program through `sw/generated/`, so changing them needs the program rebuilt; changing the banks alone keeps the ELF.
- **The build.**
  - `make build` recompiles `cluster_registers` every time (not looked into).
  - CMake refuses a build folder made from another checkout.
  - gvrun needs the image's `/opt/venv` Python (under `pixi run` it lacks `rich`).
  - GVSoC runs with `werror: true`: any `force_warning` ends the run.
