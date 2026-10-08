# GVS1 plan: learn GVSoC

GVS1 is the first task of X1, the SNAX-GVSoC exploration (D115 in
snax-forge). Goal: a working GVSoC set-up with Snitch programs running, and
enough of the developer tutorials to write an accelerator model.

This file is the checklist. `NOTES.md` is the log: what was run, what came
out, what was learned. Tick a step here when its entry is in `NOTES.md`.

## How the steps are run

- One step at a time. Each step gives: what it is for, the exact commands or
  code, the output to expect, and a short explanation of how it works.
- The output is pasted back before the next step starts. Errors are worked
  from the pasted text.
- No comprehension checks. At most one optional "worth a thought" line.
- Each concept is tied to its SNAX-MODEL counterpart in a sentence.
- Every command is read from the GVSoC source at the pinned commit and run in
  the container before it is handed over. Anything not verified is said so.
- After each step: the `NOTES.md` text for it, a write-up of the tutorial in
  `docs/tutorials/`, and the steps that remain.

## Steps

| # | Step | Teaches | Time | Status |
|---|---|---|---|---|
| 1 | Repo, submodules, container, `NOTES.md` | Layout and pins | 20 min | done 2026-10-07 |
| 2 | Build GVSoC for `snitch`, run the bundled ELF | Build flow, `gvrun`, `--trace` | 30 min | done 2026-10-07 |
| 3 | Build snitch_cluster tests at the pin, run them | Software flow, the version match | 45 min | done 2026-10-07 |
| 4 | Tutorial 0: system from scratch | Python generators, router, loader | 30 min | done 2026-10-07 |
| 5 | Tutorial 1: component from scratch | C++ model plus generator, serving an IO request | 30 min | done 2026-10-08 |
| 6 | Tutorial 2: components communicating | Wire interfaces | 30 min | done 2026-10-08 |
| 7 | Tutorial 3: system traces | `vp::Trace`, `--trace` paths | 15 min | done 2026-10-08 |
| 8 | Tutorial 4: VCD traces | `vp::Signal`, GTKWave | 20 min | |
| 9 | Tutorial 5: register map | By hand, `vp::Register`, `regmap-gen` | 45 min | |
| 10 | Tutorial 6: timing | `ClockEvent` | 30 min | |
| 11 | Tutorial 7: IO request interface | Synchronous latency, pending and `resp()` | 45 min | |
| 12 | Tutorial 10: interconnect timing | Router latency and bandwidth | 20 min | |
| 13 | Tutorial 16: control from Python | The proxy: step, read and write memory | 30 min | |
| 14 | Tutorial 19: standalone testbench (optional) | Testing a model with no core | 30 min | |
| 15 | Read the HWPE tutorial, no build | A full accelerator: config port, FSM, streamer into L1 | 60 min | |
| 16 | Close `NOTES.md` | | 15 min | |

Tutorials 0 to 3 have been built and run. Tutorials 4 onward have not been
run yet.

Tutorial 7 only covers the slave side of an IO request. Step 15 is where a
component issuing its own requests to L1 is shown, which a streamer needs.
Step 15 is therefore no longer optional (decided in step 7); step 14 still
is.

## SNAX-MODEL counterparts

| GVSoC | SNAX-MODEL |
|---|---|
| Python generator of a target | Cluster / platform file |
| `gvsoc_config.json` in the work directory | The resolved design point |
| Router | xbar |
| Memory-mapped component with a register map | Register window |
| Wire interface | `start` / `busy` / irq between controller and accelerator |
| `ClockEvent` | Event scheduler |
| Trace path and `--trace` filter | Event source names in the run viewer |
| Standalone testbench (tutorial 19) | A run with no CPU |

## Skipped tutorials

| Tutorial | Why |
|---|---|
| 8 Multiple cores | The Snitch target already has nine |
| 9 Clock domains | The cluster has one clock |
| 11, 12, 13 ISS instructions | The Snitch ISA is not being changed; 13 has no directory |
| 14 Power | Out of scope |
| 15 Multi-chip | The HEMAIA path; a ten-line generator change, read when GVS4 needs it |
| 17 External simulator API | Only for cosim |
| 18 Linux, 20 UART | Not needed |

## Where things are

- Tutorials in the source: `gvsoc/engine/docs/developer_manual/tutorials`.
  Working copies go in `tutorials/` at the repo root, with `utils/` beside
  them.
- Write-ups: `docs/tutorials/<number>_<topic>.md`, one per tutorial, written
  against the pinned source.
- The website (gvsoc-developer.readthedocs.io) is behind the source: it
  gives the old path and the old `gvsoc --binary` launcher.
- Per new container: `source gvsoc/sourceme.sh`. For the tutorials also
  `export GVSOC_ROOT=/work/gvsoc`.

## After GVS1

Kept in view, not started. Findings so far are in `NOTES.md`.

- **GVS2:** does GVSoC's L1 model arbitrate per bank for a port that is not
  a core, and how far is its Snitch target from the SNAX fork (registers,
  memory map, DMA)?
- **GVS3:** a toy component on the cluster with `start` and `busy` registers
  that reads and writes L1, driven by a small C program; how many days a
  streamer and a generic accelerator would take; whether its events can feed
  the SNAX-FORGE run viewer.
- **GVS4:** decide whether SNAX-GVSoC replaces or joins SNAX-MODEL.

## Starting a new thread

Attach this file and `NOTES.md`, and name the step you are at.


