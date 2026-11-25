#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxGroup (snax_group.cpp): one group of accelerator.json, its units' datapaths
under one control model, every number a property.

The control model (SnaxGroupRule) is in snax_group.hpp,
the datapaths (snax-forge's catalogue) in snax_datapath.hpp. The C++ checks every
property and stops on a bad one, naming it; this class only passes them on, so a
design point compiles nothing.
"""

import gvsoc.systree


class SnaxGroup(gvsoc.systree.Component):
    """A group's units and the links between them, each a wire (depth 0) or a buffer.

    Parameters
    ----------
    units : list[dict]
        Each unit (snax_group.cpp's header): name, datapath, inputs (per BRM
        input its outer port's name, or "" for one a link feeds; a name
        several units give is a forked input), seed (the index of a
        fold's seed in inputs, the last, or -1), output (the outer port's
        name, or "" when linked; each chain's sink has one), lanes,
        in_widths, in_signed, out_width, out_signed, op_width, op_signed, op,
        accumulate, reg_out, rows (a Mac's bank rows; 1 without), hold
        (per input, read once a bank row and kept), carry (its seed
        carried), k (SimdLanes' constant at one stream, decimal;
        "" at two), k1 and k2 (axpby's baked, decimal; "" when not baked),
        scalars (the slots read from CSRs, each [slot, words], in CSR order:
        their words follow a start's JOB_BEATS), latency, ii, span, and t (a
        result every t-th firing, fixed; 0 for a fold's JOB_BEATS, from the
        start).
    links : list[dict]
        Each link an edge: from and to (the producer's and the consumer's
        names), to_input (the consumer's input it feeds, an index in its
        inputs), depth (0 a wire, >= 1 a buffer) and hold (optional, true:
        a buffer into a bank's held broadcast input, popped once a row).
        Chains joined by forked inputs, no fork or join of links.
    fork_links : list[dict]
        Optional, a fork's buffered branches, each fork (the forked input's port name,
        its reader's), to and to_input (the consumer, after the fork's units,
        and its input, one left "") and depth (>= 1): the fork's beat
        through a ring of that many beats.
    csr_base : int
        Number of its group's first CSR, for the trace.

    Ports
    -----
    <unit>_<port> : io master
        The streamer's reader_<i> and writer_<j> ports, one per outer port (a
        forked input's once).
    ctrl : io slave
        A start: a JOBS per output, then each fold's JOB_BEATS without a fixed t, then
        per unit its ROWS (a bank's), CARRY (a carried seed's) and scalars.
    busy : wire<bool> master
        Busy from the next cycle on, driven on every change.
    mark : wire<uint32_t> slave
        Core 0's snapshot mark: the snap lines (docs/EVENTS.md).
    """

    SOURCES = ['snax_group.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, units: list, links: list,
            csr_base: int = 0, fork_links: list = ()):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'units': [dict(u) for u in units],
            'links': [dict(x) for x in links],
            'csr_base': csr_base,
            # written only when there is one, so every other group's properties stay as they were
            **({'fork_links': [dict(x) for x in fork_links]} if fork_links else {}),
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
