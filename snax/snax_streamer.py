#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A SNAX streamer (snax_streamer.cpp), configured as a cluster hjson's streamer template."""

import math

import gvsoc.systree
from snax_cfg import MOVERS, spatial_mismatch


# The keys of a mover group in the hjson's streamer template that the model
# reads; any other key is refused by name. dynamicPriority (default true) and
# higherStaticPriority (default false) are read as stream_param_gen.scala.tpl
# reads them.
MOVER_KEYS = ['spatial_bounds', 'temporal_dim', 'num_channel', 'fifo_depth', 'dynamicPriority',
    'higherStaticPriority']
# The keys of the streamer template the model reads (snax_cfg.MOVERS), or that do
# not change it
TEMPLATE_KEYS = [*MOVERS, 'snax_library_name']


def check_template(template: dict):
    """Refuses the keys of an hjson streamer template that the model does not cover.

    Parameters
    ----------
    template : dict
        The streamer template, as the cluster hjson gives it (e.g.
        snax_forge_streamer.hjson).
    """
    for key in template:
        if key not in TEMPLATE_KEYS:
            raise RuntimeError(f'Streamer template key not modelled: {key}')
    for group in MOVERS:
        for key in template.get(group, {}):
            if key not in MOVER_KEYS:
                raise RuntimeError(f'Streamer template key not modelled: {group}.{key}')


def movers_of(template: dict) -> list[dict]:
    """The template's movers, readers first then writers, as the streamer orders them; each
    mover's spatial bounds must multiply to its num_channel, as snax_cluster's StreamerParam
    requires (snax_cfg.spatial_mismatch)."""
    check_template(template)
    movers = []
    for group, is_reader, kind in [('data_reader_params', True, 'reader'),
            ('data_writer_params', False, 'writer')]:
        params = template.get(group)
        if params is None:
            continue
        for i in range(0, len(params['num_channel'])):
            spatial_bounds = list(params['spatial_bounds'][i])
            num_channel = params['num_channel'][i]
            why = spatial_mismatch(spatial_bounds, num_channel)
            if why is not None:
                raise RuntimeError(f'{group}[{i}]: {why}')
            movers.append({
                'name': f'{kind}{i}',
                'is_reader': is_reader,
                'spatial_bounds': spatial_bounds,
                'temporal_dim': params['temporal_dim'][i],
                'num_channel': num_channel,
                'fifo_depth': params['fifo_depth'][i],
                'dynamic_priority': 'dynamicPriority' not in params
                    or bool(params['dynamicPriority'][i]),
                'higher_static_priority': 'higherStaticPriority' in params
                    and bool(params['higherStaticPriority'][i]),
            })
    return movers


def nb_csrs(template: dict) -> int:
    """The streamer's CSRs: per mover the pointer (2), the spatial strides, the temporal
    bounds and strides; then start; then busy and the counter (Streamer.scala)."""
    rw = sum(2 + len(mover['spatial_bounds']) + 2 * mover['temporal_dim']
        for mover in movers_of(template))
    return rw + 1 + 2


def nb_tcdm_ports(template: dict) -> int:
    """The streamer's TCDM ports: one per channel (snax_tcdm_ports in the hjson)."""
    return sum(mover['num_channel'] for mover in movers_of(template))


def tcdm_port_names(template: dict) -> list[str]:
    """The owner of each TCDM port, in port order: <mover>.lane<l>."""
    return [f"{mover['name']}.lane{lane}" for mover in movers_of(template)
        for lane in range(0, mover['num_channel'])]


class SnaxStreamer(gvsoc.systree.Component):
    """A SNAX streamer: data movers with address generators and 64-bit TCDM ports.

    Parameters
    ----------
    template : dict
        The streamer template of the cluster hjson, with its keys
        (data_reader_params, data_writer_params; spatial_bounds, temporal_dim,
        num_channel, fifo_depth, dynamicPriority, higherStaticPriority).
    csr_base : int
        Number of the streamer's first CSR, for the trace.
    tcdm_size : int
        TCDM size in bytes; the address generators keep log2(tcdm_size) bits.

    Ports
    -----
    input : io slave
        CSR accesses, offsets from the first CSR (4 bytes per CSR).
    tcdm_<i> : io master
        Channel i's TCDM port, numbered readers first, as on the RTL.
    tcdm_prio_<i> : wire<bool> master
        The priority bit of channel i's request, set before each request.
    reader_<i> : io slave
        Reader i's beats to the accelerator (num_channel * 8 bytes; size 0 probes).
    writer_<j> : io slave
        Writer j's beats from the accelerator (num_channel * 8 bytes; size 0 probes).
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str, template: dict,
            csr_base: int, tcdm_size: int):
        super().__init__(parent, name)

        self.add_sources(['snax_streamer.cpp'])

        self.movers = movers_of(template)
        self.add_properties({
            'csr_base': csr_base,
            'addr_bits': int(math.log2(tcdm_size)),
            'movers': self.movers,
        })

    def gen_gtkw(self, tree, comp_traces):
        """Its VCD signals (snax_streamer.cpp), tagged snax, for gvrun's --vcd and view.gtkw."""
        tree.begin_group('snax_streamer')
        tree.add_trace(self, 'streamer_busy', 'streamer_busy', tag='snax')
        for mover in self.movers:
            name = mover['name']
            tree.add_trace(self, f'{name}_busy', f'{name}_busy', tag='snax')
            for lane in range(mover['num_channel']):
                count = f'{name}_lane{lane}_count'
                tree.add_trace(self, count, count, '[7:0]', tag='snax')
        tree.end_group('snax_streamer')

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_TCDM(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_{port}', itf, signature='io')

    def o_TCDM_PRIORITY(self, port: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'tcdm_prio_{port}', itf, signature='wire<bool>')

    def i_READER(self, reader: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'reader_{reader}', signature='io')

    def i_WRITER(self, writer: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'writer_{writer}', signature='io')
