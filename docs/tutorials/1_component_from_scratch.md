# Tutorial 1: a component from scratch

You write your own model: a C++ class and a small Python generator. You map
it at `0x20000000` in the system of tutorial 0 and read it from the program.
This is the smallest version of the register side of an accelerator.

This is GVSoC developer tutorial 1, written against the pinned source (gvsoc
`93cedc4`). The text in GVSoC's `tutorials.rst` matches the `solution/`
directory here, with one slip: it declares the handler once with
`void *__this`, and it must be `vp::Block *__this`.

Time: about 30 minutes, of which 2 to 4 minutes is the build.

## What you need

- The snax-gvsoc container, with the repo mounted at `/work` and
  `GVSOC_WORKDIR=/work/build` (see `docs/notes/NOTES.md`).
- Tutorial 0 done (`docs/tutorials/0_system_from_scratch.md`), with
  `tutorials/utils` in place.

In every new container:

```
source gvsoc/sourceme.sh
export GVSOC_ROOT=/work/gvsoc
```

## The system

Tutorial 0's system with one more router output:

```mermaid
flowchart LR
    subgraph top["Rv64 (top)"]
        clock["clock<br/>100 MHz"]
        subgraph soc["soc"]
            loader["loader<br/>ELF loader"]
            host["host<br/>RV64 core (ISS)"]
            ico["ico<br/>router"]
            mem["mem<br/>1 MB memory"]
            comp["my_comp<br/>new in tutorial 1"]
        end
    end

    clock -- clock --> soc
    loader -- out --> ico
    loader -. "start, entry" .-> host
    host -- fetch --> ico
    host -- data --> ico
    ico -- "mem: 0x0000_0000 .. 0x000F_FFFF" --> mem
    ico -- "comp: 0x2000_0000 .. 0x2000_0FFF" --> comp

    classDef new stroke-width:3px
    class comp new
```

Inside `soc`, solid arrows are `io` bindings (memory-mapped requests) and
the dotted one stands for two `wire` bindings; the arrow into `soc` is the
`clock` binding. Edge labels are port names. The arrow points from
the master port to the slave port.

| Instance | Generator class | What it is |
|---|---|---|
| `soc/my_comp` | `my_comp.MyComp` (new) | Returns a fixed 32-bit value on a read at offset 0 |

The files you add:

| File | What |
|---|---|
| `my_comp.py` | The generator: sources, parameters, ports |
| `my_comp.cpp` | The model |
| `my_system.py` | Tutorial 0's system plus two lines |

Compared with tutorial 0's `my_system.py`, the one here has no `Gdbserver`
inside `Soc`, no `o_DATA_DEBUG` binding and no `GAPY_TARGET = True`. None of
them is needed: nothing in the pinned tree reads `GAPY_TARGET`.

## Step 1: copy the tutorial out of the GVSoC tree

From `/work`:

```
cd tutorials
T=/work/gvsoc/engine/docs/developer_manual/tutorials
cp -r $T/1_how_to_write_a_component_from_scratch .
cd 1_how_to_write_a_component_from_scratch
```

The directory holds `Makefile`, `main.c`, `my_system.py` (tutorial 0's
system, without the component), `testset.cfg` and `solution/`.

`main.c` is already the new program:

```c
int main()
{
    printf("Hello, got 0x%x from my comp\n", *(uint32_t *)0x20000000);
    return 0;
}
```

## Step 2: write the generator

Create `my_comp.py` next to the `Makefile`. `make prepare` copies it, the
C++ file and the finished `my_system.py` from `solution/`; the content is
below either way.

```python
import gvsoc.systree

class MyComp(gvsoc.systree.Component):

    def __init__(self, parent: gvsoc.systree.Component, name: str, value: int):
        super().__init__(parent, name)

        self.add_sources(['my_comp.cpp'])

        self.add_properties({
            "value": value
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')
```

- **`parent` and `name`** are passed by every generator to the base class.
  Any other argument (`value` here) is a parameter of your own.
- **`add_sources`** names the C++ files of the model. This is all the build
  needs to compile the component into its own library.
