# Tutorial 0: a system from scratch

You describe a minimal SoC in one Python file (clock, core, router, memory,
ELF loader), build GVSoC for it, and run a `Hello` program on it. Every later
tutorial extends this file.

This is GVSoC developer tutorial 0, rewritten against the pinned source
(gvsoc `93cedc4`). The tutorial text in GVSoC's own `tutorials.rst` and on the
website is out of date (`parser` and `options` arguments, `remove_offset`,
the `gvsoc --binary` launcher). The file in the tutorial's `solution/`
directory is the working reference, and this page follows it.

Time: about 30 minutes, of which 2 minutes is the build.

## What you need

- The snax-gvsoc container, with the repo mounted at `/work` and
  `GVSOC_WORKDIR=/work/build` (see `docs/notes/NOTES.md`).
- GVSoC already built once for the `snitch` target (GVS1 step 2). This is not
  strictly needed, but it makes the build here short.

In every new container:

```
source gvsoc/sourceme.sh
export GVSOC_ROOT=/work/gvsoc
```

## The system

```
  Rv64 (top)
  +--------------------------------------------------------------+
  |  clock (100 MHz) ----clock----> soc                          |
  |                                                              |
  |  soc                                                         |
  |  +--------------------------------------------------------+  |
  |  |  loader --out--------+                                 |  |
  |  |    |  start, entry   |                                 |  |
  |  |    v                 v                                 |  |
  |  |  host --fetch-->  ico (router) --mem--> mem (1 MB)     |  |
  |  |       --data--->   0x0000_0000 .. 0x000f_ffff          |  |
  |  |       --data_debug->                                   |  |
  |  |  gdbserver                                             |  |
  |  +--------------------------------------------------------+  |
  +--------------------------------------------------------------+
```

| Instance | Generator class | What it is |
|---|---|---|
| `clock` | `vp.clock_domain.Clock_domain` | Clock generator, 100 MHz |
| `soc/host` | `cpu.iss.riscv.Riscv` | RV64 core, modelled by the instruction set simulator (ISS) |
| `soc/ico` | `interco.router.Router` | Memory-mapped router |
| `soc/mem` | `memory.memory.Memory` | 1 MB memory |
| `soc/loader` | `utils.loader.loader.ElfLoader` | Copies the ELF into memory, then starts the core |
| `soc/gdbserver` | `gdbserver.gdbserver.Gdbserver` | Optional GDB server |

The generator classes are found by their Python module path under the GVSoC
module roots: `cpu.iss.riscv` is `gvsoc/core/models/cpu/iss/riscv.py`,
`interco.router` is `gvsoc/core/models/interco/router.py`, and so on.

## Step 1: copy the tutorial out of the GVSoC tree

Working copies live in `tutorials/` at the repo root so the submodule stays
clean. From `/work`:

```
mkdir -p tutorials && cd tutorials
T=/work/gvsoc/engine/docs/developer_manual/tutorials
cp -r $T/utils $T/0_how_to_build_a_system_from_scratch .
cd 0_how_to_build_a_system_from_scratch
```

`utils/` is a small bare-metal runtime (start-up code, linker script,
`printf`) shared by all tutorials. The directory now holds `Makefile`,
`main.c`, `testset.cfg` and `solution/`.

## Step 2: write the generator

Create `my_system.py` next to the `Makefile`. `make prepare` does this by
copying `solution/my_system.py`; the content is below either way.

