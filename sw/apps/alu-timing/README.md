# alu-timing

The ALU's timing against the RTL (SG4): `snax-alu`'s three streamers and the
ALU, set up through `snax-alu`'s library, in five cases run one after the
other in one ELF. The same ELF runs on snax_cluster's RTL with the plain
interconnect (`cfg/snax_alu_cluster_old.hjson`) and on SNAX-GVSoC's
`snax_alu` target, and with the sparse one (`cfg/snax_alu_cluster.hjson`)
and on `snax_alu_sparse` (SG7); the counters are the values to compare.

Each case prints its errors, the streamer's counter (977), the ALU's (982)
and the start gap: `mcycle` before `start_alu()` minus `mcycle` before
`start_streamer()`, negative when the ALU starts first. The gap is the
core's timing (SG5), so each case has one counter that does not depend on
it, the one to compare:

| Case | Order and layout | Compare | Checks |
|---|---|---|---|
| `alu_first` | ALU (add, 25 beats), then the streamer; A, B, O at +0, +800, +1600 B from a 256 B boundary (banks 0, 4, 8) | 977 | Reader → ALU → writer and the writer's last grant |
| `stream_first` | The streamer, a wait of 100 `mcycle`s (the readers fill their 8 beats), then the ALU; same layout | 982 | Firing from full readers; the ALU's first cycle against the streamer's |
| `out_one_bank` | As `stream_first`, every word of O on one bank (lane i of beat t at A + 2 KiB + 1024 t + 256 i) | 982 | The writer gets one grant a cycle, its queue fills, the ALU stalls on its output |
| `len1` | ALU (add, length 1), then the streamer with bound 1 | 982, 977 | The counter stays 1 with length 1 |
| `restart_idle` | Start (add, 100), start (sub, 25) before the streamer, then the streamer | 977, O = A - B | A start while busy latches the new mode and length |

`stream_first`'s layout (snax-alu's own) has the writer lose banks 8 to 11
to reader B, then, on the plain interconnect, to reader A; the writer's
queue absorbs it. On the sparse one the writer wins the second conflict
(its pointer is at B's lanes, the writer's are next), so the streamer ends a
cycle earlier. In `out_one_bank` a writer lane with 7 or 8 words queued asks
with priority 1 on the sparse interconnect and drains several words in a
row, so the ALU fires in bursts and its counter is 74, not 72 (SG7). Every case consumes all
its beats and every run ends, so nothing carries over to the next case.
O is checked against the core's own result in every case; the program
returns the error count.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/alu-timing
    source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/alu-timing \
        --param chip/soc/binary=$PWD/build/sw/apps/alu-timing/alu-timing.elf run

On the RTL built from the same hjson:

    cd snax_cluster/target/snitch_cluster
    bin/snitch_cluster.vlt <snax-gvsoc>/build/sw/apps/alu-timing/alu-timing.elf

## Output

On SNAX-GVSoC, exit code 0:

    alu-timing alu_first: errors 0, streamer counter 29, alu counter 34, start gap -7
    alu-timing stream_first: errors 0, streamer counter 132, alu counter 25, start gap 103
    alu-timing out_one_bank: errors 0, streamer counter 209, alu counter 72, start gap 103
    alu-timing len1: errors 0, streamer counter 5, alu counter 1, start gap -7
    alu-timing restart_idle: errors 0, streamer counter 29, alu counter 34, start gap -7

On `snax_alu_sparse`, the same but for `stream_first`'s streamer counter,
131, and `out_one_bank`'s ALU counter, 74. On the RTL: plain, step 5 of
`docs/plans/SG4.md`; sparse, SG7 step 9 in `docs/notes/NOTES.md`.

`--trace="snax_acc0:<file>"` gives each ALU run's classes (`busy`,
`stall_out`, `stall_in`) and the streamer's per mover; `--trace="snax_xbar:<file>"`
the grants per bank with the inputs held.