- **`add_properties`** puts the parameter in the JSON configuration, where
  the C++ code reads it.
- **`i_INPUT`** declares the input port for whoever instantiates the
  component. `'input'` must be the name used in the C++ code, and `'io'` is
  the type that GVSoC checks on a binding.

## Step 3: write the model

Create `my_comp.cpp`. The code is the same as `solution/my_comp.cpp`; the
comments are added here and do not change the build.

```cpp
// vp.hpp: the engine API (vp::Component, traces, clocks, registers).
// io.hpp: the memory-mapped request interface (vp::IoSlave, vp::IoReq).
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>

// One C++ class per model. vp::Component is the base class of every GVSoC
// model; it gives the name, the parent, the clock, traces and the port list.
class MyComp : public vp::Component
{

public:
    // The engine builds the config object; we only pass it to the base class.
    MyComp(vp::ComponentConf &config);

private:
    // Called for every request that arrives on the input port. Static,
    // because the port stores a plain function pointer, not a member pointer.
    // The engine passes the instance back as the first argument.
    static vp::IoReqStatus handle_req(vp::Block *__this, vp::IoReq *req);

    // The input port. A slave port receives requests; its name ("input") is
    // given in the constructor and must match i_INPUT() in my_comp.py.
    vp::IoSlave input_itf;

    // The value returned on a read at offset 0, set from the Python side.
    uint32_t value;
};


MyComp::MyComp(vp::ComponentConf &config)
    : vp::Component(config)
{
    // Tell the port which function handles its requests.
    this->input_itf.set_req_meth(&MyComp::handle_req);
    // Register the port under the name used by the bindings in my_system.py.
    this->new_slave_port("input", &this->input_itf);

    // Read the "value" property that my_comp.py put in the JSON config.
    // A missing property gives 0, with no error.
    this->value = this->get_js_config()->get_child_int("value");
}

vp::IoReqStatus MyComp::handle_req(vp::Block *__this, vp::IoReq *req)
{
    // Get our instance back from the generic pointer.
    MyComp *_this = (MyComp *)__this;

    // req->get_addr() is the offset inside our window: the router already
    // removed the base 0x20000000 (rm_base=True).
    printf("Received request at offset 0x%lx, size 0x%lx, is_write %d\n",
        req->get_addr(), req->get_size(), req->get_is_write());

    // Only a 4-byte read at offset 0 is served. get_data() points to the
    // master's buffer; for a core load it is the destination register itself.
    if (!req->get_is_write() && req->get_addr() == 0 && req->get_size() == 4)
    {
        *(uint32_t *)req->get_data() = _this->value;
    }

    // Done now, no added latency. Anything else is also answered OK and
    // left untouched (see "What the model does not do").
    return vp::IO_REQ_OK;
}


// Entry point of the shared library. When the engine loads
// gen_my_comp_cpp_<hash>.so it looks up this symbol by name and calls it to
// create the instance. extern "C" keeps the name unmangled.
extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new MyComp(config);
}
```

The file has four parts: the includes, the class, the constructor and the
request handler, plus the `gv_new` entry point. They are explained in that
order below, then put on a timeline.

### The includes

| Line | What it brings in |
|---|---|
| `#include <vp/vp.hpp>` | The engine API: `vp::Component`, traces, clock events, registers. `vp` is the engine's namespace (most likely "virtual platform"; the source never spells it out). The headers are in `gvsoc/engine/engine/include/vp/`. |
| `#include <vp/itf/io.hpp>` | The `io` port type used for memory-mapped requests: `vp::IoSlave`, `vp::IoMaster`, `vp::IoReq` and the status values. Each port type has its own header in `vp/itf/` (`wire.hpp`, `clock.hpp`, ...). |

### The class

