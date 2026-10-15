#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""snax_alu's accelerator as snax_cluster builds it (snax_acc_wrapper.sv.tpl).

The composite bound to the compute core's snax_csr port. csr_mux splits the
core's CSR accesses between the streamer and the ALU as snax_csr_mux_demux.sv
does: the streamer's CSRs first, everything above them to the ALU. Each block
sees offsets from its own first CSR, as each CSR manager does on the RTL. The
streamer's channels leave the composite as its TCDM ports.

The ALU (alu, snax_alu_shell.py) takes the beats of readers A and B and gives
the writer their sum, difference, product or xor, as snax_alu_shell_wrapper.sv
does.
"""

import gvsoc.systree
import interco.router as router
from snax_streamer import SnaxStreamer, nb_csrs, nb_tcdm_ports, tcdm_port_names
from snax_alu_shell import SnaxAluShell


# snax_alu_streamer_template of snax_cluster's cfg/snax_alu_cluster_old.hjson
# at b2672f8 (unchanged up to the pin, 9fbf35d), with the hjson's keys
STREAMER_TEMPLATE = {
    'data_reader_params': {
        'spatial_bounds': [[4], [4]],
        'temporal_dim': [1, 1],
        'num_channel': [4, 4],
        'fifo_depth': [8, 8],
    },
    'data_writer_params': {
        'spatial_bounds': [[4]],
        'temporal_dim': [1],
        'num_channel': [4],
        'fifo_depth': [8],
    },
    'snax_library_name': 'snax-alu',
}

# The hjson's cluster tcdm.size (128 KiB): the address generators keep its
# log2, 17 bits
TCDM_SIZE = 128 * 1024

# The first SNAX CSR (CSR_SNAX_BEGIN, 960) and the last one the core sends
# out (1535). The core puts CSR n at byte address 4 * n on its snax_csr port.
SNAX_CSR_FIRST = 0x3C0
SNAX_CSR_LAST = 0x5FF

# The streamer's CSRs come first: 3 movers x 5 read-write CSRs and start, then
# busy and the performance counter, 960 to 977 (streamer_csr_addr_map.h).
# Where csr_mux switches to the ALU: AddrSelOffSet of snax_csr_mux_demux.sv.
ALU_CSR_FIRST = SNAX_CSR_FIRST + nb_csrs(STREAMER_TEMPLATE)

# The ALU's 5 CSRs follow, from snax-alu-lib.h: mode, length, start (978 to
# 980), then busy and the performance counter, read-only (981, 982).

# The shell wrapper's NumPE and DataWidth: a beat between the streamer and the
# ALU is 4 lanes of 64 bit
ALU_NUM_PE = 4
ALU_DATA_WIDTH = 64


class SnaxAluAcc(gvsoc.systree.Component):
    """snax_alu's accelerator: the CSR mux, the streamer and the ALU.

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    tcdm_<i> : io master
        The streamer's TCDM ports (nb_tcdm_ports of them).
    """

    # The cluster binds this many TCDM ports (snax_tcdm_ports in the hjson),
    # named in the crossbar's trace by their owner
    nb_tcdm_ports = nb_tcdm_ports(STREAMER_TEMPLATE)
    tcdm_port_names = ['streamer.' + name for name in tcdm_port_names(STREAMER_TEMPLATE)]

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        # Synchronous, no bandwidth and no latency: a request is forwarded in
        # the call that brings it, as through the RTL's combinational mux.
        csr_mux = router.Router(self, 'csr_mux')

        streamer = SnaxStreamer(self, 'streamer', template=STREAMER_TEMPLATE,
            csr_base=SNAX_CSR_FIRST, tcdm_size=TCDM_SIZE)
        alu = SnaxAluShell(self, 'alu', csr_base=ALU_CSR_FIRST, num_pe=ALU_NUM_PE,
            data_width=ALU_DATA_WIDTH)

        # The streamer's range, and everything from the ALU's first CSR to the
        # last SNAX CSR to the ALU, as the RTL mux does (sel_output). Each
        # mapping removes its base, so a block sees offsets from its first CSR.
        streamer_base = 4 * SNAX_CSR_FIRST
        alu_base = 4 * ALU_CSR_FIRST
        csr_mux.o_MAP(streamer.i_INPUT(), base=streamer_base,
            size=alu_base - streamer_base)
        csr_mux.o_MAP(alu.i_INPUT(), base=alu_base,
            size=4 * (SNAX_CSR_LAST + 1) - alu_base)

        # The beats: readers A and B in, the writer out (snax_alu_shell_wrapper.sv)
        alu.o_IN_A(streamer.i_READER(0))
        alu.o_IN_B(streamer.i_READER(1))
        alu.o_OUT(streamer.i_WRITER(0))

        self.bind(self, 'input', csr_mux, 'input')

        for port in range(0, self.nb_tcdm_ports):
            streamer.o_TCDM(port, self.i_TCDM_INTERNAL(port))

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def i_TCDM_INTERNAL(self, port: int) -> gvsoc.systree.SlaveItf:
        # Inside the composite: the streamer's port i leaves as tcdm_<i>
        return gvsoc.systree.SlaveItf(self, f'tcdm_{port}', signature='io')

    def o_TCDM(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_{port}', itf, signature='io')
