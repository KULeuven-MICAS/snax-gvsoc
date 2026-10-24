# SG1 plan: the snax_alu target and the CSR port

SG1 is the first task of M16 in snax-forge after SG0 (SNAX-GVSoC aligned
with snax_cluster, D116). It built the `snax_alu` target (since removed,
CLN1 R2, snax-gvsoc #28), the Snitch core's port for SNAX CSRs and a stub
register block. Acceptance: a CSR test program reads back what it wrote;
snax_cluster's `snax-alu` app runs to exit on a stub register block; the 17
plain tests still pass on the `snitch` target. Closed 2026-10-13; the log is
`docs/notes/NOTES.md` (SG1 steps 1 to 8).

## The cluster

snax_cluster's `cfg/snax_alu_cluster_old.hjson` at `b2672f8`: one `rv32ima`
compute core with the ALU, one `rv32ima` DMA core, 128 KiB TCDM in 32 banks,
and the plain interconnect (`sparse_interconnect: false`). The target was
written by hand with these values.

## Steps

All done 2026-10-13: P1, this plan and the pin at `b2672f8`; P2, the
`snax-alu` app copied into `tests/snax/snax-alu/` (the copy since removed,
#28; `tests/snax/<program>/` since moved to `sw/apps/<program>/`, CI1); P3,
the `snax_alu` target, 2 cores, `simple` and `printf_simple` exit 0; step 4,
how a CSR instruction can send an IO request and stall until the response; P4,
the CSR port, the 17 plain tests still pass; P5, the stub register block
(`SnaxCsrStub`, since removed) and `snax-csr`, every written value reads back;
step 7, `snax-alu` on the stub ran to the end with no CSR warnings,
`Accelerator Cycles: 0`, `Number of errors: 100`, exit code 100 (nothing
computed the output yet); P6, closed in snax-forge.

## Decided

- The target is written by hand from `snax_alu_cluster_old.hjson` (D119 in
  snax-forge); reading the hjson comes with LNK2a in snax-forge.
- The CSR path (D120): the accurate Snitch core sends CSRs 0x3C0 to 0x5FF as
  32-bit IO requests at byte address 4 * CSR on its `snax_csr` port; `csrw`
  sends one write, `csrrw` with `rd` not `x0` a read then a write, `csrrs`
  and `csrrc` a read then a write. The answer must be `IO_REQ_OK`.
- An accelerator is a cluster component per core: `ClusterArch(snax_acc=
  {core: function(parent, name)})`, bound to that core's `snax_csr` port.
- The stub followed `ReqRspManager.scala`: read-write CSRs read back and
  reset to 0, read-only CSRs read 0, anything else refused with a warning
  naming the CSR.
- GVSoC runs with `werror: true`: any warning ends the run with exit 1.

## SG2 starts from

- The stub's trace (`--trace=snax_acc0`) was the reference for SG3 and SG4:
  19 writes, then the busy reads of 981 and 976 and the counter 982.