| Line | What it does |
|---|---|
| `class MyComp : public vp::Component` | Every model is a C++ class derived from `vp::Component`. The base class holds the instance name and path (`/soc/my_comp`), the parent, the clock it inherits, the trace object and the list of ports. `vp::Component` itself derives from `vp::Block`, which is why the handler receives a `vp::Block *`. |
| `MyComp(vp::ComponentConf &config);` | The constructor signature the engine expects. `ComponentConf` carries the instance name, the parent, this instance's JSON config and pointers to the engine's time, trace and power engines. The model never reads it directly; it hands it to the base class. |
| `static vp::IoReqStatus handle_req(vp::Block *__this, vp::IoReq *req);` | The function that serves requests. It has the signature `vp::IoReqMeth` from `io.hpp`. It is `static` because a port stores a plain C function pointer, which cannot point to a member function; the instance comes in as the first argument instead. |
| `vp::IoSlave input_itf;` | The port object. A slave port receives requests; a `vp::IoMaster` would send them. Declaring the member does not create a port in the system yet; `new_slave_port` in the constructor does. |
| `uint32_t value;` | Model state. A real model keeps its registers, buffers and FSM state in members like this one. |

### The constructor

It runs once, when the engine creates the instance, before any binding
exists. Its job is to declare the ports and read the parameters.

| Line | What it does |
|---|---|
| `: vp::Component(config)` | Builds the base part from the engine's config. After this, `this->get_js_config()`, `this->get_path()` and the traces work. |
| `this->input_itf.set_req_meth(&MyComp::handle_req);` | Stores the handler's address in the port. Nothing is called yet. |
| `this->new_slave_port("input", &this->input_itf);` | Registers the port under the name `input`, with this instance as its context (the pointer that will come back as `__this`). The name is what bindings refer to: it must be the name in `i_INPUT()` in `my_comp.py`, or the run stops with `Binding from invalid slave port`. With `--trace=my_comp` this shows up as `New slave port (name: input, ...)`. |
| `this->value = this->get_js_config()->get_child_int("value");` | `get_js_config()` is this instance's part of `gvsoc_config.json`, the `/target/soc/my_comp` object with `"value": 305419896`. `get_child_int` reads one field. A missing field returns 0 without any message (`gvsoc/engine/engine/src/json.cpp`), so a typo in the property name gives a silent 0. `get_child_bool` and `get_child_str` exist too. |

### The request handler

It runs every time a master sends a request that the router maps to this
component, here once, during the program's load from `0x20000000`.

| Line | What it does |
|---|---|
| `MyComp *_this = (MyComp *)__this;` | Gets the instance back. `__this` is the context given in `new_slave_port`, so the cast is safe. |
| `printf(...)` | Prints straight to the host's standard output, with no time stamp and no way to switch it off. Tutorial 3 replaces this with `vp::Trace`, which `--trace` filters. |
| `req->get_addr()` | The address of the access, already relative to this component: the router subtracted the mapping base because of `rm_base=True` in `my_system.py`. The core sent `0x20000000`; the model sees `0x0`. |
| `req->get_size()` | Size in bytes: 4 for `lw`, 1 for `lbu`. |
| `req->get_is_write()` | `true` for a store, `false` for a load. Atomics carry an opcode as well (`get_opcode()`); this model ignores it. |
| `req->get_data()` | A pointer to the master's data. For a store the model reads from it; for a load the model writes into it. The core does not pass a temporary buffer: for a load it passes a pointer to the destination register itself (`Lsu::load` in `gvsoc/core/models/cpu/iss/include/lsu_implem.hpp`, "the target will write directly to the register"). |
| `*(uint32_t *)req->get_data() = _this->value;` | Writes the value into that register. When the handler returns, the load is complete. |
| `return vp::IO_REQ_OK;` | Tells the master that the request is finished, now. The other values are `IO_REQ_INVALID` (error; the core takes a load or store fault), `IO_REQ_PENDING` (the answer comes later through `resp()`) and `IO_REQ_DENIED` (not accepted now; the master waits for a grant). Pending and denied are covered in tutorial 7. |

Things the request can carry that this model does not use: a latency
(`set_latency()`, in cycles, added on top of the current one), which is the
simplest way to make an access cost time; `get_initiator()`, the hart ID of
the core that sent it; and a debug flag for GDB accesses.

### The entry point

