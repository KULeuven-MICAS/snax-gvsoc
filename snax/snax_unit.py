#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxUnit (snax_unit.cpp): one unit of accelerator.json, a datapath under its
nest controller, every number a property.

The rule (latency, II, jobs and job_beats), the op table and NumPy's
arithmetic on each port's type are in snax_unit.hpp. The C++ checks every
property and stops on a bad one, naming it; this class only passes them on,
so a design point compiles nothing (D134 in snax-forge).
"""

import gvsoc.systree


class SnaxUnit(gvsoc.systree.Component):
    """The datapath: lanes elements per beat, one op, latency L and II; with
    TreeAccumulate a fold, one result every job_beats firings.

    Parameters
    ----------
    datapath : str
        ElementwiseLanes (two inputs, the op per lane) or TreeAccumulate (one
        input, a fold: x is the beat's lanes summed through a tree, and the
        output's value is acc + x over the firings of one job, acc starting
        from the first x; the output one element).
    inputs : list[str]
        Input port names, in the op's operand order and the streamer's
        reader order.
    outputs : list[str]
        Output port names (one).
    lanes : int
        Elements per input beat.
    op : str
        The op's name: add, sub, mul, and, or, xor, min, max (TreeAccumulate:
        add); at NumPy's types (snax_unit.hpp): an elementwise op at the
        inputs' result type, cast to the output's; a fold's lanes cast to
        the output's type, the tree and acc at it.
    in_widths, in_signed : list
        Each input's element width (8, 16, 32 or 64; lanes * width a
        multiple of 64) and signedness, in inputs' order.
    out_widths, out_signed : list
        The output's, one each; lanes * width a multiple of 64 unless a fold
        (one word).
    latency : int
        Pipeline stages L (0: lockstep).
    ii : int
        Initiation interval.
    csr_base : int
        Number of its group's first CSR, for the trace.

    Ports
    -----
    <input>, <output> : io master
        The streamer's reader_<i> and writer_<j> ports.
    ctrl : io slave
        A start: a write of two words, jobs and job_beats.
    busy : wire<bool> master
        Busy from the next cycle on, driven on every change.
    """

    SOURCES = ['snax_unit.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, datapath: str,
            inputs: list, outputs: list, lanes: int, op: str, in_widths: list,
            in_signed: list, out_widths: list, out_signed: list, latency: int = 0, ii: int = 1,
            csr_base: int = 0):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'datapath': datapath,
            'inputs': list(inputs),
            'outputs': list(outputs),
            'lanes': lanes,
            'in_widths': list(in_widths),
            'in_signed': list(in_signed),
            'out_widths': list(out_widths),
            'out_signed': list(out_signed),
            'op': op,
            'latency': latency,
            'ii': ii,
            'csr_base': csr_base,
        })

    def i_CTRL(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'ctrl', signature='io')

    def o_PORT(self, port: str, itf: gvsoc.systree.SlaveItf):
        """Binds the input or output port named port."""
        self.itf_bind(port, itf, signature='io')

    def o_BUSY(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('busy', itf, signature='wire<bool>')

    def gen_gtkw(self, tree, comp_traces):
        """Its VCD signals (snax_unit.cpp), tagged snax, for gvrun's --vcd and view.gtkw."""
        tree.begin_group('snax_unit')
        for name, ext in (('busy', ''), ('fire', ''), ('push', ''), ('cycle_class', '[2:0]')):
            tree.add_trace(self, name, name, ext, tag='snax')
        tree.end_group('snax_unit')
