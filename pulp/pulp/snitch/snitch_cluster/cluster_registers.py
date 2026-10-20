#
# Copyright (C) 2020 GreenWaves Technologies, SAS, ETH Zurich and University of Bologna
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

import os
import tempfile
from pathlib import Path

import gvsoc.systree
import regmap.regmap
import regmap.regmap_hjson
import regmap.regmap_c_header

class ClusterRegisters(gvsoc.systree.Component):

    def __init__(self, parent, name, boot_addr=0, nb_cores=1, binary=None):
        super(ClusterRegisters, self).__init__(parent, name)

        self.add_sources(['pulp/snitch/snitch_cluster/cluster_registers.cpp'])

        self.add_properties({
            'boot_addr': boot_addr,
            'nb_cores': nb_cores
        })

    def gen(self, builddir, installdir):
        comp_path = 'pulp/snitch/snitch_cluster'
        regmap_path = f'{comp_path}/snitch_cluster_peripheral_reg.hjson'
        regmap_instance = regmap.regmap.Regmap('cluster_periph')
        regmap.regmap_hjson.import_hjson(regmap_instance, self.get_file_path(regmap_path))
        # SNAX: the headers are written beside the old ones and replace them only when
        # they differ, so a build with nothing changed does not recompile this component
        out = Path(builddir) / comp_path
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            regmap.regmap_c_header.dump_to_header(regmap=regmap_instance, name='cluster_periph',
                header_path=f'{tmp}/cluster_periph', headers=['regfields', 'gvsoc'])
            for new in Path(tmp).iterdir():
                old = out / new.name
                if not old.is_file() or old.read_bytes() != new.read_bytes():
                    os.replace(new, old)

    def o_EXTERNAL_IRQ(self, core: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'external_irq_{core}', itf, signature='wire<bool>')

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def i_BARRIER_ACK(self, core: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'barrier_req_{core}', signature='wire<bool>')

    def i_DMA_BUSY(self) -> gvsoc.systree.SlaveItf:
        """The DMA's busy state, counted by DMA_BUSY perf counters (SNAX)."""
        return gvsoc.systree.SlaveItf(self, 'dma_busy', signature='wire<bool>')

    def i_DMA_R_BEATS(self) -> gvsoc.systree.SlaveItf:
        """DMA read beats, counted by DMA_R_DONE perf counters (SNAX)."""
        return gvsoc.systree.SlaveItf(self, 'dma_r_beats', signature='wire<int>')

    def i_DMA_W_BEATS(self) -> gvsoc.systree.SlaveItf:
        """DMA write beats, counted by DMA_W_DONE perf counters (SNAX)."""
        return gvsoc.systree.SlaveItf(self, 'dma_w_beats', signature='wire<int>')

    def gen_gui(self, parent_signal):
        return gvsoc.gui.Signal(self, parent_signal, name=self.name, is_group=True, groups=["regmap"])