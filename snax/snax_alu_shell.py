#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_alu's accelerator (snax_alu_shell.cpp), after snax_alu_shell_wrapper.sv."""

import gvsoc.systree


class SnaxAluShell(gvsoc.systree.Component):
    """The ALU: num_pe lanes of add, sub, mul or xor, one beat per cycle.

    Its CSRs and its start, busy and counter rules are those of
    snax_alu_csr.sv and the ReqRspManager in front of it (snax_alu_shell.cpp).

    Parameters
    ----------
    csr_base : int
        Number of its first CSR, for the trace.
    num_pe : int
        Lanes, NumPE of the shell wrapper.
    data_width : int
        Bits per lane, DataWidth of the shell wrapper (only 64 is modelled).

    Ports
    -----
    input : io slave
        CSR accesses, offsets from the first CSR.
    in_a, in_b : io master
        The readers' beats (a streamer's reader_<i> ports).
    out : io master
        The writer's beats (a streamer's writer_<j> port).
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str, csr_base: int,
            num_pe: int, data_width: int):
        super().__init__(parent, name)

        self.add_sources(['snax_alu_shell.cpp'])

        self.add_properties({
            'csr_base': csr_base,
            'num_pe': num_pe,
            'data_width': data_width,
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_IN_A(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('in_a', itf, signature='io')

    def o_IN_B(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('in_b', itf, signature='io')

    def o_OUT(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('out', itf, signature='io')
