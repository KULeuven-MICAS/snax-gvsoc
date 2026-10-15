# snax-stream

`snax-alu`'s three streamers and the ALU in its four modes (SG4). Readers A
and B and the writer O are set up as `snax-alu` sets them, through its
library (`../snax-alu/lib`, `../snax-alu/include`): 25 beats of 4 lanes, A,
B and O one after the other from the start of L1 (+0, +800, +1600 B). A and
B are full 64-bit words from a fixed generator, so sub underflows and mul
keeps the low 64 bits of its product, as `snax_alu_pe.sv` does.

| Run | ALU mode | Checks |
|---|---|---|
| add | 0 | O = A + B |
| sub | 1 | O = A - B |
| mul | 2 | O = A * B, low 64 bits |
| xor | 3 | O = A ^ B |

Each run prints its errors, the streamer's counter (977) and the ALU's
(982); the program returns the error count. The same ELF runs on
snax_cluster's RTL (`cfg/snax_alu_cluster_old.hjson` at `b2672f8`) and on
SNAX-GVSoC's `snax_alu` target. The timing of the ALU against the RTL is
`alu-timing`'s; here the counters are printed for comparison.

## Build and run

In the container, from the folder that holds this repo and snax_cluster,
after snax_cluster's runtime is built for the cluster (see
`../snax-alu/README.md`):

    make -C snax-gvsoc/tests/snax/snax-stream
    cd snax-gvsoc && source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/snax-stream \
        --param chip/soc/binary=$PWD/tests/snax/snax-stream/build/snax-stream.elf run

On the RTL built from the same hjson:

    cd snax_cluster/target/snitch_cluster
    bin/snitch_cluster.vlt <snax-gvsoc>/tests/snax/snax-stream/build/snax-stream.elf

## Expected output

On SNAX-GVSoC, exit code 0:

    snax-stream add: errors 0, streamer counter 31, alu counter 25
    snax-stream sub: errors 0, streamer counter 31, alu counter 25
    snax-stream mul: errors 0, streamer counter 31, alu counter 25
    snax-stream xor: errors 0, streamer counter 31, alu counter 25

The streamer's counter depends on the gap between the two start writes (5
cycles here), which is the core's timing.

`--trace="snax_acc0:<file>"` gives the streamer's and the ALU's starts and
ends, per mover the cycle classes and the highest queue counts, and the
ALU's classes per run (`busy`, `stall_out`, `stall_in`); with
`--trace-level=trace` each firing too.
