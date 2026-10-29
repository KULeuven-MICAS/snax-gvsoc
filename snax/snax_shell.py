#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""SnaxShell (snax_shell.cpp): the CSRs of one group of an accelerator in front
of its SnaxGroup, GeMMX's shell contract (D130, D146 in snax-forge)."""

import gvsoc.systree


class SnaxShell(gvsoc.systree.Component):
    """START, JOBS and the units' CSRs, read-write; STATUS and COUNTER, read-only.

    A start goes to the group's ctrl as JOBS and every JOB_BEATS (JOBS and 1
    without one) when the group is idle, and is held (the core stalls) while it
    is busy; JOBS or a JOB_BEATS 0 is the empty run, ended by the shell, as
    snax_shell.hpp says.

    Parameters
    ----------
    csr_base : int
        Number of the group's first CSR (its START), for the trace.
    csrs : list[str]
        The group's read-write CSRs in CSR order: START, JOBS, then the
        units' (JOB_BEATS for each fold without a fixed T, in unit order).
        STATUS and COUNTER follow them.

    Ports
    -----
    input : io slave
        CSR accesses, offsets from the group's first CSR.
    ctrl : io master
        To the group's ctrl: a start, JOBS and every JOB_BEATS.
    busy : wire<bool> slave
        The group's busy.
    """

    SOURCES = ['snax_shell.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, csr_base: int,
            csrs: list):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'csr_base': csr_base,
            'csrs': list(csrs),
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_CTRL(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('ctrl', itf, signature='io')

    def i_BUSY(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'busy', signature='wire<bool>')
