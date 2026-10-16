#
# Copyright (C) 2024 ETH Zurich and University of Bologna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import gvsoc.systree

class SnitchDma(gvsoc.systree.Component):
    """
    Snitch DMA

    This can be instantiated to handle memory transfers inside a Snitch cluster.

    Attributes
    ----------
    parent: gvsoc.systree.Component
        The parent component where this one should be instantiated.
    name: str
        The name of the component within the parent space.
    transfer_queue_size: int
        Number of transfer requests which can be queued to the DMA.
    burst_queue_size: int
        Maximum number of outstanding burst requests.
    loc_base: int
        Base address of the local area.
    loc_size: int
        Size of the local area.
    tcdm_width: int
        Width of the local interconnect, in bytes.
    beat_size: int
        Bytes per AXI beat, the unit of the beat counts on o_R_BEATS / o_W_BEATS (SNAX).
    read_latency: int
        Cycles the DMA's own read path adds before the first data of a read stream, on top of
        the latency the memory side returns (SNAX). 0 keeps the model as it was.
    tcdm_write_latency: int
        Cycles from a line leaving the DMA to its write in the local memory; the line is
        acknowledged when it leaves (SNAX). 0 keeps the model as it was.
    one_cycle_per_stage: bool
        The midend, the backend and the AXI read take work from the cycle after it arrives,
        also when their event is already queued for the cycle it arrives in (SNAX). False
        keeps the model as it was.
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str,
            transfer_queue_size: int=8,
            burst_queue_size: int=8,
            burst_size: int=0,
            loc_base: int=0,
            loc_size: int=0,
            tcdm_width: int=0,
            beat_size: int=64,
            read_latency: int=0,
            tcdm_write_latency: int=0,
            one_cycle_per_stage: bool=False):

        super().__init__(parent, name)

        self.add_sources([
            'pulp/idma/snitch_dma.cpp',
            'pulp/idma/fe/idma_fe_xdma.cpp',
            'pulp/idma/me/idma_me_2d.cpp',
            'pulp/idma/be/idma_be.cpp',
            'pulp/idma/be/idma_be_axi.cpp',
            'pulp/idma/be/idma_be_tcdm.cpp',
        ])

        self.add_properties({
            "transfer_queue_size": transfer_queue_size,
            "burst_queue_size": burst_queue_size,
            "burst_size" : burst_size,
            "loc_base": loc_base,
            "loc_size": loc_size,
            "tcdm_width": tcdm_width,
            "beat_size": beat_size,
            "read_latency": read_latency,
            "tcdm_write_latency": tcdm_write_latency,
            "one_cycle_per_stage": one_cycle_per_stage,
        })

    def i_OFFLOAD(self) -> gvsoc.systree.SlaveItf:
        """Returns the offload port.

        This is used by the core to offload xdma instructions.\n

        Returns
        ----------
        gvsoc.systree.SlaveItf
            The slave interface
        """
        return gvsoc.systree.SlaveItf(self, 'offload', signature='wire<IssOffloadInsn<uint32_t>*>')

    def o_OFFLOAD_GRANT(self, itf: gvsoc.systree.SlaveItf):
        """Binds the offload grant port.

        This port is used for granting dmcpy instruction which was previously blocked because
        the queue was full.\n

        Parameters
        ----------
        slave: gvsoc.systree.SlaveItf
            Slave interface
        """
        self.itf_bind('offload_grant', itf, signature='wire<IssOffloadInsnGrant<uint32_t>*>')

    def o_AXI(self, itf: gvsoc.systree.SlaveItf):
        """Binds the AXI port.

        This port is used for sending burst requests to the AXI interconnect.\n

        Parameters
        ----------
        slave: gvsoc.systree.SlaveItf
            Slave interface
        """
        self.itf_bind('axi_read', itf, signature='io')
        self.itf_bind('axi_write', itf, signature='io')

    def o_TCDM(self, itf: gvsoc.systree.SlaveItf):
        """Binds the TCDM port.

        This port is used for sending line requests to the TCDM memory.\n

        Parameters
        ----------
        slave: gvsoc.systree.SlaveItf
            Slave interface
        """
        self.itf_bind('tcdm_read', itf, signature='io')
        self.itf_bind('tcdm_write', itf, signature='io')

    def o_BUSY(self, itf: gvsoc.systree.SlaveItf):
        """Binds the busy output (SNAX).

        High while a transfer is queued or running, the state dmstat 2 returns, as the
        RTL's busy_o that the cluster's DMA_BUSY perf counter counts.
        """
        self.itf_bind('busy', itf, signature='wire<bool>')

    def o_R_BEATS(self, itf: gvsoc.systree.SlaveItf):
        """Binds the read beat output (SNAX): the AXI read beats of each queued copy."""
        self.itf_bind('r_beats', itf, signature='wire<int>')

    def o_W_BEATS(self, itf: gvsoc.systree.SlaveItf):
        """Binds the write beat output (SNAX): the AXI write beats of each queued copy."""
        self.itf_bind('w_beats', itf, signature='wire<int>')
