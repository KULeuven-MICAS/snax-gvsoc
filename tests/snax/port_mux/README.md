# The port mux's rule

The rule of `snax/snax_port_mux.hpp`, the code `SnaxPortMux` (`snax/snax_port_mux.cpp`) runs for a streamer set whose groups share its movers, against hand-worked cases, with g++ only. `make regress` runs it after `sparse_pick`, as `port_mux`.

- `tb.cpp` sets up `mvt_1_dot2`'s mux at W = 8: groups `dot` (0) and `vadd` (1), movers `reader0`, `reader1`, `writer0` of 8 channels; `dot`'s ports `vmul.a`, `vmul.b` and `vsum.out` (1 channel, on the masked writer), `vadd`'s `vadd.a`, `vadd.b` and `vadd.out`. It checks, after reset and after selecting `vadd`, which ports pass and which are fatal (`SNAX_MUX_NOT_SELECTED`); a port's direction and beat size (its own words or a probe, `SNAX_MUX_WRONG_ACCESS`); the mover's access size; a narrow port's words (a reader's first words, a writer's beat padded with 0); a select refused while the streamer is busy and past the last group, the selection kept; and the configurations refused (a port of no group or mover, wider than its mover, two ports of one group on one mover).
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/port_mux`) and runs it; exit 1 on any difference.