| Line | What it does |
|---|---|
| `extern "C" vp::Component *gv_new(vp::ComponentConf &config)` | The engine opens `gen_my_comp_cpp_<hash>.so` and looks up the symbol `gv_new` by name (`gvsoc/engine/engine/src/component.cpp`). `extern "C"` keeps the name as is; without it, C++ name mangling would hide it. Each model library has exactly one. |
| `return new MyComp(config);` | Creates the instance. The engine owns it from here. |

### When each part runs

The order, seen with `make run runner_args="--trace=my_comp"` and read from
the engine source:

1. **Start-up, before time 0.** The engine loads the library, calls
   `gv_new`, and the constructor runs. The trace shows the five
   `New slave port` lines: `clock`, `reset`, `power_supply` and `voltage`
   from the base class, then `input` from our constructor.
2. **Binding.** Once every instance exists, the engine connects the ports
   from the platform tree (`Creating final bindings`). For an `io` binding it
   copies the slave's handler pointer and context into the master port
   (`IoMaster::bind_to` in `io.hpp`).
3. **Reset.** `Reset (active: 1)` then `Reset (active: 0)` at cycle 0. A
   model can override `reset(bool active)` to clear its state; this one has
   nothing to clear.
4. **Simulation.** At cycle 158 the core executes `c.lw`; the router calls
   `handle_req`, which writes the register and returns. No event is
   scheduled; the call finishes inside that instruction.

## Step 4: add the component to the system

In `my_system.py`, add the import at the top:

```python
import my_comp
```

and in `Soc`, after the `mem` mapping:

```python
        comp = my_comp.MyComp(self, 'my_comp', value=0x12345678)
        ico.o_MAP(comp.i_INPUT(), 'comp', base=0x20000000, size=0x00001000, rm_base=True)
```

## Step 5: build GVSoC for this system

```
make gvsoc 2>&1 | tee /work/build/t1_build.log | grep my_comp
```

Expected: four compile lines and four install lines for the new model, one
per build variant (`optim`, `debug`, `asserts`, `profile`):

```
[ 11%] Building CXX object engine/CMakeFiles/gen_my_comp_cpp_<hash>_debug.dir/.../my_comp.cpp.o
...
-- Installing: /work/build/install/models/gen_my_comp_cpp_<hash>.so
-- Installing: /work/build/install/models/asserts/gen_my_comp_cpp_<hash>.so
-- Installing: /work/build/install/models/profile/gen_my_comp_cpp_<hash>.so
-- Installing: /work/build/install/models/debug/gen_my_comp_cpp_<hash>.so
```

The hash was `221325801` on the check machine; it may differ with another
path.

This build is not short: 4 min 1 s on 2 cores, 197 files, the same as a
first build of tutorial 0. The tutorial directory is passed to the build as
a module root (`MODULES=$(CURDIR)`), which is an include path of every
model. Moving from tutorial 0's directory to this one changes that path, so
all models of `my_system` recompile, the RV64 core included. Expect this once
per tutorial. Rebuilds inside one tutorial are short; see step 9.

## Step 6: compile the program and run it

```
make all
make run
```

Expected: the `gvrun` command line, then

```
Received request at offset 0x0, size 0x4, is_write 0
Hello, got 0x12345678 from my comp
```

The first line is the `printf` in the model, the second the `printf` in the
simulated program.

## Step 7: see the access in the traces

```
make run runner_args="--trace=insn --trace=ico" 2>&1 | grep -B2 -A1 "Received request"
```

Expected (colour codes and padding removed):

```
1570000: 157: [/soc/host/insn] main:6  M 0000000000002f28 lui   a5, 0x20000000   a5=0000000020000000
1580000: 158: [/soc/ico/trace] Received IO req (offset: 0x20000000, size: 0x4, is_write: 0)
Received request at offset 0x0, size 0x4, is_write 0
1580000: 158: [/soc/host/insn] main:6  M 0000000000002f2c c.lw  a1, 0(a5)   a1=0000000012345678  a5:0000000020000000  PA:0000000020000000
```

The router receives the request with the full address, the model receives
it with offset 0, and the load ends with the value in `a1`. All three are in
cycle 158.

The router's address table and the ports of the model:

