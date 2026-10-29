#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxGroup (snax_group.cpp): one group of accelerator.json, its units' datapaths
under one control model, every number a property.

The control model (SnaxGroupRule, snax-forge C§17's Control) is in snax_group.hpp,
the datapaths (snax-forge's catalogue) in snax_datapath.hpp. The C++ checks every
property and stops on a bad one, naming it; this class only passes them on, so a
design point compiles nothing (D134 in snax-forge). A group of one unit is B1's
SnaxUnit.
"""

import gvsoc.systree


class SnaxGroup(gvsoc.systree.Component):
    """A chain of units, head first, each link a wire (depth 0) or a buffer.

    Parameters
    ----------
    units : list[dict]
        Each unit (snax_group.cpp's header): name, datapath, inputs (per BRM
        input its outer port's name, or "" for the link from the unit before),
        output (the outer port's name, the last unit's; else ""), lanes,
        in_widths, in_signed, out_width, out_signed, op_width, op_signed, op,
        accumulate, reg_out, latency, ii, span, and t (a result every t-th
        firing, fixed; 0 for a fold's JOB_BEATS, from the start).
    links : list[int]
        Each link's depth, one fewer than the units: 0 a wire, >= 1 a buffer.
    csr_base : int
        Number of its group's first CSR, for the trace.

    Ports
    -----
    <unit>_<port> : io master
        The streamer's reader_<i> and writer_<j> ports, one per outer port.
    ctrl : io slave
        A start: JOBS, then each fold's JOB_BEATS without a fixed t.
    busy : wire<bool> master
        Busy from the next cycle on, driven on every change.
    """

    SOURCES = ['snax_group.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, units: list, links: list,
            csr_base: int = 0):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'units': [dict(u) for u in units],
            'links': list(links),
            'csr_base': csr_base,
        })

    def i_CTRL(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'ctrl', signature='io')

    def o_PORT(self, port: str, itf: gvsoc.systree.SlaveItf):
        """Binds the outer input or output port named port."""
        self.itf_bind(port, itf, signature='io')

    def o_BUSY(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('busy', itf, signature='wire<bool>')

    def gen_gtkw(self, tree, comp_traces):
        """Its VCD signals (snax_group.cpp), tagged snax, for gvrun's --vcd and view.gtkw."""
        tree.begin_group('snax_group')
        for name, ext in (('busy', ''), ('fire', ''), ('push', ''), ('cycle_class', '[2:0]')):
            tree.add_trace(self, name, name, ext, tag='snax')
        tree.end_group('snax_group')
