#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxUnit (snax_unit.cpp): a Chisel block's datapath, every number a property.

The rule (lockstep, pipelined) and the op table are in snax_unit.hpp. The
C++ checks every property and stops on a bad one, naming it; this class only
passes them on, so a design point compiles nothing (D134 in snax-forge).
"""

import gvsoc.systree


class SnaxUnit(gvsoc.systree.Component):
    """The datapath: lanes elements per beat, one op, lockstep or pipelined;
    with one input a fold, one result every rate firings.

    Parameters
    ----------
    inputs : list[str]
        Input port names, in the op's operand order: two, or one for a fold
        (x is the beat's lanes reduced by op through a tree, and the output's
        value is op(acc, x) over the firings of one output, acc starting from
        the first x; the output one element).
    outputs : list[str]
        Output port names (one).
    lanes : int
        Elements per input beat.
    data_width : int
        Without the four lists below: every port's width, 8, 16, 32 or 64.
    op : int
        ElementwiseOp's encoding: add 0, sub 1, mul 2, and 3, or 4, xor 5,
        min 6, max 7; at NumPy's types (snax_unit.hpp): an elementwise op at
        the inputs' result type, cast to the output's; a fold's lanes cast to
        the output's type, the tree and acc at it.
    signed : bool
        Without the four lists: every port's signedness.
    in_widths, in_signed : list
        Each input's element width (8, 16, 32 or 64; lanes * width a
        multiple of 64) and signedness, in inputs' order.
    out_widths, out_signed : list
        The output's, one each; lanes * width a multiple of 64 unless a fold
        (one word). All four lists or none.
    control : str
        counted: the unit counts its firings.
    config : list[str]
        The role of each configuration word the shell sends, in order:
        count (the run's firings) and rate (firings per output; a fold,
        pipelined). Default ['count'].
    wait : str
        lockstep or pipelined.
    latency : int
        Pipeline stages L (pipelined; 0 for lockstep).
    ii : int
        Initiation interval (pipelined; 1 for lockstep).
    csr_base : int
        Number of the shell's first CSR, for the trace.

    Ports
    -----
    <input>, <output> : io master
        The streamer's reader_<i> and writer_<j> ports.
    ctrl : io slave
        A start: a write of the configuration words in CSR order.
    busy : wire<bool> master
        Busy from the next cycle on, driven on every change.
    """

    SOURCES = ['snax_unit.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, inputs: list,
            outputs: list, lanes: int, op: int, data_width: int = None, signed: bool = False,
            control: str = 'counted', wait: str = 'lockstep', latency: int = 0, ii: int = 1,
            csr_base: int = 0, config: list = None, in_widths: list = None,
            in_signed: list = None, out_widths: list = None, out_signed: list = None):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        # Only the types given: the C++ refuses a partial set of the lists
        types = {'data_width': data_width, 'signed': signed, 'in_widths': in_widths,
            'in_signed': in_signed, 'out_widths': out_widths, 'out_signed': out_signed}
        self.add_properties({key: list(value) if isinstance(value, (list, tuple)) else value
            for key, value in types.items() if value is not None})
        self.add_properties({
            'inputs': list(inputs),
            'outputs': list(outputs),
            'lanes': lanes,
            'op': op,
            'control': control,
            'config': list(config) if config is not None else ['count'],
            'wait': wait,
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
