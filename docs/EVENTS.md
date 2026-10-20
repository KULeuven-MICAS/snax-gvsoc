# SNAX-GVSoC's events

What SNAX-GVSoC's SNAX components say about a run, line by line, for
snax-forge's converter (`snax_forge/run/`, its D137 and C§7) and for anyone
reading a run by hand. The grammar is this repository's; snax-forge renames
it and never recounts.

## Traces and levels

Each SNAX component has three GVSoC traces (`vp::Trace`), named:

| Trace | Holds | On at |
|---|---|---|
| `summary` | counters: per run of a unit or streamer at its end, the others' at the end of the simulation | every level, `off` included |
| `events` | what happens once per task: starts, dones, CSR accesses, waits, function entries, DMA copies | `task` |
| `beats` | one line per beat (grants, stalls, firings, DMA beats): declared, written from FLOW3 round 2 | `beat` |

A level is which trace names are on, given to `gvrun` as one `--trace`
regex per name, all naming one file, so the lines of every component come
in the order the simulation writes them:

    gvrun ... --trace='/summary$:RUN/events.log' --trace='/events$:RUN/events.log' run

(`--trace-level` is not used: every line here is written at GVSoC's default
level.) With these traces off, a run is the same as without them.

## Lines

GVSoC writes a header before each line, `<ps>: <cycles>: [<path>] `, with
ANSI colour codes around the path; `<path>` is the component's path, then
`/` and the trace's name. The converter keeps the component's path and
ignores the rest of the header. The line itself is

    <cycle> <kind> <key>=<value> ...

`<cycle>` is a cycle of the component's own clock: the cycle the line is
about (below, per kind). Most lines are written in that cycle; a `poll`, a
`barrier`, a held `csr` write and a single `csr` read are written later, when
they are known, so sort by `<cycle>` for time order; lines of one cycle are
in simulation order. A value is a decimal integer, a hexadecimal one with
`0x` (addresses, `pc`, `csr`), a list of integers joined by `,`, or a name.
Every line ends in a newline.

## Components

The paths are those of `snax_hjson`'s cluster (`/chip/soc/cluster_0/...`);
`snax_acc<i>` is core `i`'s accelerator.

### Unit (`snax_acc<i>/unit`, `snax/snax_unit.cpp`)

| Trace | Kind | Cycle | Fields |
|---|---|---|---|
| `events` | `start` | the cycle `s` a start is taken (busy from `s + 1`) | `count`, `rate` |
| `events` | `done` | the run's last busy cycle `E` (idle from `E + 1`) | `firings`; `first` and `last`, the cycles of its first and last firing |
| `summary` | `run` | `E` | `index` (from 0), `firings`, `busy`, `stall_in`, `stall_out`, `flush` (they add up to `E - s`) |

### Streamer (`snax_acc<i>/streamer`, `snax/snax_streamer.cpp`)

Per mover (`reader<i>`, `writer<j>`, as `snax_streamer.py` names them):

| Trace | Kind | Cycle | Fields |
|---|---|---|---|
| `events` | `start` | the cycle `s` the start is taken, one line per mover | `mover` |
| `events` | `done` | the mover's last busy cycle: the commit in which its last address leaves (a mover with nothing to move: the first commit after the start) | `mover` |
| `summary` | `mover` | the streamer's end, one line per mover and run | `mover`, `run` (from 0), `busy`, `stall_xbar`, `stall_fifo`, `idle`, `qmax` (the highest count of each lane's queue, lane 0 first) |

### Crossbar (`tcdm/snax_xbar`, `snax/snax_tcdm_xbar.cpp`)

Both arbiters. Counted over the whole simulation, written at its end:

| Trace | Kind | Fields |
|---|---|---|
| `summary` | `input` | `index`, `name` (its owner: `snax_acc<i>.streamer.<mover>.lane<l>`, `core<i>`, `axi`), `grants`, `stalls` (cycles it requested and was not granted), `stalls_dma` (the part refused or lost on a bank the DMA's superbank took), `whole_run` (1 for the cores and AXI, whose traffic starts at boot) |
| `summary` | `bank` | `index`, `reads`, `writes` (a SNAX input's grant or a DMA beat's word on the bank), `conflicts` (cycles with two or more of those requests on the bank) |

The banks count the SNAX inputs and the DMA only; the cores' and AXI's
accesses are in their own `input` lines.

### Core (`pe<i>`, `core/models/cpu/iss/src/snitch/snitch.cpp`)

The `snitch` core only (`CONFIG_GVSOC_ISS_SNAX_EVENTS`, set in
`pulp/pulp/snitch/snitch_core.py`); `state` comes from `Exec::busy_enter` and
`busy_exit`, `func` from `Exec::insn_exec_profiling`, in the shared exec code.

| Trace | Kind | Cycle | Fields |
|---|---|---|---|
| `events` | `csr` | the access | `pc`, `csr`, `op` (`r`, `w`), `value`; `held`, the cycles the block held a write |
| `events` | `poll` | its first read | `pc`, `csr`, `value`, `first`, `last`, `count` |
| `events` | `barrier` | the read of CSR `0x7c2` | `first`, `last` (the cycle it is released) |
| `events` | `state` | the first cycle in it | `mode` (`run`, `sleep`) |
| `events` | `func` | the function's first instruction | `name`, `pc` |
| `summary` | `csrs` | the end of the simulation | `writes`, `reads` (SNAX CSRs, every read of a poll counted) |

`csr` and `poll` are the SNAX CSR accesses: consecutive reads of one CSR that
return one value are one `poll`, written when the next access differs; a
single read is a `csr` with `op=r`. A barrier stalls the core without leaving
`run`, so its own line says when it waits; one reached at once has `first`
equal to `last`. `sleep` is `wfi`. `func` is written when the PC enters
another function, by the ELF's symbols (`-` where none covers the PC); a
core only writes it while its `events` trace is on.

### iDMA (`idma/fe`, `pulp/pulp/idma/fe/idma_fe_xdma.cpp`)

| Trace | Kind | Cycle | Fields |
|---|---|---|---|
| `events` | `issue` | the cycle the core's copy is taken (`enqueue_copy`) | `id`, `src`, `dst`, `size`, `src_stride`, `dst_stride`, `reps` (its rows, 1 for a 1D copy) |
| `events` | `done` | the cycle the copy completes (`ack_transfer`) | `id` |
| `summary` | `dma` | the end of the simulation | `transfers`, `busy` (cycles its busy signal is high, what `DMA_BUSY` counts), `r_beats`, `w_beats` (what the beat wires carry), `bytes_to_l1`, `bytes_from_l1` |

A copy's bytes are `size` times its rows; they go to L1 when its `dst` is in
the iDMA's local area (`loc_base`, `loc_size`: the cluster's L1), and come
from L1 when its `src` is.
