#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A tiled add accelerator on SnaxShell and SnaxUnit, written by hand (GEN3
step 2).

It stands in for the composite snax-forge's generator will write from a
BRM's binding (step 3): ElementwiseTiledSpatial with lanes 4, data width 64,
the op fixed to add (so no opSel CSR), lockstep, counted. The CSR mux and the
streamer are snax_alu_acc.py's, the streamer template unchanged, so its
programs set the streamer up as snax-alu does.

CSRs: the streamer's, 960 to 977 (streamer_csr_addr_map.h); then the shell's,
from SHELL_CSR_FIRST: loopCount (978), start (979), busy (980) and the
counter (981), read-only.
"""

import gvsoc.systree
import interco.router as router
from snax_streamer import SnaxStreamer, nb_csrs, nb_tcdm_ports, tcdm_port_names
from snax_shell import SnaxShell
from snax_unit import SnaxUnit
from snax_alu_acc import STREAMER_TEMPLATE, TCDM_SIZE, SNAX_CSR_FIRST, SNAX_CSR_LAST

# Where csr_mux switches from the streamer to the shell
SHELL_CSR_FIRST = SNAX_CSR_FIRST + nb_csrs(STREAMER_TEMPLATE)

# The configuration CSRs of ElementwiseTiledSpatial with a fixed op
SHELL_FIELDS = ['loopCount']

# ElementwiseOp's add; lanes and data width as the streamer's beat (4 x 64 bit)
UNIT_OP_ADD = 0
UNIT_LANES = 4
UNIT_DATA_WIDTH = 64


class SnaxTiledAddAcc(gvsoc.systree.Component):
    """The CSR mux, the streamer, SnaxShell and SnaxUnit (lockstep add).

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    tcdm_<i> : io master
        The streamer's TCDM ports (nb_tcdm_ports of them).
    tcdm_prio_<i> : wire<bool> master
        The priority bit of each TCDM port's request.
    """

    nb_tcdm_ports = nb_tcdm_ports(STREAMER_TEMPLATE)
    tcdm_port_names = ['streamer.' + name for name in tcdm_port_names(STREAMER_TEMPLATE)]

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        csr_mux = router.Router(self, 'csr_mux')

        streamer = SnaxStreamer(self, 'streamer', template=STREAMER_TEMPLATE,
            csr_base=SNAX_CSR_FIRST, tcdm_size=TCDM_SIZE)
        shell = SnaxShell(self, 'shell', csr_base=SHELL_CSR_FIRST, fields=SHELL_FIELDS)
        unit = SnaxUnit(self, 'unit', inputs=['a', 'b'], outputs=['out'], lanes=UNIT_LANES,
            data_width=UNIT_DATA_WIDTH, op=UNIT_OP_ADD, signed=False, control='counted',
            wait='lockstep', latency=0, ii=1, csr_base=SHELL_CSR_FIRST)

        # The streamer's range, then everything to the last SNAX CSR to the
        # shell, as snax_alu_acc.py does for the ALU
        streamer_base = 4 * SNAX_CSR_FIRST
        shell_base = 4 * SHELL_CSR_FIRST
        csr_mux.o_MAP(streamer.i_INPUT(), base=streamer_base,
            size=shell_base - streamer_base)
        csr_mux.o_MAP(shell.i_INPUT(), base=shell_base,
            size=4 * (SNAX_CSR_LAST + 1) - shell_base)

        shell.o_CTRL(unit.i_CTRL())
        unit.o_BUSY(shell.i_BUSY())

        # The beats: readers A and B in, the writer out
        unit.o_PORT('a', streamer.i_READER(0))
        unit.o_PORT('b', streamer.i_READER(1))
        unit.o_PORT('out', streamer.i_WRITER(0))

        self.bind(self, 'input', csr_mux, 'input')

        for port in range(0, self.nb_tcdm_ports):
            streamer.o_TCDM(port, self.i_TCDM_INTERNAL(port))
            streamer.o_TCDM_PRIORITY(port, self.i_TCDM_PRIORITY_INTERNAL(port))

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def i_TCDM_INTERNAL(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'tcdm_{port}', signature='io')

    def o_TCDM(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_{port}', itf, signature='io')

    def i_TCDM_PRIORITY_INTERNAL(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'tcdm_prio_{port}', signature='wire<bool>')

    def o_TCDM_PRIORITY(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_prio_{port}', itf, signature='wire<bool>')
