# dma-tcdm

The DMA against the streamer in the TCDM (SG7 round 4): a DMA beat takes the
whole superbank (8 banks, 64 B) it writes in its cycle, and a streamer lane
asking for one of those banks is refused and keeps its turn. One ELF per
case, as `core-tcdm`. It starts `forge/vecadd/`'s accelerator (a lockstep
add) through `forge/vecadd/include/`'s headers; the same ELFs run on
`snax_hjson` with `forge/vecadd/snax_forge.hjson` and on snax_cluster's RTL
built from snax-forge's vecadd bundle (snax-forge `docs/RUN.md` section 8).
Each case
prints the value it compares, chosen not to depend on the cores' timing
(D123), and runs twice: a first run, then the measured one, from a warm
instruction cache.

| Case | What | Compare |
|---|---|---|
| `dma_vs_reader` | The accelerator (add, 256 beats) with A, B and O each on its own four banks, every beat in the next 256 B row: A on banks 0 to 3 (superbank 0), B on 8 to 11, O on 16 to 19. 50 cycles after a barrier the DMA core copies four 64 B blocks from DRAM into the rows after them, one row apart: in the first run at the rows' last 64 B (superbank 3, which no mover uses), in the measured run at their first 64 B (superbank 0, A's) | 977 of the measured run (the first run's shown): 264 (260) on SNAX-GVSoC and on the RTL from snax-forge's vecadd bundle (Verilator, snax_cluster `b9e475b4`) |

- `dma_vs_reader`: the accelerator starts first and waits for the
  streamer, so 977 is the beats plus 4 without contention:
  260 in the first run. In the measured run each of the four DMA beats
  refuses A's four lanes in its cycle; A then sends again, one beat late,
  and the accelerator, which takes a beat of A and of B in every cycle,
  fires a cycle later each time: 264. A is alone on its banks, so the lock makes it
  win again in the next cycle. From source, the beats land some 65 to 90 cycles after the DMA
  core leaves the barrier and the movers ask from 2 to 257 cycles after
  the start write, a few cycles after the compute core leaves it: the
  counter holds while the two cores leave the barrier within about 60
  cycles of each other.

In the window neither core touches the TCDM: the compute core starts the
accelerator and the streamer and polls their busy CSRs, the DMA core waits
on `mcycle`, issues the copies from registers and polls the DMA. The line
also gives the shell's counter (981, `acc counter`), which depends on the
gap between the two start writes (the core's timing), and the errors: O against A + B, and the
copies against their source; the program returns them.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/dma-tcdm
    source sourceme.sh
    gvrun --target snax_hjson --work-dir build/work/dma-tcdm \
      --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
      --param chip/soc/binary=$PWD/build/sw/apps/dma-tcdm/dma-tcdm-dma_vs_reader.elf run

`--trace="snax_xbar:<file>"` writes the DMA's beats (`Superbank s: grant
dma`) and the narrow winners they refuse (`Bank b: refused <input> (dma)`).
