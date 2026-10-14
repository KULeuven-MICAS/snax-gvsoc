#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_alu's accelerator as snax_cluster builds it (snax_acc_wrapper.sv.tpl).

The composite bound to the compute core's snax_csr port. A router splits the
core's CSR accesses between the streamer and the ALU as snax_csr_mux_demux.sv
does: the streamer's CSRs first, everything above them to the ALU. Each block
sees offsets from its own first CSR, as each CSR manager does on the RTL.

For now both blocks are stubs that hold their CSRs (snax_csr_stub.py); the
streamer model (SG3) and the ALU model (SG4) replace them.
"""

import gvsoc.systree
import interco.router as router
from snax_csr_stub import SnaxCsrStub


# The first SNAX CSR (CSR_SNAX_BEGIN, 0x3C0) and the last one the core sends
# out (0x5FF). The core puts CSR n at byte address 4 * n on its snax_csr port.
SNAX_CSR_FIRST = 960
SNAX_CSR_LAST = 0x5FF

# The streamer's CSRs, from the app's streamer_csr_addr_map.h: 3 movers x 5
# read-write CSRs and the start CSR (960 to 975), then busy and the performance
# counter, read-only (976, 977).
STREAMER_RW_CSRS = list(range(960, 976))
STREAMER_RO_CSRS = [976, 977]
# The ALU's, from snax-alu-lib.h: mode, length, start (978 to 980), then busy
# and the performance counter, read-only (981, 982).
ALU_RW_CSRS = [978, 979, 980]
ALU_RO_CSRS = [981, 982]

# Where the router switches to the ALU: AddrSelOffSet of snax_csr_mux_demux.sv,
# the streamer's CSR count.
ALU_CSR_FIRST = SNAX_CSR_FIRST + len(STREAMER_RW_CSRS) + len(STREAMER_RO_CSRS)


class SnaxAluAcc(gvsoc.systree.Component):
    """snax_alu's accelerator: the CSR router, the streamer and the ALU.

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        # Synchronous, no bandwidth and no latency: a request is forwarded in
        # the call that brings it, as through the RTL's combinational mux.
        csr = router.Router(self, 'csr')

        streamer = SnaxCsrStub(self, 'streamer', csr_base=SNAX_CSR_FIRST,
            rw_csrs=STREAMER_RW_CSRS, ro_csrs=STREAMER_RO_CSRS)
        alu = SnaxCsrStub(self, 'alu', csr_base=ALU_CSR_FIRST,
            rw_csrs=ALU_RW_CSRS, ro_csrs=ALU_RO_CSRS)

        # The streamer's range, and everything from the ALU's first CSR to the
        # last SNAX CSR to the ALU, as the RTL mux does (sel_output). Each
        # mapping removes its base, so a block sees offsets from its first CSR.
        streamer_base = 4 * SNAX_CSR_FIRST
        alu_base = 4 * ALU_CSR_FIRST
        csr.o_MAP(streamer.i_INPUT(), base=streamer_base,
            size=alu_base - streamer_base)
        csr.o_MAP(alu.i_INPUT(), base=alu_base,
            size=4 * (SNAX_CSR_LAST + 1) - alu_base)

        self.bind(self, 'input', csr, 'input')

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')
