#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxShell (snax_shell.cpp): the CSR manager in front of a SnaxUnit, GeMMX's
shell contract (D130 in snax-forge)."""

import gvsoc.systree


class SnaxShell(gvsoc.systree.Component):
    """The fields and start, read-write; busy and the counter, read-only.

    A start goes to the unit's ctrl when the unit is idle, and is held (the
    core stalls) while it is busy, as snax_shell.cpp says.

    Parameters
    ----------
    csr_base : int
        Number of its first CSR, for the trace.
    fields : list[str]
        The configuration CSRs, in order; the start CSR follows them.

    Ports
    -----
    input : io slave
        CSR accesses, offsets from the first CSR.
    ctrl : io master
        To the unit's ctrl: a start, the fields' words in CSR order.
    busy : wire<bool> slave
        The unit's busy.
    """

    SOURCES = ['snax_shell.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, csr_base: int,
            fields: list):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'csr_base': csr_base,
            'fields': list(fields),
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_CTRL(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('ctrl', itf, signature='io')

    def i_BUSY(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'busy', signature='wire<bool>')