```
make run runner_args="--trace=ico" 2>&1 | grep -A2 "Building router table"
make run runner_args="--trace=my_comp" 2>&1 | grep "New .* port"
```

Expected: the two ranges, `0x0 : 0x100000 -> mem` and
`0x20000000 : 0x20001000 -> comp`; then five slave ports, of which `clock`,
`reset`, `power_supply` and `voltage` come from the base class and `input`
is ours.

## Step 8: look at what the build and the run produced

```
grep -n my_comp /work/build/build/gvsoc/configs/my_system.tree.cpp
grep -n my_comp /work/build/build/gvsoc/configs/my_system.config
grep -n '"my_comp"' -A5 /work/build/work/gvsoc_config.json
```

Expected:

- `my_system.tree.cpp`: the binding
  `{"ico", "comp", "my_comp", "input", "io", "io"}` and the instance
  `{"my_comp", nullptr, nullptr, 0, "gen_my_comp_cpp_<hash>", ...}`.
- `my_system.config`: `gen_my_comp_cpp_<hash>` in `CONFIG_COMPONENTS`, and
  `CONFIG_SRCS_gen_my_comp_cpp_<hash>=` with the full path of `my_comp.cpp`.
- `gvsoc_config.json`: `"value": 305419896` (0x12345678) and
  `"ports": ["input"]`.

## Step 9: what needs a rebuild

**The value: no rebuild.** In `my_system.py`, change `value=0x12345678` to
`value=0xcafe0001`, then only:

```
make run
```

Expected: `Hello, got 0xcafe0001 from my comp`, with no platform tree
warning. The value is only in `gvsoc_config.json`, which is written at every
run; the second field of the `my_comp` line in `my_system.tree.cpp` is
`nullptr`, so the compiled tree holds no parameter for it. Change it back.

**The C++: a short rebuild.** Edit `my_comp.cpp` (for example the text of
the `printf`), then:

```
make gvsoc
make run
```

Expected: 4 files compiled (the model, once per variant), about 7 s on 2
cores. The library keeps its name: the hash covers the source names and the
compile flags, not the content of the file.

## How it works

**From generator to library.** `add_sources(['my_comp.cpp'])` adds a
component entry to `my_system.config`. The path is looked up in the module
roots, and the Makefile passes the tutorial directory as one
(`MODULES=$(CURDIR)` at build time, `--target-dir=$(CURDIR)` at run time).
That is also why `import my_comp` works. CMake builds one shared library per
entry, in four variants; a normal run loads the one directly in
`build/install/models`.

**From library to instance.** At start the engine walks the platform tree.
For `my_comp` it opens `gen_my_comp_cpp_<hash>.so`, looks up the C symbol
`gv_new` and calls it (`gvsoc/engine/engine/src/component.cpp`). The
constructor runs, creates the port and reads `value` from the JSON
configuration of this instance with `get_js_config()`.

**Binding.** After all instances exist, the engine connects the ports listed
in the tree. For an `io` binding this copies the slave's handler pointer and
instance pointer into the master port. The `--trace=ico` output shows it:
`Creating final binding (/soc/ico:comp -> /soc/my_comp:input)`.

**A request is a function call.** There is no event and no queue. The
master's `req()` is one indirect call
(`gvsoc/engine/engine/include/vp/itf/io.hpp`, `IoMaster::req`):

```
core, executing c.lw
  -> Router::handle_req       finds the mapping, subtracts the base
     -> MyComp::handle_req    writes the value into the buffer, returns IO_REQ_OK
  <- IO_REQ_OK
```

The router does not copy anything: it changes the address in the request and
passes the same request on (`req_forward`). The whole chain runs inside the
core's execution of that one instruction, which is why step 7 shows
everything in cycle 158.

**Timing.** `IO_REQ_OK` with nothing else set means zero added latency. The
request also has a latency field and there is an `IO_REQ_PENDING` status for
answers that come later; tutorial 7 covers both.

**What the model does not do.** The handler returns `IO_REQ_OK` for every
request and only acts on a 4-byte read at offset 0. Tried on this system:

