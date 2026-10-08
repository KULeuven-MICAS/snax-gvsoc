# GVSoC API reference

The GVSoC classes and calls used so far, by class, with what each argument
means. GVSoC has no API documentation for most of these; the signatures were
read from the headers and tried in the tutorials. Look here for "what were
the arguments again"; look in `docs/tutorials/` for the walk-through.

Pinned to gvsoc `93cedc4`. Signatures can change with the pin.

Only what has been used is listed, not everything a header offers. The
"Checked" column says how far an entry is trusted:

- **T0** to **T5**: built and run in that tutorial (pages in
  `docs/tutorials/`).
- **read**: read from the source at the pin, not run.

A new step adds its classes here, as it adds an entry to `NOTES.md`.

Headers are relative to `gvsoc/engine/engine/include/`; Python files to
`gvsoc/`.

## Contents

- [Model skeleton: vp::Component](#model-skeleton-vpcomponent)
- [Memory-mapped requests: io](#memory-mapped-requests-io)
- [Wires](#wires)
- [Traces: vp::Trace](#traces-vptrace)
- [VCD signals: vp::Signal](#vcd-signals-vpsignal)
- [Registers: vp::Register](#registers-vpregister)
- [Register maps: vp::regmap](#register-maps-vpregmap)
- [Statistics and sub-blocks](#statistics-and-sub-blocks)
- [Python generator of a component](#python-generator-of-a-component)
- [Python generator of a system](#python-generator-of-a-system)
- [gvrun options](#gvrun-options)
- [Rules of thumb](#rules-of-thumb)

## Model skeleton: vp::Component

`vp/vp.hpp`, `vp/component.hpp`, `vp/block.hpp`.

```cpp
#include <vp/vp.hpp>

class MyComp : public vp::Component
{
public:
    MyComp(vp::ComponentConf &config);
};

MyComp::MyComp(vp::ComponentConf &config) : vp::Component(config) {}

extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new MyComp(config);
}
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `class X : public vp::Component` | Every model. `vp::Component` derives from `vp::Block`, which holds name, path, parent, clock and traces | T1 |
| `X(vp::ComponentConf &config)` | The constructor the engine expects; pass `config` to the base class. Members without a default constructor (signals, registers, regmaps) are built in the initializer list, in declaration order | T1, T4, T5 |
| `extern "C" vp::Component *gv_new(vp::ComponentConf &config)` | The entry point of the model's library; returns `new X(config)`. Without `extern "C"` the run aborts with `couldn't find gv_new loaded module` | T1 |
| `new_slave_port(std::string name, SlavePort *port, void *comp=NULL)` | Registers an input port. `name` is what the Python generator's `SlaveItf(self, name, ...)` refers to. The instance comes back as the handler's first argument | T1 |
| `new_master_port(std::string name, vp::MasterPort *port, vp::Block *comp=NULL)` | Registers an output port, named as in the generator's `itf_bind(name, ...)` | T2 |
| `get_js_config()` | This instance's part of `gvsoc_config.json`: what the generator passed to `add_properties` | T1 |
| `get_js_config()->get_child_int("key")` | One property as an integer. A missing key returns 0 with no message. `get_child_bool`, `get_child_str` and `get("key")->get_int()` also exist | T1; the others read |
| `get_path()`, `get_name()` | `/soc/my_comp` and `my_comp` | read |
| `virtual void reset(bool active)` | Called on reset assert (`true`) and release (`false`). Override to reset model state. Signals and registers are reset by the block itself | read |
| `virtual void start()` | Called once before the simulation starts | read |

GVSoC does not check that a model's ports are bound, unless the model does
it itself.

## Memory-mapped requests: io

`vp/itf/io.hpp`. The port type behind every memory-mapped access. A request
is a direct function call from the master into the slave's handler; it takes
no simulated time unless the handler says so (tutorial 7).

Slave side:

```cpp
#include <vp/itf/io.hpp>

static vp::IoReqStatus handle_req(vp::Block *__this, vp::IoReq *req);
vp::IoSlave input_itf;

// in the constructor
this->input_itf.set_req_meth(&MyComp::handle_req);
this->new_slave_port("input", &this->input_itf);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp::IoSlave` | An input port for requests | T1 |
| `set_req_meth(vp::IoReqMeth *meth)` | Stores the handler. Its type is `vp::IoReqStatus (vp::Block *, vp::IoReq *)`; it is `static`, and the first argument is the instance, to be cast back | T1 |
| `req->get_addr()` | `uint64_t`. The address of the access. Behind a router mapping with `rm_base=True` it is the offset inside the component's window | T1 |
| `req->get_size()` | `uint64_t`. Number of bytes: 4 for `lw` / `sw`, 1 for `lbu` / `sb`, 8 for `ld` / `sd`. GCC splits a misaligned access into smaller ones | T1, T5 |
| `req->get_is_write()` | `bool`. `true` for a store, `false` for a load | T1 |
| `req->get_data()` | `uint8_t *`. The master's data: read from it on a store, write into it on a load. For a load from the core it points at the destination register itself | T1 |
| `req->get_opcode()` | `IoReqOpcode`: `READ`, `WRITE`, and the atomics `LR`, `SC`, `SWAP`, `ADD`, ... | read |
| return `vp::IO_REQ_OK` | The request is done, now | T1 |
| return `vp::IO_REQ_INVALID` | Error. The RV64 core takes a load or store fault; the tutorial runtime exits 1 and `gvrun` prints `Platform returned an error (exitcode: 1)` with no address. Not checked on Snitch | T1 |
| return `vp::IO_REQ_PENDING`, `vp::IO_REQ_DENIED` | The answer comes later through `resp()`; not accepted now, the master waits for `grant()`. Tutorial 7 | read |
| `req->inc_latency(n)`, `set_latency(n)`, `get_latency()` | Cycles this request takes, relative to the current cycle. Tutorial 7 | read |
| `vp::IoMaster`, `req(IoReq *)`, `set_resp_meth`, `set_grant_meth`, `is_bound()` | The master side: a component that issues requests itself (a streamer). Step 15 | read |

An unanswered load keeps what was in the destination: `lw` returns the old
register value, `lbu` returns 0 (T1).

## Wires

`vp/itf/wire.hpp`, implementation in `vp/itf/implem/wire_class.hpp`. A typed
point-to-point signal. `sync` is a direct call into the receiver's handler:
no event, no delay, no stored value.

```cpp
#include <vp/itf/wire.hpp>

vp::WireMaster<bool> notif_itf;                                   // output
vp::WireSlave<bool> in_itf;                                       // input
static void handle_in(vp::Block *__this, bool value);

// in the constructor
this->new_master_port("notif", &this->notif_itf);
this->in_itf.set_sync_meth(&MyComp::handle_in);
this->new_slave_port("in", &this->in_itf);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp::WireMaster<T>` | An output of type `T`. `T` can be a pointer to a class of your own | T2 |
| `master.sync(T value)` | Sends the value: calls the handler of every bound slave, now, nested inside the caller | T2 |
| `master.is_bound()` | `false` when nothing is bound. `sync()` on an unbound master crashes with a segmentation fault, so guard optional outputs | T2 |
| `vp::WireSlave<T>` | An input of type `T` | T2 |
| `slave.set_sync_meth(void (*)(vp::Block *, T value))` | Stores the handler; static, the instance as first argument | T2 |
| `set_sync_meth_muxed(void (*)(vp::Block *, T, int), int id)` | One handler for an array of ports, with the port index as third argument (the stock cluster registers use it for one wire per core) | read |
| `sync_back`, `set_sync_back_meth` | The slave returning a value through a pointer | read |

The signature string in the generator (`'wire<bool>'`) is only a label both
ends must match; GVSoC never compares it with the C++ types. One master can
be bound to several slaves. A pointer sent on a wire that points into the
sender's stack is only valid during the handler.

## Traces: vp::Trace

`vp/trace/trace.hpp`, `vp/trace/block_trace.hpp`. Text lines that GVSoC
prints only when asked, with time, cycle and path in front.

```cpp
vp::Trace trace;

// in the constructor
this->traces.new_trace("trace", &this->trace);

// anywhere
this->trace.msg(vp::TraceLevel::DEBUG, "Received request at offset 0x%lx\n", req->get_addr());
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `traces.new_trace(std::string name, Trace *trace, TraceLevel level = vp::TraceLevel::DEBUG)` | Registers a trace. Its path is the component path plus `name`. `level` is the default level of `msg()` calls without one. A model can have several, each with its own name | T3 |
| `trace.msg(int level, const char *fmt, ...)` | Prints when the trace is enabled and the level passes. `printf` format; GVSoC adds the header | T3 |
| `trace.msg(const char *fmt, ...)` | Same, at the trace's default level | read |
| Levels | `vp::TraceLevel::ERROR`, `WARNING`, `INFO`, `DEBUG`, `TRACE`, from least to most detail | T3 |
| `trace.warning(fmt, ...)`, `trace.fatal(fmt, ...)` | A warning, an error that stops the run | read |
| `vp_warning_always(trace_ptr, fmt, ...)` | A warning printed whatever the options. With the default `werror` it ends the run with exit code 1; `--no-werror` lets it go on. `vp::regmap` uses it for an unknown offset | T5 |

Every component already has a trace called `trace` from `vp::Block` and one
called `comp`; give your own traces other names. Traces are compiled out of
the default build: any `--trace`, `--vcd` or `--event` switches the run to
the debug build, about 3.5 times slower.

## VCD signals: vp::Signal

`vp/signal.hpp`. A value that is written to the VCD file on every change.

```cpp
#include <vp/signal.hpp>

vp::Signal<uint32_t> vcd_value;

// in the initializer list
vcd_value(*this, "status", 32)
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Signal(Block &parent, std::string name, int width, bool do_reset=true, T reset=0)` | Parent block, name (the VCD path is the component path plus `name`), width in bits, whether it is reset, reset value. `T` must be at least `width` bits wide | T4 |
| `Signal(Block &parent, std::string name, int width, ResetKind reset_kind, T reset_value=0)` | Same, with `ResetKind::HighZ` to start as `z` | read |
| `set(T value, int64_t cycle_delay=0, int64_t time_delay=0)` | Stores the value and dumps a change, now or after a delay | T4 without the delays |
| `get()` | The current value, so a signal can also be model state | read |
| `release(...)` | Dumps `z` (high impedance), for example for an idle period | T4 |
| `set_and_release(T value, ...)` | The value for one cycle, then `z`: a pulse | read |
| `inc(T value)`, `dec(T value)` | Change by `value` | read |

A signal also has a text trace at `TRACE` level, `<path>/trace`. Nothing is
dumped without `--vcd` and an `--event` expression that matches the path.

## Registers: vp::Register

`vp/register.hpp`, `engine/engine/src/register.cpp`. A value with a name,
partial access, a trace and a VCD signal.

```cpp
vp::Register<uint32_t> my_reg;

// in the initializer list
my_reg(*this, "my_reg", 32)

// in the request handler, for a register at offset 8
_this->my_reg.update(req->get_addr() - 8, req->get_size(), req->get_data(), req->get_is_write());
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Register(Block &parent, std::string name, int width, bool do_reset=false, T reset_val=0)` | Parent block, name (path: component path plus `name`), width in bits, whether the block's reset writes `reset_val` into it. `T` holds the value: `uint8_t` to `uint64_t` | T5; `do_reset` through the generated classes |
| `update(uint64_t reg_offset, int size, uint8_t *value, bool is_write)` | The read or write of an access. `reg_offset`: byte offset inside the register, not a bus address. `size`: number of bytes. `value`: the request's data pointer, source on a write and destination on a read. `is_write`: the direction; with `false` it copies the register out. A `memcpy`, with no check that `reg_offset + size` fits the width | T5 |
| `get()` | The full value | T5 |
| `set(T value)` | Sets the full value, with trace and VCD change. Does not go through the callback | T5 |
| `set_field(T value, int offset, int width)`, `get_field(int offset, int width)` | One bit field; what the generated `<field>_set` / `<field>_get` call | T5 through the generated accessors |
| `inc(T)`, `dec(T)`, `=`, `\|=`, `&=`, conversion to `T` | Shorthands for `set` and `get` | read |
| `register_callback(std::function<void(uint64_t, int, uint8_t *, bool)> callback, bool exec_on_reset=false)` | `callback(reg_offset, size, value, is_write)` replaces the default handling in `access`, for loads and stores. It must call `update` itself to do the read or write. `exec_on_reset`: also call it when the register is reset, as a write of the reset value | T5 |
| `access(uint64_t reg_offset, int size, uint8_t *value, bool is_write)` | The callback when there is one, `update` otherwise. This is what `vp::regmap::access` calls; use it in place of `update` when a hand-placed register has a callback | T5 through the regmap |
| `release()` | Shows the register as `z` in the VCD | read |

Traces: `<path>/trace`, with `Modified register (value: ...)` at `TRACE`
level. Measured in T5: a 1-byte store at `reg_offset` 1 replaces one byte;
an 8-byte store into a 32-bit register is accepted and writes past the
value; a `write_mask` exists but `write` does not apply it, so read-only
needs a callback.

## Register maps: vp::regmap

`vp/register.hpp`, generated classes from `regmap-gen`. The tool, its input
format and a full example are in `docs/reference/regmap.md`.

```cpp
#include "headers/mycomp_regfields.h"      // first: the macros
#include "headers/mycomp_gvsoc.h"          // then the classes that use them

vp_regmap_regmap regmap;

// in the initializer list
regmap(*this, "regmap")

// in the constructor
this->regmap.build(this, &this->trace);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp_regmap_<name>` | The generated map class, a `vp::regmap`, which is a `vp::Block`. `<name>` is `regmap-gen --name`, default `regmap` | T5 |
| `vp_regmap_<name>(vp::Block &top, std::string name)` | Parent and name. Registers get the paths `<component>/<name>/<register>` | T5 |
| `regmap.<register>` | One member per register, lower case: a `vp::Register<T>` with name, offset, width, reset value and fields filled in, built with `do_reset` on | T5 |
| `regmap.<register>.<field>_get()`, `<field>_set(v)` | Field accessors | T5 |
| `build(vp::Block *comp, vp::Trace *trace, std::string name="")` | Stores the trace on which an unknown offset is reported | T5; no visible effect when left out, the abort without it is read |
| `access(uint64_t offset, int size, uint8_t *value, bool is_write)` | `offset` is relative to the start of the map. Finds the register with `reg.offset <= offset` and `offset + size <= reg.offset + width/8`, and calls its `access` with the offset inside the register. Returns `false` when a register was found, `true` when not, after `Accessing invalid register (...)`, which with the default `werror` ends the run | T5 |

Traces: `<register path>/trace`, with `Register access (name: ..., value: {
FIELD=... })` at `DEBUG` level.

## Statistics and sub-blocks

| Call | Meaning | Checked |
|---|---|---|
| `this->stats.register_stat(StatCommon *stat, name, desc)` | Registers a counter; `--stats` writes all of them to `build/work/stats.txt` at the end of the run. Example in `gvsoc/core/models/memory/memory.cpp` | read; `--stats` output seen in T3 |
| A class derived from `vp::Block`, built with a parent and a name | A sub-unit inside one model: own path, traces, registers and clock events, no bindable ports. `vp::regmap` is one; the Snitch fast core's `Ssr` is another | T5 for `vp::regmap`; otherwise read |

## Python generator of a component

`engine/python/gvsoc/systree_gvrun2.py`, imported as `gvsoc.systree`.

```python
import gvsoc.systree

class MyComp(gvsoc.systree.Component):
    def __init__(self, parent: gvsoc.systree.Component, name: str, value: int):
        super().__init__(parent, name)
        self.add_sources(['my_comp.cpp'])
        self.add_properties({"value": value})

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_NOTIF(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('notif', itf, signature='wire<bool>')
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Component.__init__(parent, name)` | Places the instance in the tree; its path is the parent's path plus `name` | T0, T1 |
| `add_sources([...])` | The C++ files of the model, relative to a module root. One library per set of sources and flags, named by a hash of the names, not the content. A component without sources is a pure container | T1 |
| `add_properties({...})` | Values for this instance, written to `gvsoc_config.json` and read in C++ with `get_js_config()`. Changing a value needs no rebuild | T1 |
| `gvsoc.systree.SlaveItf(self, 'name', signature='io')` | Describes an input port; `name` must be the name in `new_slave_port`. By convention returned by a method `i_NAME()` | T1 |
| `self.itf_bind('name', slave_itf, signature='...')` | Binds this component's output `name` (as in `new_master_port`) to another component's input. By convention inside a method `o_NAME(itf)` | T2 |
| Signatures | `'io'`, `'wire<bool>'`, `'wire<MyClass *>'`. A label: a mismatch between the two ends is `Invalid signature`, but the C++ types are not checked | T1, T2 |
| `self.bind(self, 'in_0', child, 'in_0')` | In a container, forwards its own port to a child, as `snitch_cluster.py` does | read |
| `def gen(self, builddir, installdir)` | Called for every component during `make gvsoc`, before the models compile. Used to generate headers, for example a register map | T5 |
| `def gen_gtkw(self, tree, comp_traces)` | Called when `gvrun` writes the GTKWave script; `tree.add_trace(self, self.name, vcd_signal='status[31:0]', tag='overview')` puts a signal in the prepared view. It does not decide what is dumped | T4 |

What GVSoC checks on a binding (T0): a misspelled method is a Python
`AttributeError`; a signature mismatch is `Invalid signature`; a port name
the C++ model does not have is `Binding from invalid slave port`. A missing
binding is not reported.

## Python generator of a system

The stock components used by the tutorial system `my_system.py`. Paths are
under `core/models/`.

| Component | Arguments and ports used | Checked |
|---|---|---|
| `vp.clock_domain.Clock_domain(parent, name, frequency)` | A clock generator, `frequency` in Hz. `clock.o_CLOCK(soc.i_CLOCK())` gives the clock to a component and everything under it | T0 |
| `interco.router.Router(parent, name, latency=0, bandwidth=0, synchronous=True, ...)` | A memory-mapped router. `ico.i_INPUT()` is its input; several masters can bind to it | T0; `latency` and `bandwidth` read (step 12) |
| `ico.o_MAP(itf, name=None, base=0, size=0, rm_base=True, remove_offset=0, latency=0)` | Maps `base .. base+size-1` to a slave. `rm_base`: subtract `base`, so the slave sees an offset | T0, T1 |
| `memory.memory.Memory(parent, name, size)` | A memory of `size` bytes; `mem.i_INPUT()` | T0 |
| `cpu.iss.riscv.Riscv(parent, name, isa='rv64imafdc', binaries=[binary])` | The RV64 core, modelled by the instruction set simulator. `o_FETCH(itf)`, `o_DATA(itf)` (mandatory), `o_DATA_DEBUG(itf)` (GDB only), `i_FETCHEN()`, `i_ENTRY()` | T0 |
| `utils.loader.loader.ElfLoader(parent, name, binary=binary)` | Writes the ELF through `o_OUT(itf)`, then starts the core through `o_START(itf)` and `o_ENTRY(itf)`. Without these two the simulation never ends | T0 |
| `gvrun.parameter.TargetParameter(self, name='binary', value=None, description='...').get_value()` | A parameter of the target, set on the command line with `--parameter binary=<elf>` | T0 |
| `class Target(gvsoc.runner.Target)` with `model`, `name`, `description` | The top that `gvrun --target-dir=<dir> --target=<file name>` instantiates | T0 |

The generator runs twice: at build time, to list the models to compile, and
at run time, to write `build/work/gvsoc_config.json`. A change of values or
of the tree needs no rebuild as long as every model variant is already
compiled.

## gvrun options

Passed in the tutorials as `make run runner_args="..."`.

| Option | Effect | Checked |
|---|---|---|
| `--parameter binary=<elf>` | Sets a `TargetParameter` | T0 |
| `--trace=REGEX` | Enables the traces whose path matches; can be given several times. `REGEX:file` writes them to a file in the work directory | T3 |
| `--trace-level=error\|warning\|info\|debug\|trace` | The most detailed level that is printed | T3 |
| `--vcd` | Writes `build/work/all.vcd` and `view.gtkw` | T4 |
| `--event=REGEX` | Which signals are dumped. `--vcd` alone dumps almost nothing | T4 |
| `--stats` | Writes `build/work/stats.txt`; uses the profile build, about 2.7 times slower | T3 |
| `--no-werror` | A model warning no longer ends the run | T5 |

## Rules of thumb

- A request, a wire `sync` and a register access are plain function calls.
  They happen inside the caller and take no simulated time. Time comes from
  latency on a request (tutorial 7) or from a clock event (tutorial 6).
- Have the model's state consistent before driving a wire: the callee may
  call back into it.
- Check mandatory ports and properties in the model. GVSoC reports neither
  an unbound port nor a missing property.
- Return `IO_REQ_INVALID` for offsets and sizes the model does not serve, so
  a wrong access traps instead of reading stale data.
- Guard optional output wires with `is_bound()`.
- Give traces, signals and registers their own names; `trace` and `comp`
  are taken by the base classes.
- Profiling runs use no `--trace`, `--vcd` or `--event`. Numbers that are
  needed in every run are statistics.
