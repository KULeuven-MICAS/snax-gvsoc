#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The standard composite of an accelerator slot with an accelerator.json: the
CSR mux, one streamer per streamer set, per group one SnaxShell and one
SnaxGroup, and per shared set (snax-forge D169) one SnaxPortMux.

    SnaxAccelerator.for_slot(slot, tcdm_size, file) -> class

The slot (snax_cfg.AccSlot) gives its streamer sets and the description
(snax_cfg.Description), one accelerator per set in the sets' order, the
cluster its TCDM size. Set k's streamer is `streamer_<set>`; each entry of
its accelerator's inputs ("<unit>.<port>") takes that streamer's reader of
its index, each entry of its outputs the writer of its index; a port on a
link (snax-forge C§17) is the group's own and meets no streamer.

A shared set (accelerator.json's movers and port_mux, snax-forge D169) has its
groups share its streamer's movers: its outer ports bind to `port_mux_<set>`
(SnaxPortMux), one port per mover user in the movers' order, and the mux's
mover k to the streamer's k-th mover (readers, then writers); the streamer's
busy wire goes to the mux. PORT_MUX_SEL, the accelerator's last CSR, goes to
the mux, and its last group's window ends before it.

CSRs (snax-forge D157, snax_cluster's csr_range_table; csr_layout): set k
holds [b_k, b_k + s_k + c_k), its streamer's s_k CSRs (nb_csrs of its
template) from b_k, then its accelerator's c_k from b_k + s_k; b_0 is
SNAX_CSR_FIRST (960) and b_{k+1} = b_k + s_k + c_k. accelerator.json's
offsets run over all the accelerators from 0 (the shell's view): an
accelerator's CSR at offset o is at b_k + s_k + o - o_k, o_k its first
offset. Each group's window (START, JOBS, its units' R/W CSRs, STATUS,
BUSY_COUNTER) goes to its shell, and a shared set's PORT_MUX_SEL to its mux. The
last CSR must be at most SNAX_ACC_CSR_LAST.

The TCDM ports are the streamers' channels, set after set, each streamer's
readers first: the cluster names port p by its owner,
`streamer_<set>.<mover>.lane<l>`.

Names (component_names, over every group of the description): with one
group of one unit, the shell is `shell` and the group `unit`
(snax_acc<i>/unit, the trace path snax-forge's manifests name); with several
groups of one unit each, `shell_<group>` and `unit_<unit>`; a linked group
(several units) is `group_<group>`, its shell `shell_<group>`.

Each SnaxGroup gets its units in the group's order (group_units): per unit
its datapath, its inputs in BRM port order (an outer one named
`<unit>_<port>`, a linked one ""), seed (the index of a fold's seed among
them, the last, or -1), its output (outer, or "" when linked), its
types, timing and t: params.T when the unit has one, 0 for a fold's
JOB_BEATS, else 1; SimdLanes' baked slots (k, k1, k2) and the ones it reads
from its CSRs (scalars, each [slot, words]); and its links as edges, each {from, to, to_input, depth}:
the producer's and the consumer's names and the consumer's input it feeds,
its index in that unit's inputs.
"""

from dataclasses import dataclass

import gvsoc.systree
import interco.router as router
from snax_cfg import (CATALOGUE, DTYPES, SEED, CfgTargetError, dirs_of, scalar_csrs,
                      streamer_channels)
from snax_group import SnaxGroup
from snax_port_mux import SnaxPortMux
from snax_shell import SnaxShell
from snax_streamer import SnaxStreamer, nb_csrs, tcdm_port_names

# The first SNAX CSR (CSR_SNAX_BEGIN, 960) and the last one the core sends
# out (1535). The core puts CSR n at byte address 4 * n on its snax_csr port.
SNAX_CSR_FIRST = 0x3C0
SNAX_CSR_LAST = 0x5FF
# The last CSR an accelerator may use: snax_cluster's hw/snitch/src/csr_snax_def.sv reserves
# 0x5FE (CSR_SNAX_READ_TASK_READY_QUEUE) and 0x5FF (CSR_SNAX_WRITE_TASK_DONE_QUEUE), which
# hw/snax_util/src/snax_intf_translator.sv routes to the cluster's top-level CSR port, not
# to the accelerator
SNAX_ACC_CSR_LAST = 0x5FD


def compile_components():
    """Has the build compile SnaxShell, SnaxGroup and SnaxPortMux, as it would for a target
    whose tree holds them: a cluster file with an accelerator runs on the installed components,
    whatever a built target's default file holds. The build path only (gvsoc.systree's
    registry)."""
    for sources in (SnaxShell.SOURCES, SnaxGroup.SOURCES, SnaxPortMux.SOURCES):
        gvsoc.systree.get_generated_component(list(sources), [], [])


@dataclass(frozen=True)
class SetLayout:
    """A streamer set's CSRs (module doc): its name, streamer template and accelerator, its
    first CSR b_k (its streamer's), s_k its streamer's CSRs, c_k its accelerator's."""

    name: str
    template: dict
    accelerator: object
    first: int
    streamer_csrs: int
    own_csrs: int

    @property
    def own(self) -> int:
        """Its accelerator's first CSR: b_k + s_k."""
        return self.first + self.streamer_csrs

    @property
    def end(self) -> int:
        """The CSR after its last: b_{k+1}."""
        return self.own + self.own_csrs

    def csr(self, offset: int) -> int:
        """The CSR of its accelerator's CSR at accelerator.json's offset."""
        return self.own + offset - self.accelerator.csrs[0].offset


def csr_layout(slot) -> list:
    """The slot's sets' CSRs (SetLayout), packed from SNAX_CSR_FIRST."""
    layout, first = [], SNAX_CSR_FIRST
    for s, acc in zip(slot.sets, slot.description.accelerators):
        row = SetLayout(s.name, s.streamer, acc, first, nb_csrs(s.streamer), len(acc.csrs))
        layout.append(row)
        first = row.end
    return layout


def component_names(description) -> tuple:
    """The shells' and the groups' component names, by group: shell and unit for one group of
    one unit; else shell_<group>, and unit_<unit> for a group of one unit, group_<group> for a
    linked group."""
    groups = description.groups
    single = len(groups) == 1 and len(groups[0].units) == 1
    shells = {g.name: 'shell' if single else f'shell_{g.name}' for g in groups}
    comps = {g.name: ('unit' if single else f'unit_{g.units[0].name}') if len(g.units) == 1
             else f'group_{g.name}' for g in groups}
    return shells, comps


def group_units(accelerator, group) -> tuple:
    """SnaxGroup's units and links properties for group (module doc)."""
    to = {link.to: link for link in group.links}
    frm = {link.from_: link for link in group.links}
    units, ins_of = [], {}
    for u in group.units:
        dirs = dirs_of(u)
        ins = ins_of[u.name] = [p for p in u.ports if dirs[p] == 'in']
        (out,) = [p for p in u.ports if dirs[p] == 'out']
        in_ports = [u.ports[p] for p in ins]
        out_port = u.ports[out]
        facts = CATALOGUE[u.datapath]
        op_width, op_signed = (DTYPES[u.op_type] if facts.typed
                               else (out_port.width, out_port.signed))
        t = u.params['T'] if 'T' in u.params else 0 if facts.is_fold(u.params) else 1
        units.append({
            'name': u.name, 'datapath': u.datapath,
            'inputs': ['' if f'{u.name}.{p}' in to else f'{u.name}_{p}' for p in ins],
            'seed': ins.index(SEED) if SEED in ins else -1,
            'output': '' if f'{u.name}.{out}' in frm else f'{u.name}_{out}',
            'lanes': in_ports[0].lanes,
            'in_widths': [p.width for p in in_ports], 'in_signed': [p.signed for p in in_ports],
            'out_width': out_port.width, 'out_signed': out_port.signed,
            'op_width': op_width, 'op_signed': op_signed,
            'op': u.params.get('op', 'add'),
            'accumulate': bool(u.params.get('accumulate', True)),
            'reg_out': bool(u.params.get('regOut', False)),
            'k': str(u.params['k']) if 'k' in u.params else '',
            'k1': str(u.params['k1']) if 'k1' in u.params else '',
            'k2': str(u.params['k2']) if 'k2' in u.params else '',
            'scalars': [[s, len(scalar_csrs(s, dtype))] for s, dtype in u.scalars.items()],
            'latency': u.latency, 'ii': u.ii, 'span': u.span, 't': t,
        })
    links = []
    for x in group.links:
        src, dst = x.from_.split('.', 1)[0], x.to.split('.', 1)
        links.append({'from': src, 'to': dst[0], 'to_input': ins_of[dst[0]].index(dst[1]),
                      'depth': x.depth})
    return units, links


def mux_ports(accelerator) -> list:
    """A shared accelerator's SnaxPortMux ports: every mover's users in the movers' order, each
    {name, group (its index in port_mux.groups), mover, num_channel}."""
    groups = list(accelerator.port_mux.groups)
    return [{'name': u.port, 'group': groups.index(u.group), 'mover': k,
             'num_channel': u.num_channel}
            for k, m in enumerate(accelerator.movers) for u in m.users]


class SnaxAccelerator(gvsoc.systree.Component):
    """The CSR mux, the streamers, the shells and groups of one slot, bound to a core's
    snax_csr port, its streamers' channels leaving it as its TCDM ports; for_slot gives the
    slot's class.

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    tcdm_<i> : io master
        The streamers' TCDM ports (nb_tcdm_ports of them), set after set.
    tcdm_prio_<i> : wire<bool> master
        The priority bit of each TCDM port's request.
    """

    # Set by for_slot: the sets' CSR layout (SetLayout), the description, the TCDM size, and
    # the TCDM ports the cluster binds (snax_tcdm_ports in the hjson), named in the crossbar's
    # trace by their owner
    layout = []
    description = None
    tcdm_size = None
    nb_tcdm_ports = 0
    tcdm_port_names = []

    @classmethod
    def for_slot(cls, slot, tcdm_size: int, file='?'):
        """The class of the slot's composite, with the class attributes the cluster reads
        (nb_tcdm_ports, tcdm_port_names)."""
        layout = csr_layout(slot)
        last = layout[-1].end - 1
        if last > SNAX_ACC_CSR_LAST:
            raise CfgTargetError(file, slot.at,
                f"the accelerator's last CSR {last} is past {SNAX_ACC_CSR_LAST}, the last an "
                "accelerator may use (sets " + ', '.join(
                    f'{row.name} {row.first}-{row.end - 1}' for row in layout) + ')')
        return type(f'SnaxAccelerator_{slot.name}', (cls,), {
            'layout': layout,
            'description': slot.description,
            'tcdm_size': tcdm_size,
            'nb_tcdm_ports': sum(streamer_channels(row.template) for row in layout),
            'tcdm_port_names': [f'streamer_{row.name}.{name}' for row in layout
                                for name in tcdm_port_names(row.template)],
        })

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        shell_names, group_names = component_names(self.description)
        csr_mux = router.Router(self, 'csr_mux')
        self.bind(self, 'input', csr_mux, 'input')

        port = 0
        for k, row in enumerate(self.layout):
            streamer = SnaxStreamer(self, f'streamer_{row.name}', template=row.template,
                csr_base=row.first, tcdm_size=self.tcdm_size)
            csr_mux.o_MAP(streamer.i_INPUT(), base=4 * row.first, size=4 * row.streamer_csrs)

            acc = row.accelerator
            # The set's end: the next set's streamer, past the last set everything to the last
            # SNAX CSR, which the block holding the set's last CSR refuses
            set_end = row.end if k + 1 < len(self.layout) else SNAX_CSR_LAST + 1
            mux_csr = None if acc.port_mux is None else row.csr(acc.port_mux.csr.offset)
            owner = {}
            for j, group in enumerate(acc.groups):
                base = row.csr(group.window[0].offset)
                shell = SnaxShell(self, shell_names[group.name], csr_base=base, csrs=group.rw,
                    widths=group.rw_widths, busy_counter_width=group.busy_counter_width)
                # The group's window; the set's last group's to PORT_MUX_SEL or the set's end
                end = (row.csr(acc.groups[j + 1].window[0].offset) if j + 1 < len(acc.groups)
                       else mux_csr if mux_csr is not None else set_end)
                csr_mux.o_MAP(shell.i_INPUT(), base=4 * base, size=4 * (end - base))

                units, links = group_units(acc, group)
                comp = SnaxGroup(self, group_names[group.name], units=units, links=links,
                    csr_base=base)
                shell.o_CTRL(comp.i_CTRL())
                comp.o_BUSY(shell.i_BUSY())
                for u in group.units:
                    owner[u.name] = comp

            if acc.port_mux is not None:
                # The beats through the mux: every mover's users to its mover
                mux = SnaxPortMux(self, f'port_mux_{row.name}', csr_base=mux_csr,
                    sel_width=acc.port_mux.csr.width, groups=acc.port_mux.groups,
                    movers=[{'name': m.name, 'is_reader': m.role == 'read',
                             'num_channel': m.num_channel} for m in acc.movers],
                    ports=mux_ports(acc))
                csr_mux.o_MAP(mux.i_INPUT(), base=4 * mux_csr, size=4 * (set_end - mux_csr))
                streamer.o_BUSY(mux.i_BUSY())
                for i, user in enumerate(mux_ports(acc)):
                    unit, port_name = user['name'].split('.', 1)
                    owner[unit].o_PORT(f'{unit}_{port_name}', mux.i_PORT(i))
                readers = [m for m in acc.movers if m.role == 'read']
                for m, mover in enumerate(acc.movers):
                    mux.o_MOVER(m, streamer.i_READER(m) if mover.role == 'read'
                                else streamer.i_WRITER(m - len(readers)))
            else:
                # The beats: the set's readers into its outer inputs, its outer outputs into
                # its writers
                for i, entry in enumerate(acc.inputs):
                    unit, port_name = entry.split('.', 1)
                    owner[unit].o_PORT(f'{unit}_{port_name}', streamer.i_READER(i))
                for j, entry in enumerate(acc.outputs):
                    unit, port_name = entry.split('.', 1)
                    owner[unit].o_PORT(f'{unit}_{port_name}', streamer.i_WRITER(j))

            # Its TCDM ports out as the composite's, after the previous sets'
            channels = streamer_channels(row.template)
            for p in range(channels):
                streamer.o_TCDM(p, self.i_TCDM_INTERNAL(port + p))
                streamer.o_TCDM_PRIORITY(p, self.i_TCDM_PRIORITY_INTERNAL(port + p))
            port += channels

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
