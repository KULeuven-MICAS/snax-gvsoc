#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""What every SNAX accelerator composite shares (snax_alu_acc.py, snax_unit_acc.py): the CSR
range the core sends out, the part of it an accelerator may use, and the ports the cluster
binds."""

import gvsoc.systree


# The first SNAX CSR (CSR_SNAX_BEGIN, 960) and the last one the core sends
# out (1535). The core puts CSR n at byte address 4 * n on its snax_csr port.
SNAX_CSR_FIRST = 0x3C0
SNAX_CSR_LAST = 0x5FF
# The last CSR an accelerator may use: snax_cluster's hw/snitch/src/csr_snax_def.sv reserves
# 0x5FE (CSR_SNAX_READ_TASK_READY_QUEUE) and 0x5FF (CSR_SNAX_WRITE_TASK_DONE_QUEUE), which
# hw/snax_util/src/snax_intf_translator.sv routes to the cluster's top-level CSR port, not
# to the accelerator
SNAX_ACC_CSR_LAST = 0x5FD


class SnaxAcc(gvsoc.systree.Component):
    """A composite bound to a core's snax_csr port, its streamer's channels leaving it as its
    TCDM ports.

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    tcdm_<i> : io master
        The streamer's TCDM ports (nb_tcdm_ports of them).
    tcdm_prio_<i> : wire<bool> master
        The priority bit of each TCDM port's request.
    """

    # The cluster binds this many TCDM ports (snax_tcdm_ports in the hjson),
    # named in the crossbar's trace by their owner
    nb_tcdm_ports = 0
    tcdm_port_names = []

    def bind_ports(self, csr_mux, streamer):
        """The composite's input into csr_mux, and the streamer's TCDM ports out as its own."""
        self.bind(self, 'input', csr_mux, 'input')

        for port in range(0, self.nb_tcdm_ports):
            streamer.o_TCDM(port, self.i_TCDM_INTERNAL(port))
            streamer.o_TCDM_PRIORITY(port, self.i_TCDM_PRIORITY_INTERNAL(port))

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def i_TCDM_INTERNAL(self, port: int) -> gvsoc.systree.SlaveItf:
        # Inside the composite: the streamer's port i leaves as tcdm_<i>
        return gvsoc.systree.SlaveItf(self, f'tcdm_{port}', signature='io')

    def o_TCDM(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_{port}', itf, signature='io')

    def i_TCDM_PRIORITY_INTERNAL(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'tcdm_prio_{port}', signature='wire<bool>')

    def o_TCDM_PRIORITY(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_prio_{port}', itf, signature='wire<bool>')