```python
import gvsoc.systree
import gvsoc.runner

import cpu.iss.riscv
import memory.memory
import vp.clock_domain
import interco.router
import utils.loader.loader
import gdbserver.gdbserver
from gvrun.parameter import TargetParameter


GAPY_TARGET = True

class Soc(gvsoc.systree.Component):

    def __init__(self, parent, name, binary):
        super().__init__(parent, name)

        # Main memory
        mem = memory.memory.Memory(self, 'mem', size=0x00100000)

        # Main interconnect
        ico = interco.router.Router(self, 'ico')
        ico.o_MAP(mem.i_INPUT(), 'mem', base=0x00000000, size=0x00100000, rm_base=True)

        # The core: fetch, data and debug accesses all go to the router
        host = cpu.iss.riscv.Riscv(self, 'host', isa='rv64imafdc', binaries=[binary])
        host.o_FETCH     (ico.i_INPUT    ())
        host.o_DATA      (ico.i_INPUT    ())
        host.o_DATA_DEBUG(ico.i_INPUT    ())

        # ELF loader: runs first, then gives the core its entry point and
        # tells it to start
        loader = utils.loader.loader.ElfLoader(self, 'loader', binary=binary)
        loader.o_OUT     (ico.i_INPUT    ())
        loader.o_START   (host.i_FETCHEN ())
        loader.o_ENTRY   (host.i_ENTRY   ())

        gdbserver.gdbserver.Gdbserver(self, 'gdbserver')


# Wrapper that owns the clock, so that it reaches every component in Soc
class Rv64(gvsoc.systree.Component):

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        binary = TargetParameter(
            self, name='binary', value=None, description='Binary to be simulated'
        ).get_value()

        clock = vp.clock_domain.Clock_domain(self, 'clock', frequency=100000000)
        soc = Soc(self, 'soc', binary)
        clock.o_CLOCK    (soc.i_CLOCK    ())


# The top target that the launcher instantiates
class Target(gvsoc.runner.Target):

    gapy_description = "Router test"
    model = Rv64
    name = "test"
```

Reading it from the bottom up:

- **`Target`** is what `gvrun --target=my_system` looks for. The file name
  is the target name. `GAPY_TARGET = True` marks the file as a target, and
  `model` names the top component class.
- **`Rv64`** is a thin wrapper with two jobs. It declares the `binary`
  parameter, which is what `gvrun --parameter binary=<elf>` sets. It also
  creates the clock and binds it to `soc`. A clock bound to a component is
  inherited by everything inside it, so no other clock wiring is needed.
- **`Soc`** is the real system. Each component is created with its parent
  (`self`) and a name; the names give the paths you see in traces
  (`/soc/host`, `/soc/ico`).

Three things to know about the wiring:

