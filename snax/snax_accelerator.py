#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The standard composite of an accelerator slot with an accelerator.json: the
CSR mux, the streamer, and per group one SnaxShell and one SnaxGroup.

    SnaxAccelerator.for_slot(slot, tcdm_size, file) -> class

The slot (snax_cfg.AccSlot) gives the streamer template and the accelerator
(snax_cfg.Accelerator), the cluster its TCDM size. Each entry of the
accelerator's inputs ("<unit>.<port>") takes the streamer's reader of its
index, each entry of its outputs the writer of its index; a port on a link
(snax-forge C§17) is the group's own and meets no streamer.

CSRs: the streamer's from SNAX_CSR_FIRST (nb_csrs of its template); then the
accelerator's, at the offsets accelerator.json gives: each group's window
(START, JOBS, its units' R/W CSRs, STATUS, COUNTER) to its shell. The last
must be at most SNAX_ACC_CSR_LAST.

Names (component_names): with one group of one unit, the shell is `shell` and
the group `unit` (snax_acc<i>/unit, the trace path snax-forge's manifests
name); with several groups of one unit each, `shell_<group>` and
`unit_<unit>`; a linked group (several units) is `group_<group>`, its shell
`shell_<group>`.

Each SnaxGroup gets its units in the group's order (group_units): per unit
its datapath, its inputs in BRM port order (an outer one named
`<unit>_<port>`, a linked one ""), its output (outer, or "" when linked), its
types, timing and t: params.T when the unit has one, 0 for a fold's
JOB_BEATS, else 1; and its links as edges, each {from, to, to_input, depth}:
the producer's and the consumer's names and the consumer's input it feeds,
its index in that unit's inputs.
"""

import gvsoc.systree
import interco.router as router
from snax_cfg import CATALOGUE, DTYPES, CfgTargetError, dirs_of, streamer_channels
from snax_group import SnaxGroup
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
    """Has the build compile SnaxShell and SnaxGroup, as it would for a target whose tree holds
    them: a cluster file with an accelerator runs on the installed components, whatever a
    built target's default file holds. The build path only (gvsoc.systree's registry)."""
    for sources in (SnaxShell.SOURCES, SnaxGroup.SOURCES):
        gvsoc.systree.get_generated_component(list(sources), [], [])


def component_names(accelerator) -> tuple:
    """The shells' and the groups' component names, by group: shell and unit for one group of
    one unit; else shell_<group>, and unit_<unit> for a group of one unit, group_<group> for a
    linked group."""
    groups = accelerator.groups
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
            'output': '' if f'{u.name}.{out}' in frm else f'{u.name}_{out}',
            'lanes': in_ports[0].lanes,
            'in_widths': [p.width for p in in_ports], 'in_signed': [p.signed for p in in_ports],
            'out_width': out_port.width, 'out_signed': out_port.signed,
            'op_width': op_width, 'op_signed': op_signed,
            'op': u.params.get('op', 'add'),
            'accumulate': bool(u.params.get('accumulate', True)),
            'reg_out': bool(u.params.get('regOut', False)),
            'latency': u.latency, 'ii': u.ii, 'span': u.span, 't': t,
        })
    links = []
    for x in group.links:
        src, dst = x.from_.split('.', 1)[0], x.to.split('.', 1)
        links.append({'from': src, 'to': dst[0], 'to_input': ins_of[dst[0]].index(dst[1]),
                      'depth': x.depth})
    return units, links


class SnaxAccelerator(gvsoc.systree.Component):
    """The CSR mux, the streamer, the shells and groups of one slot, bound to a core's
    snax_csr port, its streamer's channels leaving it as its TCDM ports; for_slot gives the
    slot's class.

    Ports
    -----
    input : io slave
        The compute core's CSR accesses, a 32-bit request at 4 * CSR number.
    tcdm_<i> : io master
        The streamer's TCDM ports (nb_tcdm_ports of them).
    tcdm_prio_<i> : wire<bool> master
        The priority bit of each TCDM port's request.
    """

    # Set by for_slot: the streamer template, the accelerator, the TCDM size, and the TCDM
    # ports the cluster binds (snax_tcdm_ports in the hjson), named in the crossbar's trace by
    # their owner
    template = None
    accelerator = None
    tcdm_size = None
    nb_tcdm_ports = 0
    tcdm_port_names = []

    @classmethod
    def for_slot(cls, slot, tcdm_size: int, file='?'):
        """The class of the slot's composite, with the class attributes the cluster reads
        (nb_tcdm_ports, tcdm_port_names)."""
        accelerator = slot.accelerator
        last = SNAX_CSR_FIRST + nb_csrs(slot.streamer) + len(accelerator.csrs) - 1
        if last > SNAX_ACC_CSR_LAST:
            raise CfgTargetError(file, slot.at,
                f"the accelerator's last CSR {last} is past {SNAX_ACC_CSR_LAST}, the last an "
                "accelerator may use")
        return type(f'SnaxAccelerator_{slot.name}', (cls,), {
            'template': slot.streamer,
            'accelerator': accelerator,
            'tcdm_size': tcdm_size,
            'nb_tcdm_ports': streamer_channels(slot.streamer),
            'tcdm_port_names': ['streamer.' + name for name in tcdm_port_names(slot.streamer)],
        })

    def __init__(self, parent: gvsoc.systree.Component, name: str):
        super().__init__(parent, name)

        acc = self.accelerator
        # The accelerator's first CSR, after the streamer's
        first = SNAX_CSR_FIRST + nb_csrs(self.template)
        shell_names, group_names = component_names(acc)

        csr_mux = router.Router(self, 'csr_mux')
        streamer = SnaxStreamer(self, 'streamer', template=self.template,
            csr_base=SNAX_CSR_FIRST, tcdm_size=self.tcdm_size)
        streamer_base = 4 * SNAX_CSR_FIRST
        csr_mux.o_MAP(streamer.i_INPUT(), base=streamer_base, size=4 * first - streamer_base)

        owner = {}
        for k, group in enumerate(acc.groups):
            base = first + group.window[0].offset
            shell = SnaxShell(self, shell_names[group.name], csr_base=base, csrs=group.rw)
            # The group's window; past the last group, everything to the last SNAX CSR,
            # which its shell refuses
            end = (first + acc.groups[k + 1].window[0].offset if k + 1 < len(acc.groups)
                   else SNAX_CSR_LAST + 1)
            csr_mux.o_MAP(shell.i_INPUT(), base=4 * base, size=4 * (end - base))

            units, links = group_units(acc, group)
            comp = SnaxGroup(self, group_names[group.name], units=units, links=links,
                csr_base=base)
            shell.o_CTRL(comp.i_CTRL())
            comp.o_BUSY(shell.i_BUSY())
            for u in group.units:
                owner[u.name] = comp

        # The beats: the readers into the outer inputs, the outer outputs into the writers
        for i, entry in enumerate(acc.inputs):
            unit, port = entry.split('.', 1)
            owner[unit].o_PORT(f'{unit}_{port}', streamer.i_READER(i))
        for j, entry in enumerate(acc.outputs):
            unit, port = entry.split('.', 1)
            owner[unit].o_PORT(f'{unit}_{port}', streamer.i_WRITER(j))

        self.bind_ports(csr_mux, streamer)

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
