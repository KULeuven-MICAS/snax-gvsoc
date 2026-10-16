# core-tcdm

The cores' TCDM accesses through the interconnect (SG7 round 3): the compute
core's sub-word accesses, AMO and LR/SC on L1, and its loads against the
streamer's readers on the same banks. One ELF per case, as `stream-timing`.
The same ELFs run on snax_cluster's RTL with the plain interconnect
(`cfg/snax_alu_cluster_old.hjson`) and on SNAX-GVSoC's `snax_alu` target, and
with the sparse one (`cfg/snax_alu_cluster.hjson`) and on `snax_alu_sparse`.
Each case prints the value it compares, chosen not to depend on the core's
timing (D123); `core_vs_reader`'s turned out to depend on its instruction
fetch (below).

| Case | What | Compare |
|---|---|---|
| `subword` | Stores and loads of bytes, halves and words to L1, read back at other widths; a doubleword stored and loaded (two words: the cores are rv32ima, with no 8-byte access); `amoadd.w`; `lr.w` then `sc.w` on one word | `errors` (per group) and `sc`, the SC's result; the program returns `errors` |
| `core_vs_reader` | Readers A and B, 2 beats each, every lane on bank 0 (16 requests); right after the start write the core loads a word on bank 16, then one on bank 0 | 977 |
| `after_stores` | The core's stores to the area are the last accesses to banks 0 to 3; then A (1 beat) and B (4 beats) on those banks | 977 |

The streamer cases leave the ALU off, as `stream-timing` does, so each lane
reads its beats and stops. The area is 8 KiB from a 256 B boundary (bank 0),
written by the core first; between those stores and the start write there
are only CSR instructions (`core_vs_reader` adds its two loads in one `asm`
block right after the start write). The compiler reads the signed byte and
half with `lbu` and `lhu` and compares the bits, so `lb` and `lh` are not
used.

- `core_vs_reader`: every reader request asks with priority 1 on the sparse
  interconnect (queue counts 0 and 1), so the core, with 0, waits until the
  readers are done: 17. The plain one gives the core its turn among the 8
  lanes, which costs the readers one cycle: 18. The first load on bank 16
  keeps the core's bank-0 load after the readers' first requests; either
  counter holds for the core's bank-0 load reaching the interconnect 4 to
  10 cycles after the start write.
- `after_stores`: the plain interconnect's per-bank state is left at core
  0's input (12) by its stores, from which `rr_arb_tree` takes B first:
  5. The sparse one restarts its pointer after the idle cycles and takes A,
  the lower input, first: 6.

Measured (SG7 round 3, step 6), plain RTL / plain target / sparse RTL /
sparse target: `subword` 0 errors on all but the sparse RTL, where the SC
fails (`sc` 1, 2 errors: its wrapper leaves the AMO shim's `core_id`
undriven); `core_vs_reader` 18 / 17 / 17 / 17; `after_stores` 5 / 5 / 6 / 6.
On SNAX-GVSoC the instruction line with the start write and the loads
misses in the I-cache, so the core asks for bank 0 at s + 14, too late to
take a cycle from the readers on the plain target: that counter depends on
the core's fetch timing.

`subword` on the sparse RTL: snax_cluster's sparse wrapper leaves the
memory side's user field undriven, so the AMO shim sees `core_id` X and
`is_core` 0 and the SC fails. SNAX-GVSoC keeps the plain RTL's behaviour, a
reservation per hart, which is the correct one; snax_cluster is to be fixed
after SG7, and until then the case returns 2 there.

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
