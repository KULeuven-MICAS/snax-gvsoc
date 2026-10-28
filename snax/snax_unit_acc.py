#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The standard composite of an accelerator slot with an accelerator.json: the
CSR mux, the streamer, one SnaxShell per group and one SnaxUnit per unit.

    SnaxUnitAcc.for_slot(slot, tcdm_size, file) -> class

The slot (snax_cfg.AccSlot) gives the streamer template and the accelerator
(snax_cfg.Accelerator), the cluster its TCDM size. Each entry of the
accelerator's inputs ("<unit>.<port>") takes the streamer's reader of its
index, each entry of its outputs the writer of its index.

CSRs: the streamer's from SNAX_CSR_FIRST (nb_csrs of its template); then the
accelerator's, at the offsets accelerator.json gives: each group's window
(START, JOBS, its units' R/W CSRs, STATUS, COUNTER) to its shell. The last
must be at most SNAX_ACC_CSR_LAST (snax_acc.py).

Names: with one group of one unit, the shell is `shell` and the unit `unit`
(snax_acc<i>/unit, the trace path snax-forge's manifests name); with more,
`shell_<group>` and `unit_<unit>`.
"""

import gvsoc.systree
import interco.router as router
from snax_acc import SNAX_ACC_CSR_LAST, SNAX_CSR_FIRST, SNAX_CSR_LAST, SnaxAcc
from snax_cfg import CfgTargetError
from snax_streamer import SnaxStreamer, nb_csrs, nb_tcdm_ports, tcdm_port_names
from snax_shell import SnaxShell
from snax_unit import SnaxUnit


def compile_components():
    """Has the build compile SnaxShell and SnaxUnit, as it would for a target whose tree holds
    them: a cluster file with an accelerator runs on the installed components, whatever a
    built target's default file holds. The build path only (gvsoc.systree's registry)."""
    for sources in (SnaxShell.SOURCES, SnaxUnit.SOURCES):
        gvsoc.systree.get_generated_component(list(sources), [], [])


def component_names(accelerator) -> tuple:
    """The shells' names by group and the units' by unit: shell and unit for one group of
    one unit, else shell_<group> and unit_<unit>."""
    groups = accelerator.groups
    single = len(groups) == 1 and len(groups[0].units) == 1
    shells = {g.name: 'shell' if single else f'shell_{g.name}' for g in groups}
    units = {u.name: 'unit' if single else f'unit_{u.name}' for g in groups for u in g.units}
    return shells, units


class SnaxUnitAcc(SnaxAcc):
    """The CSR mux, the streamer, the shells and units of one slot, ports as SnaxAcc's;
    for_slot gives the slot's class."""

    # Set by for_slot: the streamer template, the accelerator, the TCDM size, and
    # SnaxAcc's nb_tcdm_ports and tcdm_port_names
    template = None
    accelerator = None
    tcdm_size = None

    @classmethod
    def for_slot(cls, slot, tcdm_size: int, file='?'):
        """The class of the slot's composite, with the class attributes the cluster reads
        (nb_tcdm_ports, tcdm_port_names)."""
        accelerator = slot.accelerator
        last = SNAX_CSR_FIRST + nb_csrs(slot.streamer) + len(accelerator.csrs) - 1
        if last > SNAX_ACC_CSR_LAST:
            raise CfgTargetError(file, slot.at,
                f"the accelerator's last CSR {last} is past {SNAX_ACC_CSR_LAST}, the last an "
                "accelerator may use")
        return type(f'SnaxUnitAcc_{slot.name}', (cls,), {
            'template': slot.streamer,
            'accelerator': accelerator,
            'tcdm_size': tcdm_size,
            'nb_tcdm_ports': nb_tcdm_ports(slot.streamer),
            'tcdm_port_names': ['streamer.' + name for name in tcdm_port_names(slot.streamer)],
        })

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        acc = self.accelerator
        # The accelerator's first CSR, after the streamer's
        first = SNAX_CSR_FIRST + nb_csrs(self.template)
        shell_names, unit_names = component_names(acc)

        csr_mux = router.Router(self, 'csr_mux')
        streamer = SnaxStreamer(self, 'streamer', template=self.template,
            csr_base=SNAX_CSR_FIRST, tcdm_size=self.tcdm_size)
        streamer_base = 4 * SNAX_CSR_FIRST
        csr_mux.o_MAP(streamer.i_INPUT(), base=streamer_base, size=4 * first - streamer_base)

        for k, group in enumerate(acc.groups):
            base = first + group.window[0].offset
            shell = SnaxShell(self, shell_names[group.name], csr_base=base, csrs=group.rw)
            # The group's window; past the last group, everything to the last SNAX CSR,
            # which its shell refuses
            end = (first + acc.groups[k + 1].window[0].offset if k + 1 < len(acc.groups)
                   else SNAX_CSR_LAST + 1)
            csr_mux.o_MAP(shell.i_INPUT(), base=4 * base, size=4 * (end - base))

            (unit_cfg,) = group.units
            ins = acc.ports_of(unit_cfg.name, acc.inputs)
            outs = acc.ports_of(unit_cfg.name, acc.outputs)
            in_ports = [unit_cfg.ports[p] for _, p in ins]
            out_ports = [unit_cfg.ports[p] for _, p in outs]
            unit = SnaxUnit(self, unit_names[unit_cfg.name], datapath=unit_cfg.datapath,
                inputs=[p for _, p in ins], outputs=[p for _, p in outs],
                lanes=in_ports[0].lanes, op=unit_cfg.op,
                in_widths=[p.width for p in in_ports], in_signed=[p.signed for p in in_ports],
                out_widths=[p.width for p in out_ports],
                out_signed=[p.signed for p in out_ports],
                latency=unit_cfg.latency, ii=unit_cfg.ii, csr_base=base)

            shell.o_CTRL(unit.i_CTRL())
            unit.o_BUSY(shell.i_BUSY())

            # The beats: the readers into the inputs, the outputs into the writers
            for i, port in ins:
                unit.o_PORT(port, streamer.i_READER(i))
            for j, port in outs:
                unit.o_PORT(port, streamer.i_WRITER(j))

        self.bind_ports(csr_mux, streamer)
