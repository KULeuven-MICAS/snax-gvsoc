# The winner check

The crossbar's sparse pick (`snax/snax_sparse_arb.hpp`, the code `snax_tcdm_xbar.cpp` runs) against snax_cluster's elaborated `SparseInterconnect.sv`, per bank and cycle, under the same random stimulus (`docs/notes/NOTES.md`, "The crossbar and the sparse interconnect", has the runs that compared them). Run by hand; not in `make regress` or CI.

- `tb.cpp` drives the module through Verilator and the header beside it: random valid, banks, priority bits and bank `ready` (refusals), in phases of 500 cycles with their own load, bank spread, priority and refusal rates. Each input's bank-local address is its own index, so the bank's request address names the selection, also in a refused cycle. Only accesses the granularity allows. Per cycle and bank it compares the module's request valid and address with the model's pick, and per input its `ready` with the model's (picked, not refused).
- `ports.py` writes `ports.h`: the module's input and bank counts and accessors for its per-port signals.
- `run.sh` builds both into `<module dir>/check/` and runs them.

## Running

In snax_cluster's image `d3d8f5572ff4` (`ghcr.io/kuleuven-micas/snax:main`; it has Verilator 5.024, no Icarus), from snax-gvsoc's root, with the parent folder mounted:

    run.sh MODULE_SV MODULE_CONFIG [MODEL_CONFIG [CYCLES [SEED]]]

`MODULE_CONFIG` is the `sparse_config` the module was elaborated with; `MODEL_CONFIG` the model's, the same by default, or the module's first ports only, the other inputs then held idle. The modules NOTES.md's runs elaborated (snax_cluster `9fbf35d`):

    A="[[12, 1], [1, 1], [1, 1], [1, 1]]"
    M="[[12, 1], [8, 8], [1, 1], [1, 1], [1, 1]]"
    tests/snax/sparse_arb/run.sh build/sg7/alu/SparseInterconnect.sv "$A"
    tests/snax/sparse_arb/run.sh build/sg7/mixed/SparseInterconnect.sv "$M"
    tests/snax/sparse_arb/run.sh build/sg7/alu/SparseInterconnect.sv "$A" "[[12, 1]]"

The modules above 64 inputs need a snax_cluster with the 128-input sparse interconnect; they were elaborated in the same image (`d3d8f5572ff4`) from snax_cluster's `hw/chisel` with the Scala caches of the home folder mounted under `/root`, snax-forge's platform (32 banks of 64 bits, 512 rows, 2 cores, so `--userWidth 3` as snaxgen computes it), each `CFG` and `N` below:

    sbt -batch -mem 8192 "runMain snax.sparse_interconnect.SparseInterconnectGen --NumInp N --NumOut 32 --memAddrWidth 9 --tcdmAddrWidth 17 --dataWidth 64 --strbWidth 8 --priorityWidth 1 --userWidth 3 --sparseConfig \"CFG\" --hw-target-dir <snax-gvsoc>/build/port1/<name>"

    M100="[[48, 1], [32, 8], [16, 1], [1, 1], [1, 1], [1, 1], [1, 1]]"   # N 100, 72 inputs per bank
    M128="[[76, 1], [32, 8], [16, 1], [1, 1], [1, 1], [1, 1], [1, 1]]"   # N 128, 100 per bank
    N128="[[108, 1], [16, 1], [1, 1], [1, 1], [1, 1], [1, 1]]"           # N 128, 128 per bank
    tests/snax/sparse_arb/run.sh build/port1/m100/SparseInterconnect.sv "$M100"
    tests/snax/sparse_arb/run.sh build/port1/m128/SparseInterconnect.sv "$M128"
    tests/snax/sparse_arb/run.sh build/port1/n128/SparseInterconnect.sv "$N128"
    tests/snax/sparse_arb/run.sh build/port1/m100/SparseInterconnect.sv "$M100" "[[48, 1], [32, 8]]"
    tests/snax/sparse_arb/run.sh build/port1/m128/SparseInterconnect.sv "$M128" "[[76, 1], [32, 8]]"
    tests/snax/sparse_arb/run.sh build/port1/n128/SparseInterconnect.sv "$N128" "[[108, 1]]"

It prints what the stimulus covered (selections, contested ones, ones the priority decided, ones after a refusal and after an idle cycle, ones at a bank's arbiter input 64 or above and how many of those were contested) and the differences; exit 1 on any.
