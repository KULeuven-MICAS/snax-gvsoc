# snax-stream

`snax-alu`'s three streamers on SNAX-GVSoC's `snax_alu` target, with the test
datapath in the ALU's place (SG3, `snax/snax_test_datapath.py`). Readers A
and B and the writer O are set up as `snax-alu` sets them, through its
library (`../snax-alu/lib`, `../snax-alu/include`): 25 beats of 4 lanes,
A, B and O one after the other from the start of L1 (+0, +800, +1600 B).

| Run | Datapath mode | Checks |
|---|---|---|
| copy A, k=1 | `0x00`: copies A, one firing per cycle | O equals A |
| copy B, k=3 | `0x21`: copies B, one firing every 3 cycles | O equals B |

Each run prints its errors, the streamer's counter (977) and the datapath's
(982); the program returns the error count. Not for the RTL: there the ALU
computes, and its mode CSR has no k.

## Build and run

In the container, from the folder that holds this repo and snax_cluster,
after snax_cluster's runtime is built for the cluster (see
`../snax-alu/README.md`):

    make -C snax-gvsoc/tests/snax/snax-stream
    cd snax-gvsoc && source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/snax-stream \
        --param chip/soc/binary=$PWD/tests/snax/snax-stream/build/snax-stream.elf run

## Expected output

On SNAX-GVSoC at SG3 P5, exit code 0:

    snax-stream copy A, k=1: errors 0, streamer counter 42, datapath counter 25
    snax-stream copy B, k=3: errors 0, streamer counter 79, datapath counter 73

`--trace="snax_acc0:<file>"` gives the streamer's and the datapath's starts
and ends, and per mover the cycle classes and the highest queue counts.
