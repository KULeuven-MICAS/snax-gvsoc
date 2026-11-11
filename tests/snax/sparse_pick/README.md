# The crossbar's pick at up to 128 inputs

The pick of `snax/snax_sparse_arb.hpp` (`SnaxSparseArb::pick` on `SnaxInputMask`, a `std::bitset<128>`) checked model against model, with g++ only. `make regress` runs it after `group`, as `sparse_pick`. The check against the RTL is `../sparse_arb/` (Verilator, by hand).

- `tb.cpp` drives one arbiter per input count from 1 to 128, four phases of 2000 cycles each with their own rates of valid requests, priority bits, idle cycles (no pick, so the pointer restarts) and refusals (the lock). Every pick is compared with `RefArb`, the rule written as a plain loop over the inputs, and for 1 to 64 inputs also with `OldArb`, the pick on `uint64_t` masks as it was before PORT1 (snax-gvsoc `85552fc4`). Then the sparse configuration at 128 inputs (96 SNAX ports of granularity 1 and 32 of granularity 32: 97 inputs per bank, each reaching its bank) and its refusal of 129 inputs per bank.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/sparse_pick`) and runs it; exit 1 on any difference.

It prints the picks compared (901720 at the seed in `tb.cpp`) and `OK`. A copy of the pick with its round robin starting at the last pick and not after it gives 390586 differences.
