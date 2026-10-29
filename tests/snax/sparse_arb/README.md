# The winner check

SG7 step 5 (`docs/plans/SG7.md`): the crossbar's sparse pick (`snax/snax_sparse_arb.hpp`, the code `snax_tcdm_xbar.cpp` runs) against snax_cluster's elaborated `SparseInterconnect.sv`, per bank and cycle, under the same random stimulus. Run by hand; not in `make regress` or CI.

- `tb.cpp` drives the module through Verilator and the header beside it: random valid, banks, priority bits and bank `ready` (refusals), in phases of 500 cycles with their own load, bank spread, priority and refusal rates. Each input's bank-local address is its own index, so the bank's request address names the selection, also in a refused cycle. Only accesses the granularity allows. Per cycle and bank it compares the module's request valid and address with the model's pick, and per input its `ready` with the model's (picked, not refused).
- `ports.py` writes `ports.h`: the module's input and bank counts and accessors for its per-port signals.
- `run.sh` builds both into `<module dir>/check/` and runs them.

## Running

In snax_cluster's image `d3d8f5572ff4` (`ghcr.io/kuleuven-micas/snax:main`; it has Verilator 5.024, no Icarus), from snax-gvsoc's root, with the parent folder mounted:

    run.sh MODULE_SV MODULE_CONFIG [MODEL_CONFIG [CYCLES [SEED]]]

`MODULE_CONFIG` is the `sparse_config` the module was elaborated with; `MODEL_CONFIG` the model's, the same by default, or the module's first ports only, the other inputs then held idle. The modules of SG7 step 2:

    A="[[12, 1], [1, 1], [1, 1], [1, 1]]"
    M="[[12, 1], [8, 8], [1, 1], [1, 1], [1, 1]]"
    tests/snax/sparse_arb/run.sh build/sg7/alu/SparseInterconnect.sv "$A"
    tests/snax/sparse_arb/run.sh build/sg7/mixed/SparseInterconnect.sv "$M"
    tests/snax/sparse_arb/run.sh build/sg7/alu/SparseInterconnect.sv "$A" "[[12, 1]]"

It prints what the stimulus covered (selections, contested ones, ones the priority decided, ones after a refusal and after an idle cycle) and the differences; exit 1 on any.
