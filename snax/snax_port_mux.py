#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A shared streamer's data-side mux (snax_port_mux.cpp, snax-forge D169)."""

import gvsoc.systree


class SnaxPortMux(gvsoc.systree.Component):
    """Between a streamer set's shared movers and its groups' ports, selected by PORT_MUX_SEL.

    Parameters
    ----------
    csr_base : int
        Number of PORT_MUX_SEL, for the trace.
    sel_width : int
        PORT_MUX_SEL's width in bits.
    groups : list
        The groups' names, in PORT_MUX_SEL's order (accelerator.json's port_mux.groups).
    movers : list
        The streamer's movers in its order, each {name, is_reader, num_channel}.
    ports : list
        The groups' ports, each {name, group (index in groups), mover (index in movers),
        num_channel}.

    Ports
    -----
    input : io slave
        PORT_MUX_SEL at offset 0.
    busy : wire<bool> slave
        The streamer's busy.
    port_<i> : io slave
        ports[i]'s beats, from its group.
    mover_<k> : io master
        To the streamer's reader or writer of movers[k].
    """

    SOURCES = ['snax_port_mux.cpp']

    def __init__(self, parent: gvsoc.systree.Component, name: str, csr_base: int,
            sel_width: int, groups: list, movers: list, ports: list):
        super().__init__(parent, name)

        self.add_sources(self.SOURCES)

        self.add_properties({
            'csr_base': csr_base,
            'sel_width': sel_width,
            'groups': list(groups),
            'movers': list(movers),
            'ports': list(ports),
        })

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def i_BUSY(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'busy', signature='wire<bool>')

    def i_PORT(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'port_{port}', signature='io')

    def o_MOVER(self, mover: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'mover_{mover}', itf, signature='io')
