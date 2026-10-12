# SNAX-GVSoC notes

The log of SNAX-GVSoC, from SG0 on (M16 in snax-forge, D116). One entry per
step: what was run, what came out, what was learned. GVSoC itself was learnt
in `KULeuven-MICAS/snax-gvsoc-experiment` (X1); its notes and tutorial pages
stay there.

## Pins

| What | Commit |
|---|---|
| GVSoC and its seven folded submodules | see `UPSTREAM.md` |
| snax_cluster, the probe and the RTL reference | `8ebd42299c1db2ab26006f68f76896097b64b278` (2026-09-16) |

## Log

### SG0 step 1: detached copy

- 2026-10-12. Done as written in `UPSTREAM.md` under "How the copy was made";
  rehearsed in Claude's sandbox first with the same result.
- The git on micas-lapserv1 has no `subtree` command. The clone and the
  folding ran in the `snax-gvsoc:gvs1` container (Ubuntu 24.04, git 2.43),
  the push from the host.
- Checks: each folded folder's tree equals its upstream pin; commit counts
  config_tree 4, core 2080, engine 2013, gvrun 54, gvtest 67, pulp 607,
  pulpos 63. About 210 MB pushed. Only `main`; upstream has no tags.
- GitHub Actions was turned off before the first push, since upstream's
  workflow builds every target on each push. P1 removes it.

### SG0 step 2: P1

- 2026-10-12. `UPSTREAM.md`, a short README, this file and the SG0 plan.
  Upstream's CI workflow and CODEOWNERS removed (listed in `UPSTREAM.md`).
- `container/` imported from snax-gvsoc-experiment `386e433`, unchanged
  apart from its header comments and line endings (CRLF in the experiment,
  LF here); the image is now `snax-gvsoc:sg0`.
- Checked in Claude's sandbox, not in the container (Ubuntu 24.04, a Python
  3.13 venv with `container/requirements.txt`, 2 cores): at the repo root
  `make build TARGETS=snitch` took 9 min 11 s; the bundled
  `fp32_computation_vector.elf` exits 0 in 2 s; `--trace=pe0/insn` gives 484
  lines from cycle 7909 to 23862, as in the experiment. The figures are from
  Claude's run.
