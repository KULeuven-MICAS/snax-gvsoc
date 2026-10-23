# LNK2a plan: SNAX-GVSoC's target read from the cluster hjson

LNK2a is a task of M14 in snax-forge (D119, D111, D134 there): the cluster
hjson from the design point, and SNAX-GVSoC's target read from it, so GEN3's
runs run on the read target. The hjson is the contract: snax_cluster's
clustergen and snaxgen read the same files (LNK2b). Done: rounds 1 and 2,
tags `lnk2a-r1` and `lnk2a-r2`.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- On the MICAS server, by Claude Code, in snax-forge's image
  (`ghcr.io/kuleuven-micas/snax-forge:main`), as GEN3.
- One commit per step on `ry/lnk2a`, here and in snax-forge; each round
  tagged (`lnk2a-r1`, `lnk2a-r2`).
- Anything not verified is said so.

## The rounds

| Round | Content |
|---|---|
| 1 | SNAX-GVSoC reads the hjson: the TCDM from arguments, the reader, the generic target, the standard composite, forge/'s fixtures as hjson written by hand, the hand-written targets on the generic one (steps 1 to 5 here); snax-forge's docs (step 6) |
| 2 | snax-forge's writer: three hjson files (cluster, streamer, accelerator) and the manifest from a design point, in place of round 1's hand-written fixtures, compared byte for byte again; the schemas (steps 0 to 5 of round 2) |

## Decisions

Taken before round 1, not reopened (round 2's below):

- The hjson is the contract. Two files per design: the cluster file, named
  after the base platform (`snax_alu.hjson`), and the accelerator file,
  named after its slot (`snax_alu_acc.hjson`). The cluster's `snax_acc_cfg`
  entry (the slot) keeps the slot keys (`snax_acc_name`, `bender_target`,
  `snax_tcdm_ports`, the interconnect config, `snax_num_rw_csr`,
  `snax_num_ro_csr`); its `snax_streamer_cfg` and `snax_datapath_cfg` are
  `$ref`s into the accelerator file (`snax_alu_acc.hjson#/snax_streamer_cfg`,
  `#/datapath`).
- SNAX-GVSoC's reader resolves `#/key` and `file.hjson#/key` refs itself;
  snax_cluster's clustergen and snaxgen cannot yet (LNK2b's fix).
- forge/'s designs use the sparse interconnect (`snax_alu_cluster.hjson`);
  the plain `snax_alu` stays SG5's baseline, read from
  `snax_alu_cluster_old.hjson`.
- The slot keeps `snax_acc_name: snax_alu` for now; `cluster.name` stays the
  source file's (it names snax_cluster's RTL).
- One generic, installed target, `snax_hjson`; the hjson path is a target
  option.
- A slot with `snax_datapath_cfg` gets the standard composite
  (`snax/snax_unit_acc.py`); one without is looked up by name in a registry
  (`snax_alu` -> `SnaxAluAcc`, `register_accelerator`); neither is an error.
- The measured timing is not in the hjson: constants in `snax/snax_hjson.py`,
  calibrated to snax_cluster's RTL (SG2's DMA, the DRAM's latency, the
  cores' latency, the HTIF poll backdoor, the clock). From the hjson where it
  maps: `dma_req_fifo_depth` -> `transfer_queue_size`,
  `dma_axi_req_fifo_depth` -> `burst_queue_size`,
  `num_int_outstanding_loads` -> `int_loads_in_flight`, `isa` -> misa,
  `dma_data_width`, `boot_addr`, `cluster_base_addr`, `tcdm.*`,
  `cluster_periph_size`, `zero_mem_size`, `dram.*`, the hive's core count,
  `sparse_interconnect` and `sparse_interconnect_config` or the narrow and
  wide ports.

Taken before round 2, not reopened:

- Three hjson files per design, each changing for its own reason: the
  cluster (`snax_alu.hjson`, the platform's source with its values written
  back and the slot set), the streamer (`snax_alu_streamer.hjson`, the
  template as the hjson has it) and the accelerator (`snax_alu_acc.hjson`,
  the datapath block). The slot's `snax_streamer_cfg` and
  `snax_datapath_cfg` are `$ref`s to the whole files; the reader resolves a
  ref without `#`.
- The streamer is lowered per design, as GEN3's generator lowered it: lanes
  and `num_channel` from the BRM ports, `temporal_dim` and `fifo_depth` from
  the platform's streamer knobs. A standalone streamer input, a frozen
  streamer file and `temporal_dim` from the DFG are snax-forge open item 78.
