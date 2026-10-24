# LNK2a plan: SNAX-GVSoC's target read from the cluster hjson

LNK2a is a task of M14 in snax-forge (D119, D111, D134 there): the cluster
hjson from the design point, and SNAX-GVSoC's target read from it, so GEN3's
runs run on the read target. The hjson is the contract: snax_cluster's
clustergen and snaxgen read the same files (LNK2b). Done: rounds 1 and 2,
tags `lnk2a-r1` and `lnk2a-r2`.

## The rounds

1: SNAX-GVSoC reads the hjson (forge/'s fixtures written by hand). 2:
snax-forge's writer makes the hjson files and the manifest; the schemas.

## Decisions

- Three files per design (round 2): the cluster (`snax_alu.hjson`), the
  streamer (`snax_alu_streamer.hjson`), the accelerator
  (`snax_alu_acc.hjson`); all three since renamed `snax_forge*.hjson`. The
  slot's `snax_streamer_cfg` and `snax_datapath_cfg` are `$ref`s to the
  whole files; SNAX-GVSoC's reader resolves them itself.
- One generic target, `snax_hjson`, the hjson path an option; a slot with
  `snax_datapath_cfg` gets the standard composite.
- The measured timing is not in the hjson: constants in `snax/snax_hjson.py`,
  calibrated to the RTL (the DMA, the DRAM's and the cores' latency, the HTIF
  backdoor, the clock); queue depths, `isa`, addresses and sizes, `tcdm.*`,
  `dram.*`, the core count and the interconnect come from the hjson.
- The streamer is lowered per design (lanes and `num_channel` from the BRM
  ports, `temporal_dim` and `fifo_depth` from the platform; open item 78);
  the slot's name is the platform's `accelerator_slot`; snax-forge generates
  no Python.

## What round 1 gives

`snax/snax_cfg.py` (the reader, named errors), the `snax_hjson` target
(`--param hjson=<path>`), `snax/snax_unit_acc.py` (GEN3's composite written
once), `forge/<design>/` as hjson, run by `make regress` on `snax_hjson`.

## What round 2 gives

snax-forge's `gen/gvsoc.py` writes the hjson files, `include/` and the
manifest, with schemas; here, whole-file refs and snax_cluster's schema
copied by `sw/sync.py`; forge/'s fixtures are the writer's output.

## Findings

- **The TCDM was hard-coded.** Since step 1 `ClusterArch` takes size, banks
  and bank width and places the peripherals and zero memory after the TCDM;
  16 banks run with nothing compiled.
- **L1 size and base need the ELF.** They come from the runtime's
  `sw/generated/`; changing them needs that and the program rebuilt.
  Changing banks alone keeps the ELF.
- **Cross-file `$ref` in snax_cluster.** clustergen and snaxgen called
  `JsonRef.replace_refs` without a `base_uri`; fixed in LNK2b (open item 51).
- **The schema's `"items:"` typo.** At `05615e4` no `snax_acc_cfg` entry was
  validated; fixed in snax_cluster `cf4b0002` (LNK2b), with no item defaults,
  which clustergen would write into an accelerator-less core's `{}`.
- **Plain and sparse give the same cycles on forge/'s fixtures.** Their one
  bank conflict goes to reader 0 under both arbiters (the plain interconnect
  is since removed).
- **The platform tree's signature is the component tree.** A file with
  another component tree runs on the JSON config, with gvrun's warning.

## Steps

All done: round 1 steps 1 to 6; round 2 R2.0 to R2.5 (docs: D134, with D84,
D87, D111, D128, D131 amended and D132 retired).

## Round 2 findings

- **The fixtures are round 1's, parsed.** `include/` byte-identical, the
  forge runs give main's logs, so the cycles are round 1's.
- **The written cluster file is JSON.** The source parsed: comments go, key
  order stays.
- **What the hjson cannot hold is refused.** An L1 or L2 field that does not
  read back through `hjson_platform.py` is `gen.platform`.

## Open

- `make build` rebuilds `cluster_registers` on every run; not investigated.
- More than one hive, another `boot_addr` or base, another L1 size: taken by
  the reader and the target, never run (the last two need a rebuilt
  `sw/generated/` and ELF).
- More than one accelerator slot per core, wide TCDM ports: refused
  (`CfgTargetError`).
