#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A stand-in for the CSR side of a SNAX accelerator (snax_csr_stub.cpp)."""

import gvsoc.systree


class SnaxCsrStub(gvsoc.systree.Component):
    """Read-write CSRs that read back what was written, read-only CSRs that read 0.

    Bound to a Snitch core's snax_csr port. Any other CSR, or a write to a
    read-only one, is refused and stops the run.

    Parameters
    ----------
    rw_csrs : list[int]
        Numbers of the read-write CSRs.
    ro_csrs : list[int]
        Numbers of the read-only CSRs.
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str,
            rw_csrs: list[int], ro_csrs: list[int]):
        super().__init__(parent, name)

        self.add_sources(['snax_csr_stub.cpp'])

        self.add_properties({
            'rw_csrs': list(rw_csrs),
            'ro_csrs': list(ro_csrs),
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')
