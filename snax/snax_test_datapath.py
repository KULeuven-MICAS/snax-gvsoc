#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A test datapath in the ALU's place (snax_test_datapath.cpp), until the ALU model (SG4)."""

import gvsoc.systree


class SnaxTestDatapath(gvsoc.systree.Component):
    """Copies a beat from in_a or in_b to out, one firing at most every k cycles.

    It holds the ALU's 5 CSRs (mode, length, start; busy, counter): mode bit 0
    picks the copied input (0: in_a, 1: in_b), mode bits 7:4 are k - 1.

    Parameters
    ----------
    csr_base : int
        Number of its first CSR, for the trace.
    beat_bytes : int
        Bytes per beat (8 per lane).

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
            beat_bytes: int):
        super().__init__(parent, name)

        self.add_sources(['snax_test_datapath.cpp'])

        self.add_properties({
            'csr_base': csr_base,
            'beat_bytes': beat_bytes,
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_IN_A(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('in_a', itf, signature='io')

    def o_IN_B(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('in_b', itf, signature='io')

    def o_OUT(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('out', itf, signature='io')
