# stream-timing

The streamer's timing on its own: the compute core sets up the streamer's two readers, leaves the writer's temporal bound at 0, starts the streamer, polls its busy CSR (976) and prints the streamer's counter (977). It runs on SNAX-GVSoC on `snax_hjson` with `forge/vecadd/snax_forge.hjson`; the same ELFs ran on snax_cluster's RTL with the sparse interconnect (`cfg/snax_alu_cluster.hjson`, the cluster snax-forge's base cluster is a copy of). The counter is the value to compare.

The accelerator is never started, so nothing takes the readers' beats. Each lane reads at most `fifo_depth` (8) beats and the reader is done; the beats stay in its queues and hold its credit, and the RTL does not clear them at start. So each case is an ELF of its own. Two cases use that: a first run leaves beats in one reader's queues, then the measured run starts, with no access to the TCDM in between; they also print the first run's counter.

| Case | Readers | Counter |
|---|---|---|
| `zero_bound` | every temporal bound 0: busy one cycle | 0 |
| `a_alone` | A: 8 beats from bank 0 | 9 |
| `ab_other_banks` | A and B, B 16 banks away | 9 |
| `ab_same_banks` | A and B, B 1 KiB away: lane i of each on the same bank | 10 |
| `a_stride0` | A with spatial stride 0: four lanes on one bank | 12 |
| `prio_queued` | first A alone, 4 beats; then A (4 beats, 4 queued: priority 0) and B (1 beat, none queued: priority 1) on banks 0 to 3 | 6 |
| `idle_restart` | first B alone, 1 beat on banks 0 to 3; then, after idle cycles, A (1 beat) and B (4 beats) on those banks, both priority 1 | 6 |

Each counter is the same on the RTL and on SNAX-GVSoC. In `prio_queued` the sparse interconnect lets B, the reader with an empty queue, go first; in `idle_restart` its pointer restarts after the idle cycles, so A, the lower input, goes first. The first runs count 5 and 2.

Each beat is 4 lanes of 64 bit; the temporal stride is 32 B, so A's beat t covers banks 4t to 4t + 3. The counter is reset the cycle after the start write (s) and counts the busy cycles after that, so it is g - s with g the cycle of the last grant.

The line also gives `polls` (busy reads that saw 1) and the `mcycle` span from before the start write to after the last poll; both depend on the core's timing, not only on the streamer.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from `sw/` first when needed):

    make -C sw/apps/stream-timing
    source sourceme.sh
    for c in zero_bound a_alone ab_other_banks ab_same_banks a_stride0 prio_queued idle_restart; do
      gvrun --target snax_hjson --work-dir build/work/st-$c \
        --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/stream-timing/stream-timing-$c.elf run
    done

`--trace="snax_xbar:<file>"` writes the crossbar's grants per bank and cycle, with the inputs held, each named by its owner (`snax_acc0.streamer.reader0.lane0`); `--trace="snax_acc0/streamer:<file>"` the streamer's start, AGUs, end and per mover the cycle classes and the highest queue counts. With `--trace-level=trace` they add each read's response (`Resp`) and each lane queue's count (`Queue`).