- The slot's name comes from the platform's `accelerator_slot` (from the
  source's `snax_acc_name`).
- snax-forge generates no Python: no composite, no target, no install check.

## What round 1 gives

- `snax/snax_cfg.py`: the reader (`load(path) -> ClusterCfg`); its module
  doc lists every key read and the datapath block's fields; named errors
  (`CfgParseError`, `CfgRefError`, `CfgKeyError`, `CfgTypeError`,
  `CfgSlotError`, `CfgTargetError`). Tests in `tests/snax/test_snax_cfg.py`.
- `snax/snax_hjson.py`: the `snax_hjson` target, `--param hjson=<path>`
  (`declare_user_property`; the target qualifier
  `--target snax_hjson:hjson=<path>` works too), a relative path from gvrun's
  working directory, by default the installed copy of
  `sw/cfg/snax_alu_cluster.hjson` (`install/generators/cfg/`).
- `snax/snax_unit_acc.py`: `SnaxUnitAcc`, GEN3's generated composite written
  once, built from the slot.
- `snax_alu.py` and `snax_alu_sparse.py`: `SnaxHjsonBoard` on their fixed
  `sw/cfg/` file, no hjson option; `snax_tiled_add.py` unchanged (the
  board's `accelerator` still replaces the slot's).
- `forge/<design>/`: `snax_alu.hjson`, `snax_alu_acc.hjson`, GEN3's
  `include/` and the manifest (`cluster` in place of `target` and
  `target_dirs`), run by `make regress` on `snax_hjson`.

## What round 2 gives

- snax-forge: `platforms/snax_alu.hjson` (a verbatim copy of
  `sw/cfg/snax_alu_cluster.hjson`); a platform's `hjson` and
  `accelerator_slot`; `snax_forge/gen/gvsoc.py` writes the three hjson files,
  `include/` and the manifest (no `note`), refusing `gen.source`,
  `gen.slot` and `gen.platform`; schemas for the streamer and accelerator
  files (`snax_forge/gen/schema/`, `jsonschema`).
- Here: `snax_cfg.py` resolves whole-file refs; `sw/sync.py` copies
  snax_cluster's `docs/schema/snitch_cluster.schema.json` (its `"items:"`
  typo as it was; fixed by snax-forge's LNK2b, synced at `cf4b0002`); forge/'s fixtures are the writer's output, parsed equal to
  round 1's (the streamer and datapath split into two files, the manifest's
  `files` with the streamer file, no `note`).

## Findings

- **The TCDM was hard-coded.** `ClusterArch.Tcdm` fixed 128 KiB in 4 x 8
  banks of 8 B and put the peripherals and the zero memory at fixed offsets;
  since step 1 both arch paths take size, banks and bank width (today's
  values as defaults) and place the rest after the TCDM by size. 16 banks
  run `snax-alu` and `core-tcdm` with nothing compiled.
- **L1 size and base need the ELF.** The runtime's `sw/generated/` (copied
  from snax_cluster's clustergen and regtool output, CI1) holds the L1's
  size and base; another size or base needs that rebuilt and the program
  with it. Changing banks alone keeps the ELF. Not tried.
- **Cross-file `$ref` in snax_cluster.** clustergen (`util/clustergen.py:82`)
  and snaxgen (`util/snaxgen/snaxgen.py:31`) call `JsonRef.replace_refs`
  without a `base_uri`, so `snax_alu_acc.hjson#/...` does not resolve there;
  LNK2b's fix (snax-forge open item 51).
- **The schema's `"items:"` typo.** `docs/schema/snitch_cluster.schema.json:497`
  (at the pin, `05615e4`) names the `snax_acc_cfg` item schema `"items:"`,
  not `"items"`, so no `snax_acc_cfg` entry is ever validated: neither the
  slot keys nor a new `snax_datapath_cfg` are checked by clustergen. Fixed
  in snax_cluster `cf4b0002` (snax-forge LNK2b, synced here): `"items"`,
  with `snax_disable_csr_manager`, `snax_datapath_cfg` and `snax_forge_rtl`,
  and no item defaults, since clustergen's validator would write them into
  an accelerator-less core's `{}`.
- **The timing is not in the hjson.** The DMA's read path, write latency and
  stages, the DRAM's latency and width, the cores' added latency, the HTIF
  backdoor and the clock stay constants, calibrated to the RTL (SG2, SG5,
  SG7).
