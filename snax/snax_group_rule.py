#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A group's control rule, snax-forge's C§17 (Control), in plain Python: the twin of
snax_group.hpp's SnaxGroupRule, with no GVSoC import, so tests/snax/group/gen.py writes the
group cases from it and snax-forge can import it from the submodule.

    GroupRule(units, links, output=None).run(jobs, ts, valid, ready, cycles) -> (rows, end)

A unit is a dict: ``name``, ``L`` (latency), ``ii``, ``span`` (the cycles it reads one beat in
place) and ``inputs`` (its count of outer inputs, from the streamer). A link is an edge
``{"from", "to", "to_input", "depth"}``: the producer's and the consumer's names, the
consumer's input it drives (the datapaths use it, the rule does not), and its depth D (0 a
wire, >= 1 a buffer of D beats). ``output`` names the unit that owns the group's outer output;
by default the sink, the unit without an out-edge.

Each cycle has two passes over the units in a topological order:

- forward, what each unit offers whatever its room: unit k's input has a beat (avail_k) when
  its outer inputs all have one and every in-edge offers one, a wire what its producer offers
  this cycle (its pipeline's head, or with L = 0 a firing that gives), a buffer its oldest beat
  (occupancy > 0);
- backward, in reverse order, whether each unit has room (room_k): the outer output's ready for
  the unit owning it, and every out-edge takes, a wire when its consumer fires, a buffer when
  occupancy < D or its consumer fires; a unit whose head (or with L = 0 a giving firing) has no
  room is frozen.

Unit k fires n_k times per run: JOBS * T for the sink, n_succ * T_k for a unit before it (each
firing of its consumer takes one of its results, one per T_k firings). The cycle's class is
judged at the unit owning the outer output: stall_out (it is frozen) > busy (any unit fires,
reads or is in its II gap) > stall_in (a unit with outer inputs wants to fire and one has no
beat) > flush.

Until tier A a group is one chain: a unit with two out-edges (a fork) or two in-edges (a join),
a cycle, or units no link joins are refused (GroupError), as snax_cfg.py's ``gen.chain``.
"""


class GroupError(ValueError):
    """A group the rule does not run (see the module doc)."""


class GroupRule:
    """C§17's Control over edges: per unit its beat digit, its L-deep pipeline, its II gap and
    lane counter; per buffer its occupancy."""

    def __init__(self, units, links, output=None):
        self.units = units
        index = {u["name"]: k for k, u in enumerate(units)}
        if len(index) != len(units):
            raise GroupError("two units share a name")
        self.links = []
        for e in links:
            for end in ("from", "to"):
                if e[end] not in index:
                    raise GroupError(f"link {e['from']} -> {e['to']}: no unit {e[end]}")
            self.links.append(dict(e, src=index[e["from"]], dst=index[e["to"]]))
        n = len(units)
        self.ins = [[i for i, e in enumerate(self.links) if e["dst"] == k] for k in range(n)]
        self.outs = [[i for i, e in enumerate(self.links) if e["src"] == k] for k in range(n)]
        for k, u in enumerate(units):
            for edges, what in ((self.outs[k], "out-edges (a fork)"),
                                (self.ins[k], "in-edges (a join)")):
                if len(edges) > 1:
                    raise GroupError(f"unit {u['name']} has {len(edges)} {what}: until tier A "
                                     "a group is a chain")
        self.order = self._topological()
        sinks = [k for k in range(n) if not self.outs[k]]
        if len(sinks) != 1:
            raise GroupError("units " + ", ".join(units[k]["name"] for k in sinks)
                             + " have no out-edge: until tier A a group is one chain")
        self.output = sinks[0] if output is None else index[output]

    def _topological(self):
        """The units in a topological order, each before its consumers (index order among
        those ready)."""
        need = [len(i) for i in self.ins]
        order, ready = [], [k for k, x in enumerate(need) if x == 0]
        while ready:
            k = ready.pop(0)
            order.append(k)
            for i in self.outs[k]:
                d = self.links[i]["dst"]
                need[d] -= 1
                if need[d] == 0:
                    ready.append(d)
        if len(order) != len(self.units):
            raise GroupError("the links form a cycle")
        return order

    def firings_per_run(self, jobs, ts):
        """Each unit's firings n_k in a run of ``jobs``, unit k a result every ts[k] firings."""
        counts = [0] * len(self.units)
        for k in reversed(self.order):
            succ = [self.links[i]["dst"] for i in self.outs[k]]
            counts[k] = (jobs if not succ else counts[succ[0]]) * ts[k]
        return counts

    def run(self, jobs, ts, valid, ready, cycles):
        """Steps a run started in cycle 0 for ``cycles`` cycles: valid(c) the outer inputs'
        valids (a unit with outer inputs has its beat when all are 1), ready(c) the outer
        output's. Rows of (valids, ready, per unit (fire, give), per link its occupancy, busy,
        class, notes) and the run's last cycle E (None when it does not end)."""
        n, links = len(self.units), self.links
        counts = self.firings_per_run(jobs, ts)
        fired, lane = [0] * n, [0] * n
        slots = [[False] * u["L"] for u in self.units]
        last = [None] * n
        occ = [0] * len(links)
        rows, end = [], None
        empty = jobs == 0 or 0 in ts
        for c in range(cycles):
            v, r = valid(c), ready(c)
            busy = c >= 1 and not empty and (end is None or c <= end)
            if not busy:
                rows.append((v, r, [(0, 0)] * n, list(occ), 0, "-", "idle"))
                continue
            ins = [all(v) if u["inputs"] else True for u in self.units]
            avail, wants, wfire, gives, head, offer = ([None] * n for _ in range(6))
            for k in self.order:
                u = self.units[k]
                avail[k] = ins[k] and all(offer[links[i]["src"]] if links[i]["depth"] == 0
                                          else occ[i] > 0 for i in self.ins[k])
                ii_ok = last[k] is None or c >= last[k] + u["ii"]
                wants[k] = fired[k] < counts[k] and ii_ok
                wfire[k] = wants[k] and avail[k] and (u["span"] == 1 or lane[k] == u["span"] - 1)
                gives[k] = wfire[k] and (fired[k] + 1) % ts[k] == 0
                head[k] = u["L"] > 0 and slots[k][-1]
                offer[k] = head[k] if u["L"] > 0 else gives[k]
            out, notes = [None] * n, []
            busy_cls = waits = False
            frozen, fires = [False] * n, [False] * n
            for k in reversed(self.order):
                u = self.units[k]
                room = (r if k == self.output else True) and all(
                    fires[links[i]["dst"]] if links[i]["depth"] == 0
                    else occ[i] < links[i]["depth"] or fires[links[i]["dst"]]
                    for i in self.outs[k])
                frozen[k] = (head[k] if u["L"] > 0 else gives[k]) and not room
                fire = push = read = False
                if not frozen[k]:
                    fire = wfire[k]
                    push = head[k] if u["L"] > 0 else gives[k]
                    read = u["span"] > 1 and wants[k] and avail[k]
                    if u["L"] > 0:
                        slots[k] = [gives[k] and fire] + slots[k][:-1]
                    gap = last[k] is not None and c < last[k] + u["ii"]
                    busy_cls = busy_cls or fire or read or gap
                    waits = waits or (wants[k] and not ins[k])
                else:
                    notes.append(f"{u['name']} holds")
                if read and not fire:
                    notes.append(f"{u['name']} reads lane {lane[k]}")
                if fire:
                    notes.append(f"{u['name']} fires {fired[k]}" + (" (gives)" if gives[k] else "")
                                 + (f", lane {lane[k]}" if u["span"] > 1 else ""))
                    fired[k] += 1
                    last[k] = c
                    lane[k] = 0
                elif read:
                    lane[k] += 1
                if push:
                    notes.append(f"{u['name']} pushes")
                fires[k] = fire
                out[k] = (int(fire), int(push))
            for i, e in enumerate(links):
                if e["depth"]:
                    occ[i] += out[e["src"]][1] - out[e["dst"]][0]
            cls = ("stall_out" if frozen[self.output] else "busy" if busy_cls else
                   "stall_in" if waits else "flush")
            done = (all(fired[k] == counts[k] and not any(slots[k]) for k in range(n))
                    and not any(occ))
            if done:
                end = c
            rows.append((v, r, out, list(occ), 1, cls, "; ".join(reversed(notes)) or cls))
        return rows, end