| Access from the program | What happens |
|---|---|
| 4-byte read at offset 4 | `IO_REQ_OK`, register untouched: the program gets the old content of `a1` (`0x978` in the run), because `lw` passes the register itself and does not clear it first |
| 1-byte read at offset 0 | The size check fails, nothing written: reads `0x0`, because `lbu` clears the register before the request (zero extension) |
| 4-byte write at offset 0 | Accepted and dropped; the next read still gives the value |
| Read at `0x30000000`, not mapped | The router returns `IO_REQ_INVALID`; see below |

**`IO_REQ_INVALID`.** A model that returns `vp::IO_REQ_INVALID` for accesses
it does not handle makes the error visible. On this RV64 core the load then
raises a load fault, the runtime's `handle_exception` calls `exit(1)`, and
`gvrun` ends with:

```
Input error: Platform returned an error (exitcode: 1)
```

There is no message that names the address; `--trace=insn` shows the jump to
`handle_exception` right after the load. The stricter handler, tried here:

```cpp
    if (!req->get_is_write() && req->get_addr() == 0 && req->get_size() == 4)
    {
        *(uint32_t *)req->get_data() = _this->value;
        return vp::IO_REQ_OK;
    }
    return vp::IO_REQ_INVALID;
```

This was not tried on the Snitch target, whose core may treat an invalid
access differently.

## SNAX-MODEL counterparts

| GVSoC | SNAX-MODEL |
|---|---|
| `MyComp` behind a router mapping | A register window with one read-only register |
| `value` passed in `my_system.py`, stored in `gvsoc_config.json` | A field of the accelerator entry in the cluster file, resolved into the design point |
| `handle_req` called by the master | A register read served by the window at the time of the access |

One difference to keep in mind: the handler has no time of its own. It runs
inside the instruction of the core that sends the request. A model that
works over several cycles needs clock events, which is tutorial 6.

## Things that can go wrong

- **`ModuleNotFoundError: No module named 'my_comp'`**, then
  `Dependency 'my_comp' of the target module 'my_system' is missing`, during
  `make gvsoc`: `my_comp.py` is not next to `my_system.py`.
- **`couldn't find gv_new loaded module (module: gen_my_comp_cpp_<hash>)`**
  at run time, exit code 134: the `extern "C" gv_new` function is missing
  from `my_comp.cpp`. The build passes without it.
- **`Binding from invalid slave port`** at start: the name in `i_INPUT`
  (`'input'`) is not the name given to `new_slave_port`.
- **`Invalid signature`**: the signature in `i_INPUT` is not `'io'`.
- **`Input error: Platform returned an error (exitcode: 1)`** with no other
  message: the program took a load or store fault. Either the address is not
  in the router map (check `base` and `size` in `o_MAP`), or a model returned
  `IO_REQ_INVALID`. A mapping smaller than the access also ends this way:
  the router splits the request and the second part is not mapped.
- **The program reads a wrong value and nothing complains**: the access did
  not match what the handler checks (offset, size, direction), and the
  handler returned `IO_REQ_OK` anyway.
- **The value does not change after an edit of `my_system.py`** when the
  commands are run from a script in quick succession: delete `__pycache__/`
  next to the generator first.
- **The build takes minutes after switching tutorials**: expected, see
  step 5.

## Files

| Path | What |
|---|---|
| `tutorials/1_how_to_write_a_component_from_scratch/my_comp.py` | The generator of the component |
| `tutorials/1_how_to_write_a_component_from_scratch/my_comp.cpp` | The model |
| `tutorials/1_how_to_write_a_component_from_scratch/my_system.py` | The system |
| `tutorials/1_how_to_write_a_component_from_scratch/main.c` | The program |
| `build/install/models/gen_my_comp_cpp_<hash>.so` | The compiled model |
| `build/build/gvsoc/configs/my_system.config` | Models to build |
| `build/build/gvsoc/configs/my_system.tree.cpp` | Instances and bindings |
| `build/work/gvsoc_config.json` | Properties of this run, with `value` |

`build/test/test`, `build/work/` and the `my_system` build are shared with
tutorial 0 and overwritten by this one.