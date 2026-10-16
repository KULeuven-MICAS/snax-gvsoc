# The plain winner check

SG7 round 4 (`docs/plans/SG7.md`): the crossbar's plain pick
(`snax/snax_plain_arb.hpp`, the code `snax_tcdm_xbar.cpp` runs) against
common_cells v1.40.0's `rr_arb_tree`, as `stream_xbar` instantiates it in
snax_cluster's plain interconnect (`FairArb`, `LockIn`, `AxiVldRdy`, no
external priority), per cycle under the same random stimulus. Run by hand;
not in `make regress` or CI. The sparse pick has its own check,
`../sparse_arb/`.

- `plain_arb_top.sv` wraps the tree with those parameters and one-bit data.
- `tb.cpp` drives it through Verilator and the header beside it: each input
  holds its request until granted (as the interconnect's masters do, and as
  `LockIn` assumes), new requests and `gnt_i` (the bank's ready; low is a
  refusal) at random, in phases of 500 cycles with their own inputs,
  request and refusal rates. Per cycle it compares the tree's `req_o` and
  `idx_o` with the model's pick and, per requesting input, its `gnt_o` with
  the model's. common_cells' assertions are on (`--assert`), `lock` and
  `lock_req` among them.
- `run.sh` builds both into a folder and runs them.

## Running

In snax_cluster's image `d3d8f5572ff4` (Verilator 5.024), from snax-gvsoc's
root, with the parent folder mounted; `COMMON_CELLS` is the checkout the
RTL build took (`.bender/git/checkouts/common_cells-*` in snax_cluster at
the pin):

    run.sh COMMON_CELLS NUM_IN OBJ_DIR [CYCLES [SEED]]

The targets' crossbar has 15 inputs (12 SNAX ports, two cores, AXI):

    CC=../snax_cluster/.bender/git/checkouts/common_cells-02aa01ee4a3b2e52
    tests/snax/plain_arb/run.sh $CC 15 build/plain_arb/15 100000 1

It prints what the stimulus covered (selections, contested ones, ones after
a refusal, and of those the ones with a request that came during the lock)
and the differences; exit 1 on any.

`MODEL_DIR`, if set, is a folder whose `snax_plain_arb.hpp` is used instead
of `snax/`'s: a copy with a rule broken, which the check must catch, e.g.
the refused winner losing its turn:

    mkdir -p build/broken
    sed 's/        this->lock = true;/        this->rr_q = this->next_rr(this->req_d);/' \
        snax/snax_plain_arb.hpp > build/broken/snax_plain_arb.hpp
    MODEL_DIR=$PWD/build/broken tests/snax/plain_arb/run.sh $CC 15 build/plain_arb/broken
