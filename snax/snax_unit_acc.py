#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The standard composite of an accelerator slot with a datapath block: the CSR
mux, the streamer, SnaxShell and SnaxUnit.

    SnaxUnitAcc.for_slot(slot, tcdm_size, file) -> class

The slot (snax_cfg.AccSlot) gives the streamer template and the datapath
block (snax_cfg.Datapath), the cluster its TCDM size. The unit's inputs take
the streamer's readers in order, its outputs the writers.

CSRs: the streamer's from SNAX_CSR_FIRST (nb_csrs of its template); then the
shell's: the datapath's fields, start, busy and the counter, read-only. The
counter must be at most SNAX_ACC_CSR_LAST (snax_acc.py).
"""

import gvsoc.systree
import interco.router as router
from snax_acc import SNAX_ACC_CSR_LAST, SNAX_CSR_FIRST, SNAX_CSR_LAST, SnaxAcc
from snax_cfg import CfgTargetError
from snax_streamer import SnaxStreamer, nb_csrs, nb_tcdm_ports, tcdm_port_names
from snax_shell import SnaxShell
from snax_unit import SnaxUnit

# The unit kinds a datapath block may name
UNITS = ['SnaxUnit']


def compile_components():
    """Has the build compile SnaxShell and SnaxUnit, as it would for a target whose tree holds
    them: a cluster file with a datapath block runs on the installed components, whatever a
    built target's default file holds. The build path only (gvsoc.systree's registry)."""
    for sources in (SnaxShell.SOURCES, SnaxUnit.SOURCES):
        gvsoc.systree.get_generated_component(list(sources), [], [])


class SnaxUnitAcc(SnaxAcc):
    """The CSR mux, the streamer, SnaxShell and SnaxUnit of one slot, ports as SnaxAcc's;
    for_slot gives the slot's class."""

    # Set by for_slot: the streamer template, the datapath block, the TCDM size, and
    # SnaxAcc's nb_tcdm_ports and tcdm_port_names
    template = None
    datapath = None
    tcdm_size = None

    @classmethod
    def for_slot(cls, slot, tcdm_size: int, file='?'):
        """The class of the slot's composite, with the class attributes the cluster reads
        (nb_tcdm_ports, tcdm_port_names)."""
        datapath = slot.datapath
        if datapath.unit not in UNITS:
            raise CfgTargetError(file, f'{slot.at}.snax_datapath_cfg.unit',
                f'{datapath.unit!r}, not a unit kind ({UNITS})')
        shell_last = SNAX_CSR_FIRST + nb_csrs(slot.streamer) + len(datapath.fields) + 2
        if shell_last > SNAX_ACC_CSR_LAST:
            raise CfgTargetError(file, slot.at,
                f"the shell's last CSR {shell_last} is past {SNAX_ACC_CSR_LAST}, the last an "
                "accelerator may use")
        return type(f'SnaxUnitAcc_{slot.name}', (cls,), {
            'template': slot.streamer,
            'datapath': datapath,
            'tcdm_size': tcdm_size,
            'nb_tcdm_ports': nb_tcdm_ports(slot.streamer),
            'tcdm_port_names': ['streamer.' + name for name in tcdm_port_names(slot.streamer)],
        })

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        datapath = self.datapath
        # Where csr_mux switches from the streamer to the shell
        shell_csr_first = SNAX_CSR_FIRST + nb_csrs(self.template)

        csr_mux = router.Router(self, 'csr_mux')

        streamer = SnaxStreamer(self, 'streamer', template=self.template,
            csr_base=SNAX_CSR_FIRST, tcdm_size=self.tcdm_size)
        shell = SnaxShell(self, 'shell', csr_base=shell_csr_first, fields=datapath.fields)
        unit = SnaxUnit(self, 'unit', inputs=datapath.inputs, outputs=datapath.outputs,
            lanes=datapath.lanes, op=datapath.op, in_widths=datapath.in_widths,
            in_signed=datapath.in_signed, out_widths=datapath.out_widths,
            out_signed=datapath.out_signed, control=datapath.control, config=datapath.config,
            wait=datapath.wait, latency=datapath.latency, ii=datapath.ii,
            csr_base=shell_csr_first)

        # The streamer's range, then everything to the last SNAX CSR to the
        # shell
        streamer_base = 4 * SNAX_CSR_FIRST
        shell_base = 4 * shell_csr_first
        csr_mux.o_MAP(streamer.i_INPUT(), base=streamer_base,
            size=shell_base - streamer_base)
        csr_mux.o_MAP(shell.i_INPUT(), base=shell_base,
            size=4 * (SNAX_CSR_LAST + 1) - shell_base)

        shell.o_CTRL(unit.i_CTRL())
        unit.o_BUSY(shell.i_BUSY())

        # The beats: the readers into the inputs, the outputs into the writers
        for i, port in enumerate(datapath.inputs):
            unit.o_PORT(port, streamer.i_READER(i))
        for j, port in enumerate(datapath.outputs):
            unit.o_PORT(port, streamer.i_WRITER(j))

        self.bind_ports(csr_mux, streamer)