- **Platform and fixtures on plain and sparse.** `snax_alu` (plain) stays
  the baseline; forge/'s fixtures moved from `snax_alu`'s board (plain) to
  `snax_alu_cluster.hjson` (sparse). On vecadd, vecmul and vsum the cycle
  counts stay the same: the one bank conflict of each accelerator run (the
  two readers in vecadd's first cycle) goes to reader 0 under both arbiters.
- **The platform tree's signature is the component tree.** A file with the
  default file's components and bindings (`snax_alu_cluster_old.hjson`)
  uses `snax_hjson`'s platform tree, its properties through the JSON config;
  a fixture's (other ports) does not match, and gvrun warns and runs it on
  the JSON config.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | Banks probe: `ClusterArch.Tcdm` (both arch paths) takes size, banks and bank width; peripherals and zero memory after it by size. snax_alu with 16 banks from a scratch `--target-dir`: nothing compiled, 16 banks in `gvsoc_config.json`, `core-tcdm` and `snax-alu` (128) pass; the defaults give main's config and logs | done |
| 2 | The reader `snax/snax_cfg.py`: refs within and across files, named errors, the slot counts against the accelerator file; tests on the three `sw/cfg/` files and broken ones; `hjson` imports under gvrun's Python | done |
| 3 | The `snax_hjson` target, `--param hjson=` (`declare_user_property`), the accelerator registry, in TARGETS. On both `sw/cfg/` files every SNAX regress program gives `snax_alu`'s and `snax_alu_sparse`'s logs and `gvsoc_config.json` (20 of 20 each) | done |
| 4 | The datapath block, `SnaxUnitAcc`, forge/'s three fixtures as hand-written hjson, regress on `snax_hjson`; `make regress` passes on vecadd, vecmul, vsum and vsum-r16; on a plain copy each gives main's logs | done |
| 5 | `snax_alu.py` and `snax_alu_sparse.py` on the generic target; this file and the notes; full `make regress` | done |
| 6 | snax-forge's docs: STATUS (LNK2a `wip`, open items 51 and 68) | done |
| R2.0 | Round 1's leftovers: the forge app Makefiles' comments, this file's Open; snax-forge's `gvsoc/Makefile` TARGETS with `snax_hjson`; its `alu_probe` and `tiled_add_sparse_probe` still run (no fix needed) | done |
| R2.1 | snax-forge: `platforms/snax_alu.hjson`, the platform's `hjson` and `accelerator_slot`, `design from-hjson` fills them | done |
| R2.2 | snax-forge's writer (three hjson files, headers, manifest), the composite and target writers and the install check removed; here, whole-file refs in `snax_cfg.py` | done |
| R2.3 | Schemas: snax_cluster's in `sw/sync.py`'s copied files; snax-forge's for the streamer and accelerator files | done |
| R2.4 | forge/'s fixtures from the writer; snax-forge's submodule at this branch; full `make regress`, snax-forge's `pixi run test` | done |
| R2.5 | Docs: snax-forge D134 (D84, D87, D111, D128, D131 amended, D132 retired), C§13 and C§16, ARCHITECTURE, STATUS (LNK2a done, open items 51, 68, 77 closed, 78); here this file, the notes, `forge/README.md` | done |

## Round 2 findings

- **The fixtures are round 1's, parsed.** The writer's cluster file equals
  round 1's hand-written one but for the two refs; its streamer and
  accelerator files equal round 1's `snax_streamer_cfg` and `datapath`;
  `include/` is byte-identical; the forge runs give main's logs (pointers
  masked, the platform-tree warning aside), so the cycles are round 1's.
- **The written cluster file is JSON.** It is the source parsed, so its
  comments go; the key order stays. The source's own streamer template, a
  top-level key only the slot referred to, is dropped, as round 1 did by
  hand.
- **What the hjson cannot hold is refused.** The writer reads its cluster
  file back through snax-forge's `hjson_platform.py`; an L1 or L2 field that
  does not come back (an L1 not whole KiB, a latency) is `gen.platform`.

## Open

- A design whose ports meet on a bank, where plain and sparse differ: none
  of forge/'s three. Plain and sparse differ only on such a design; on
  forge/'s three they give the same cycles.
- `make build` rebuilds `cluster_registers` on every run, changed or not
  (before LNK2a too); not investigated.
- snax_cluster's clustergen and snaxgen on the three files: they resolve
  neither a cross-file nor a whole-file `$ref` yet (LNK2b, snax-forge open
  item 51); round 2 checks the cluster file against snax_cluster's schema
  with snax-forge's own resolution.
- A cluster file with more than one hive, another `boot_addr` or base, or a
  different L1 size: the reader and the target take them, no run has (the
  last two need a rebuilt `sw/generated/` and ELF).
- More than one accelerator slot per core, and wide TCDM ports: refused
  (`CfgTargetError`).
