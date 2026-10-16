# core-tcdm

The cores' TCDM accesses through the interconnect (SG7 round 3): the compute
core's sub-word accesses, AMO and LR/SC on L1, and its loads against the
streamer's readers on the same banks. One ELF per case, as `stream-timing`.
The same ELFs run on snax_cluster's RTL with the plain interconnect
(`cfg/snax_alu_cluster_old.hjson`) and on SNAX-GVSoC's `snax_alu` target, and
with the sparse one (`cfg/snax_alu_cluster.hjson`) and on `snax_alu_sparse`.
Each case prints the value it compares, chosen not to depend on the core's
timing (D123); `core_vs_reader` runs twice so that its measured run does not
depend on the core's instruction fetch (below).

| Case | What | Compare |
|---|---|---|
| `subword` | Stores and loads of bytes, halves and words to L1, read back at other widths; a doubleword stored and loaded (two words: the cores are rv32ima, with no 8-byte access); `amoadd.w`; `lr.w` then `sc.w` on one word | `errors` (per group) and `sc`, the SC's result; the program returns `errors` |
| `core_vs_reader` | Readers A and B, 2 beats each, every lane on bank 0 (16 requests); right after the start write the core loads a word on bank 16, then one on bank 0. Twice: a first run, then the measured one | 977 of the measured run (the first run's shown) |
| `after_stores` | The core's stores to the area are the last accesses to banks 0 to 3; then A (1 beat) and B (4 beats) on those banks | 977 |

The streamer cases leave the ALU off, as `stream-timing` does, so each lane
reads its beats and stops. The area is 8 KiB from a 256 B boundary (bank 0),
written by the core first; between those stores and the start write there
are only CSR instructions (`core_vs_reader` adds its two loads in one `asm`
block right after the start write, and between its two runs there are only
CSR instructions too). The compiler reads the signed byte and
half with `lbu` and `lhu` and compares the bits, so `lb` and `lh` are not
used.

- `core_vs_reader`: the start write and the two loads are one 32 B
  instruction line (`start_and_load`, not inlined), run twice, so in the
  measured run the line is in GVSoC's I-cache and the core loads 1 cycle
  after the start write, as on the RTL (in a first run on GVSoC the line
  misses and the core comes 10 cycles later). The first load on bank 16
  keeps the core's bank-0 load after the readers' first requests. Plain:
  the core gets its turn among the 8 lanes, which costs the readers one
  cycle: 18. Sparse: in the first run every reader request asks with
  priority 1 (queue counts 0 and 1) and the core, with 0, waits until the
  readers are done: 17. In the measured run each lane's queue still holds
  the first run's 2 words (the ALU is off), so the readers ask with 0, as
  the core, and the core gets its round-robin turn: 18, as plain.
- `after_stores`: the plain interconnect's per-bank state is left at core
  0's input (12) by its stores, from which `rr_arb_tree` takes B first:
  5. The sparse one restarts its pointer after the idle cycles and takes A,
  the lower input, first: 6.

Measured, plain RTL / plain target / sparse RTL / sparse target: `subword`
0 errors on all but the sparse RTL, where the SC fails (`sc` 1, 2 errors:
its wrapper leaves the AMO shim's `core_id` undriven); `after_stores` 5 / 5
/ 6 / 6 (SG7 round 3, step 6); `core_vs_reader` 18 / 18 / 18 / 18, first
run 18 / 17 / 17 / 17 (round 3b, step 4). Round 3's single run gave 18 /
17 / 17 / 17: on SNAX-GVSoC the core asked for bank 0 at s + 14, too late
to take a cycle from the readers on the plain target, so that counter
depended on the core's fetch timing; the first run still does.

`subword` on the sparse RTL: snax_cluster's sparse wrapper leaves the
memory side's user field undriven, so the AMO shim sees `core_id` X and
`is_core` 0 and the SC fails. SNAX-GVSoC keeps the plain RTL's behaviour, a
reservation per hart, which is the correct one; snax_cluster is to be fixed
after SG7, and until then the case returns 2 there.
Fixed by snax_cluster #658 (SG8): from the pin `05615e4` on, `subword` gives 0 errors and `sc` 0 on the sparse RTL too.

The line also gives `polls` (busy reads that saw 1), and `core_vs_reader`
the two words the core loaded; they depend on the core's timing or not at
all on the interconnect.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/core-tcdm
    source sourceme.sh
    for c in subword core_vs_reader after_stores; do
      gvrun --target snax_alu --work-dir build/work/ct-$c \
        --param chip/soc/binary=$PWD/build/sw/apps/core-tcdm/core-tcdm-$c.elf run
    done

`--trace="snax_xbar:<file>"` writes the crossbar's grants, the cores' as
`core0` and `core1`, with the size of an access smaller than a word.