- **Ports.** `i_X()` returns a handle to an input port, for example
  `ico.i_INPUT()` or `host.i_FETCHEN()`. `o_Y(handle)` binds an output port
  to it, for example `host.o_FETCH(...)` or `loader.o_START(...)`. Every
  binding in this file has that form. Where these methods come from and how
  to list them is in [Ports](#ports-finding-them-and-what-is-checked).
- **The router map.** `o_MAP` binds a router output and attaches an address
  range to it. Requests whose address falls in `base .. base+size-1` go to
  that output. `rm_base=True` subtracts `base`, so the memory receives a
  local offset.
- **The loader.** GVSoC has no back door for loading programs. The loader
  is a component that writes the ELF into memory through the router like
  any other master, then drives two wires on the core: the entry address
  and fetch enable.

## Step 3: build GVSoC for this target

```
make gvsoc
```

This runs the top-level GVSoC build with `TARGETS=my_system` and
`MODULES=$(CURDIR)`, so GVSoC can find `my_system.py`.

Expected: near the top,

```
-- Generating GVSOC config to /work/build/build/gvsoc/configs/my_system.config with command:
```

and a long list of `-- Up-to-date:` install lines at the end. About 2 minutes
on 2 cores after a `snitch` build; most of it is the RV64 core model.

If `my_system.py` is missing or has a Python error, the build stops here with
`RuntimeError: Invalid target specified: my_system` or the Python traceback.

Do not pass `BUILDDIR=`. Without it the tutorial shares `/work/build` with
the `snitch` build, and the `snitch` target still runs afterwards. With it you
get a second full GVSoC build under `/work/build/<name>`.

## Step 4: compile the program and run it

```
make all
make run
```

`make all` compiles `main.c` with the runtime in `../utils` into
`/work/build/test/test`. `make run` is:

```
gvrun --target-dir=$(CURDIR) --target=my_system --work-dir=/work/build/work \
    --parameter binary=/work/build/test/test run
```

Expected: the `gvrun` command line, then

```
Hello
```

## Step 5: look at the instruction trace

```
make run runner_args="--trace=insn" > /work/build/t0_insn.log 2>&1
wc -l /work/build/t0_insn.log
sed -n 2,4p /work/build/t0_insn.log
tail -2 /work/build/t0_insn.log
```

Expected: 231 lines. The first instruction:

```
30000: 3: [/soc/host/insn] _start:5   M 0000000000000c04 auipc   sp, 0x0   sp=0000000000000c04
```

and the last one an `ebreak` in `exit:81` at `2980000: 298`.

The columns are: time in picoseconds, cycle number, trace path, source
function and line, privilege mode, address, instruction, and the registers
written and read. 100 MHz is 10000 ps per cycle, and this core model runs one
instruction per cycle. `--trace=` takes a regular expression matched against
the trace path.

## Step 6: look at what the build and the run produced

```
cat /work/build/build/gvsoc/configs/my_system.tree.cpp
grep -n '"mappings"' -A8 /work/build/work/gvsoc_config.json
ls /work/build/install/models | grep gen_
```

Expected:

- `my_system.tree.cpp`: 43 lines. `_bindings_soc` has seven entries, one per
  binding in `Soc`, for example
  `{"host", "fetch", "ico", "input", "io", "io"}` and
  `{"loader", "start", "host", "fetchen", "wire<bool>", "wire<bool>"}`.
- The `grep`: the `mem` mapping with `"base": 0` and `"size": 1048576`.
- The `ls`: `gen_memory_memory_cpp_<hash>.so`,
  `gen_interco_router_router_common_cpp_<hash>.so` and
  `gen_isa_rv64imafdc_<hash>.so`, next to the Snitch ones.

## Step 7: change a value without rebuilding

In `my_system.py`, change both `size=0x00100000` to `size=0x00200000` (the
`Memory` line and the `o_MAP` line). Then only:

```
make run
```

Expected:

```
Warning: installed platform tree /work/build/install/lib/libplatform_tree_my_system.so does not match the live system tree, falling back to the JSON config path (rebuild the target to regenerate the tree).
Hello
```

The `grep` from step 6 now shows `2097152`. Restore the file with
`make prepare`; `make run` then prints `Hello` with no warning.

The warning is not a problem here. The run used the new size, and the
instruction trace is identical to the one from a rebuilt system. What the
warning means and when a rebuild is needed is in
[What needs a rebuild](#what-needs-a-rebuild).

## How it works

The Python generator runs twice.

**At build time.** CMake calls `gapy --target=my_system ... components`,
which executes `my_system.py` and writes two files in
`/work/build/build/gvsoc/configs/`:

- `my_system.config`: the C++ models the system needs. A generator declares
  them with `add_sources([...])`. Each one is compiled into its own `.so` in
  `/work/build/install/models`, named by a hash of its sources and compile
  flags, so two systems that use the same model share the library.
- `my_system.tree.cpp`: the instance tree and all bindings as constant C++
  data, compiled into `libplatform_tree_my_system.so`.

**At run time.** `gvrun` executes the script again with the parameter values
from the command line and writes `gvsoc_config.json` in the work directory.
That file holds the properties of each instance: the memory size, the router
mappings, the binary path. The launcher then loads the model libraries,
creates the instances following the tree, binds the ports, and gives each
instance its properties.

This split explains step 7; see [What needs a rebuild](#what-needs-a-rebuild).

**Port types.** Each binding has a signature on both ends, the last two
columns in `my_system.tree.cpp`. This system uses three: `io` for
memory-mapped requests, `wire<T>` for a plain value, and `clock`.

**Boot.** At cycle 1 the loader sends the ELF contents to the router as one
write request (0x2f3c bytes at address 0x4, visible with
`--trace=ico/trace`). It then sets the entry address and raises fetch enable,
and the core runs its first instruction at cycle 3.

**Output.** There is no UART in this system. `printf` and `exit` use
semihosting: the runtime executes an `ebreak` sequence that the core model
catches and handles on the host. That is the `ebreak` at the end of the
trace.

## The core model (ISS)

ISS stands for instruction set simulator. It is GVSoC's CPU model
(`gvsoc/core/models/cpu/iss/`): C++ that fetches each instruction of the ELF,
decodes it, and applies its effect to a software copy of the registers. It
models what an instruction does, not the pipeline that does it. Timing is a
count added on top: one cycle per instruction by default, plus extra cycles
for things like a memory request that comes back with latency. That is why
the trace in step 5 shows one instruction per cycle.

The parts, by file name in `iss/src/`: `decode.cpp` and `insn_cache.cpp`
(decoding, each address decoded once), `regfile.cpp` and `csr.cpp`,
`prefetch/` and `lsu.cpp` (these send the requests on the `fetch` and `data`
ports), `exec/` (the execution loop) and `timing.cpp`. `iss/isa_gen/`
generates the decoder from the ISA string, which is where the
`isa_rv64imafdc_<hash>` library in step 6 comes from. The Snitch cores are
variants of the same ISS (`iss/src/snitch*`).

## Ports: finding them and what is checked

There is no single port list like a Verilog module header. Ports are declared
in two places:

- **In the C++ model**, where they really exist. The constructor calls
  `new_master_port("name", ...)` or `new_slave_port("name", ...)`.
- **In the Python generator**, as `i_X` / `o_Y` methods. Each one wraps one
  C++ port name and a type signature. `host.i_FETCHEN()` returns
  `SlaveItf(self, 'fetchen', signature='wire<bool>')`, and
  `loader.o_START(itf)` calls
  `self.itf_bind('start', itf, signature='wire<bool>')`. The `i_` / `o_`
  prefix is a naming convention, not a language feature.

The generator's methods are the nearest thing to a module header. Three ways
to list the ports of a component:

```
# Python side: the methods, with a docstring under most of them
grep -n "def [io]_[A-Z_]*(" /work/gvsoc/core/models/cpu/iss/riscv.py
grep -n "def [io]_[A-Z_]*(" /work/gvsoc/core/models/utils/loader/loader.py

# C++ side: the real ports
grep -n "new_slave_port\|new_master_port" /work/gvsoc/core/models/memory/memory.cpp

# At run time: every port an instance created
make run runner_args="--trace=host" 2>&1 | grep "New .* port"
```

The first `grep` shows 14 methods for the core, among them `o_FETCH`,
`o_DATA`, `o_DATA_DEBUG`, `i_FETCHEN`, `i_ENTRY`, `i_IRQ` and `o_OFFLOAD`.
The docstrings give the C++ port type and say which ports must be bound.
`i_CLOCK`, `i_RESET`, `i_POWER` and `i_VOLTAGE` come from the base
`Component` class, so every component has them.

The Python list can be incomplete. `memory.cpp` creates `input`, `power_ctrl`
and `meminfo`, but `memory.py` only has `i_INPUT`. A port without a method
can still be bound by name:
`gvsoc.systree.SlaveItf(mem, 'meminfo', signature='io')`.

Nothing in GVSoC works out the right connections for you; they come from the
docstrings and from existing targets. What GVSoC checks, tried on this system:

| Mistake | What happens |
|---|---|
| Method name misspelled (`host.i_FETCH_EN()`) | Python `AttributeError: ... Did you mean: 'i_FETCHEN'?`, before the simulation starts |
| Wrong type (`loader.o_START(host.i_ENTRY())`) | `Invalid signature (master: wire<bool>@soc/loader->start, slave: wire<uint64_t>@soc/host->bootaddr)` |
| Port name that the C++ model does not have | `Binding from invalid slave port (master: loader / start, slave: host / nosuchport)`, aborts at start |
| `host.o_DATA` left out | `/soc/host/wrapper Data master port is not connected`, aborts at start; this check is written in the core model |
| `host.o_DATA_DEBUG` left out | No message, prints `Hello`; the port is only needed for GDB |
| `loader.o_START` or `loader.o_ENTRY` left out | No message, and the simulation never ends |

Names and types are checked. Completeness is not, unless the author of the
model wrote a check. Two ports of the same type bound the wrong way round
also pass. A component of our own should check its mandatory ports in C++,
as the core does for `data`.

## What needs a rebuild

Besides the instances and bindings, the compiled tree
(`libplatform_tree_my_system.so`) holds some parameter values, such as the
size and latency of a `Memory`. At run time GVSoC renders the tree again
from the current script and compares a hash with the one stored at build
time. When they differ it prints the warning from step 7, ignores the
compiled tree and builds the same system from `gvsoc_config.json`, which is
always written fresh. The run therefore uses the new values.

| Change | Rebuild? |
|---|---|
| A value: memory size, router mapping | No |
| Shape, with models that are already compiled: more or fewer instances, other bindings | No |
| A model variant that was never compiled: other sources or compile flags | Yes |
| Any C++ edit | Yes |

The second row was checked on the `snitch` target by changing its L1 from 32
banks to 16 and to 64 in the installed generator: all three ran without a
rebuild, with the same trace length and the same run time.

The third row fails clearly at start-up. For example
`Router(self, 'ico', synchronous=False)` uses another source file, so its
library does not exist yet:

```
Couldn't find component (name: gen_interco_router_router_common_cpp_<hash>, ...)
```

One caveat, from a comment in `gvsoc/engine/python/gvsoc/runner_gvrun2.py`:
the JSON path only works for models that read their parameters from JSON. A
model that only reads its compiled config gets uninitialised values. `Memory`
and the clock have a JSON fallback in their C++
(`if (!this->has_tree_config())`), and the router reads JSON only, so this
system and the stock `snitch` target are safe. Other models with a compiled
config have not been checked. Rebuilding once a configuration is settled
removes the warning and the question.

## SNAX-MODEL counterparts

| GVSoC | SNAX-MODEL |
|---|---|
| `my_system.py`, the Python generator of a target | Cluster / platform file |
| `gvsoc_config.json` in the work directory | The resolved design point |
| `Router` with its `o_MAP` entries | xbar |

The `Router` is a general address-decoding interconnect, closest to an AXI
crossbar. It is not the TCDM crossbar of the Snitch cluster. In GVSoC's
`snitch` target the TCDM path is three models in a row: a `Router` per core
for the address decode, an `L1_interleaver` that picks the bank, and one
`Memory` per bank that models the bank being busy (read from the source; see
the GVS2 findings in `docs/notes/NOTES.md`).

## Things that can go wrong

- **`Invalid target specified: my_system`** during `make gvsoc`:
  `my_system.py` is not next to the `Makefile`, or `GAPY_TARGET = True` is
  missing.
- **`Received error during copy (addr: 0x4, ...)`** from `/soc/loader` at
  run time: the ELF does not fit the router map. Check `base` and `size` in
  `o_MAP` against the `MEMORY` line in `../utils/link.ld`.
- **The simulation never ends and prints nothing**: the core was never
  started. Check that `loader.o_START` and `loader.o_ENTRY` are bound.
- **`Invalid signature`, `Binding from invalid slave port`,
  `... port is not connected`**: a wrong binding; see
  [Ports](#ports-finding-them-and-what-is-checked).
- **`Couldn't find component (name: gen_...)`**: the generator now asks for
  a model variant that was not compiled. Run `make gvsoc` again.
- **The platform tree warning**: see
  [What needs a rebuild](#what-needs-a-rebuild).
- **`gvrun: command not found`**: `source gvsoc/sourceme.sh` was not run in
  this container.
- **GDB.** `make run runner_args=--gdbserver` starts a server on port 12345,
  but the `riscv64-unknown-elf-gdb` in the toolchain needs libpython3.10,
  which Ubuntu 24.04 does not have. GDB is skipped here.

## Files

| Path | What |
|---|---|
| `tutorials/0_how_to_build_a_system_from_scratch/my_system.py` | The generator |
| `tutorials/0_how_to_build_a_system_from_scratch/main.c` | The program |
| `tutorials/utils/` | Shared bare-metal runtime |
| `build/build/gvsoc/configs/my_system.config` | Models to build |
| `build/build/gvsoc/configs/my_system.tree.cpp` | Instances and bindings |
| `build/install/models/` | One `.so` per model |
| `build/test/test` | The compiled program |
| `build/work/gvsoc_config.json` | Properties of this run |

Every tutorial writes to `build/test/test` and `build/work/`, so each one
overwrites the previous.
