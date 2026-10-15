# stream-timing

The streamer's timing on its own (SG3): the compute core sets up `snax_alu`'s
two readers, leaves the writer's temporal bound at 0, starts the streamer,
polls its busy CSR (976) and prints the streamer's counter (977). The same
ELFs run on snax_cluster's RTL (`cfg/snax_alu_cluster_old.hjson` at
`b2672f8`) and on SNAX-GVSoC's `snax_alu` target; the counter is the value to
compare.

The ALU is never started, so nothing takes the readers' beats. Each lane
reads at most `fifo_depth` (8) beats and the reader is done; the beats stay
in its queues and hold its credit, and the RTL does not clear them at start.
So each case is an ELF of its own.

| Case | Readers | Counter (RTL and SNAX-GVSoC, SG3 step 5) |
|---|---|---|
| `zero_bound` | every temporal bound 0: busy one cycle | 0 |
| `a_alone` | A: 8 beats from bank 0 | 9 |
| `ab_other_banks` | A and B, B 16 banks away | 9 |
| `ab_same_banks` | A and B, B 1 KiB away: lane i of each on the same bank | 10 |
| `a_stride0` | A with spatial stride 0: four lanes on one bank | 12 |

Each beat is 4 lanes of 64 bit; the temporal stride is 32 B, so A's beat t
covers banks 4t to 4t + 3. The counter is reset the cycle after the start
write (s) and counts the busy cycles after that, so it is g - s with g the
cycle of the last grant.

The line also gives `polls` (busy reads that saw 1) and the `mcycle` span
from before the start write to after the last poll; both depend on the
core's timing (SG5), not only on the streamer.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/stream-timing
    source sourceme.sh
    for c in zero_bound a_alone ab_other_banks ab_same_banks a_stride0; do
      gvrun --target snax_alu --work-dir build/work/st-$c \
        --param chip/soc/binary=$PWD/build/sw/apps/stream-timing/stream-timing-$c.elf run
    done

`--trace="snax_xbar:<file>"` writes the crossbar's grants per bank and cycle,
with the inputs held, each named by its owner
(`snax_acc0.streamer.reader0.lane0`); `--trace="snax_acc0/streamer:<file>"`
the streamer's start, AGUs, end and per mover the cycle classes and the
highest queue counts. With `--trace-level=trace` they add each read's
response (`Resp`) and each lane queue's count (`Queue`).
