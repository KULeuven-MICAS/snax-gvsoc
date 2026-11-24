#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""A group's control rule, snax-forge's, in plain Python: the twin of
snax_group.hpp's SnaxGroupRule, with no GVSoC import, so tests/snax/group/gen.py writes the
group cases from it and snax-forge can import it from the submodule.

    GroupRule(units, links, output=None, forks=(), fork_links=()).run(jobs, job_beats, valid,
        ready, cycles) -> (rows, end)

A unit is a dict: ``name``, ``L`` (latency), ``ii``, ``span`` (the cycles it reads one beat in
place), ``inputs`` (its count of outer inputs, from the streamer) and ``seed`` (optional, false
by default: its last outer input is a fold's or a Mac's seed, one beat per job). A broadcast
input is wires between its slicer or reader and the lanes: the rule does not see it. A link is an edge
``{"from", "to", "to_input", "depth"}``: the producer's and the consumer's names, the
consumer's input it drives (the datapaths use it, the rule does not), and its depth D (0 a
wire, >= 1 a buffer of D beats). ``output`` names the unit that owns the group's outer output;
by default the sink, the unit without an out-edge.

Each cycle has two passes over the units in a topological order:

- forward, what each unit offers whatever its room: unit k's input has a beat (avail_k) when
  its outer inputs all have one (a seeded unit's seed only on its job's first beat, d = 0:
  fire = a.valid and (not first or seed.valid); the seed is taken with that firing,
  seed.ready = fire and first) and every in-edge offers one, a wire what its producer offers
  this cycle (its pipeline's head, or with L = 0 a firing that gives), a buffer its oldest beat
  (occupancy > 0);
- backward, in reverse order, whether each unit has room (room_k): the outer output's ready for
  the unit owning it, and every out-edge takes, a wire when its consumer fires, a buffer when
  occupancy < D or its consumer fires; a unit whose head (or with L = 0 a giving firing) has no
  room is frozen. A unit not frozen reads its input when it wants to and its input has a beat,
  at every span: lane l in place at span S, firing on lane S - 1; at span 1 the read is its
  firing.

Unit k fires n_k times per run: JOBS * T for the sink, n_succ * T_k for a unit before it (each
firing of its consumer takes one of its results, one per T_k firings). The cycle's class is
judged at the units owning the outer outputs: stall_out (one is frozen) > busy (any unit fires,
reads or is in its II gap) > stall_in (a unit with outer inputs wants to fire and one has no
beat) > flush.

A group is one or more chains: each a path of units joined by links, from a head to a
sink that owns one outer output; a unit with two out-edges (a fork) or two in-edges (a join)
or a cycle is refused (GroupError), as snax_cfg.py's ``gen.chain``. Chains meet only at a
fork of an outer input, ``forks``: lists of ``(unit, j)``, unit's j-th outer input, each a
head's and none a seed or of a unit of span > 1. One reader gives such an input to every
member: in valid(c) it appears once, at its first member's place, and its beat is taken only
when every member fires, so a member that would fire waits while another cannot. Several
chains take ``jobs``, ``ready`` and ``d_out`` per output, in ``outputs``' order (the sinks in
unit order unless ``output`` lists them); a unit fires JOBS of its own chain times the T
over itself and the units after it. The cycle is stall_out when any output's unit is frozen;
the run ends when every chain has.

A banked unit has ``rows`` R (``ROWS``, default 1): its sums are R rows, one a firing
in turn, so a job of T firings (T a multiple of R) starts each row on its first R firings
(``first``, a seed taken on each) and gives R results, one on each of its last R firings (a
row is done when the job's last pass adds into it). It is a chain's sink. Its ``hold``
(optional, outer input places among its own) are read once every R firings and kept:
such an input needs its beat only on the firings where fired mod R = 0, and its reader's beat
(a slicer's slice) is taken there. A link with ``hold`` into a banked unit is held the same way:
its beat is needed and taken on those firings only, so the consumer takes one result of its
producer every R firings (n_producer = n_consumer / R * T_producer); its depth is 1 or more.

A fork may also give its beat to a unit further down a chain through a buffer, ``fork_links``:
``{"fork", "to", "to_input", "depth"}``, the fork's index in ``forks``, the consumer (after
every member of the fork in the order) and its input, and the buffer's depth D >= 1. The fork's
beat is taken when every member fires and every such buffer has room (occupancy < D, or its
consumer fires); the consumer's input has a beat when its buffer holds one, popped on each of
its firings. A buffer shallower than the beats the consumer waits through never ends the run
(LOWER refuses it).

With ``d_out`` above 1 the outer output goes through a packer (snax_group.hpp's
SnaxPacker): the owning unit's outer room is ``ready`` only on a push that sends the word (its
slice is d_out - 1, or the push is the run's last result, from the count of pushes), true on a
push the packer keeps; ``sent`` lists, per cycle, whether a word went to the writer.

With ``d_in`` above 1 on an outer input, a slicer (snax_group.hpp's SnaxSlicer) sits
between its reader and the unit: the rule sees its held word (``full``), not the reader's
valid; a firing (a seed's take) pops a slice, the d_in-th clears ``full``; it takes the
reader's word when empty or on that last pop, only in busy cycles, so the word shows the
cycle after. ``took`` lists, per cycle, whether each sliced input took a word.
"""


class GroupError(ValueError):
    """A group the rule does not run (see the module doc)."""


class GroupRule:
    """The control rule over edges: per unit its firings (its job_beats_counter their remainder
    mod T), its L-deep pipeline, its II gap and lane counter; per buffer its occupancy."""

    def __init__(self, units, links, output=None, forks=(), fork_links=()):
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
                    raise GroupError(f"unit {u['name']} has {len(edges)} {what}: a chain has "
                                     "neither")
        self.order = self._topological()
        sinks = [k for k in range(n) if not self.outs[k]]
        names = [output] if isinstance(output, str) else output
        self.outputs = sinks if names is None else [index[x] for x in names]
        self.output = self.outputs[0]
        # each unit's chain: the output its path of links ends at
        self.chain = [None] * n
        for o, k in enumerate(sinks):
            while True:
                self.chain[k] = o
                if not self.ins[k]:
                    break
                k = self.links[self.ins[k][0]]["src"]
        if names is not None and sorted(self.outputs) != sinks:
            raise GroupError(f"outputs {list(names)}: each chain's sink owns one, "
                             + ", ".join(units[k]["name"] for k in sinks))
        self.chain = [self.outputs.index(sinks[o]) for o in self.chain]
        self.forks = [[(index[u], j) for u, j in f] for f in forks]
        self.fork_links = []
        for e in fork_links:
            if e["to"] not in index or not 0 <= e["fork"] < len(self.forks):
                raise GroupError(f"fork link {e}: no unit {e['to']} or no fork {e['fork']}")
            self.fork_links.append(dict(e, dst=index[e["to"]]))
        self._check_forks()
        self._check_fork_links()
        self._check_banks()
        if len(sinks) > 1:
            joined = list(range(len(sinks)))

            def root(o):
                while joined[o] != o:
                    o = joined[o]
                return o

            for f in self.forks:
                for k, _ in f[1:]:
                    joined[root(self.chain[k])] = root(self.chain[f[0][0]])
            parts = {}
            for o, k in enumerate(sinks):
                parts.setdefault(root(o), []).append(units[k]["name"])
            if len(parts) > 1:
                raise GroupError("the chains ending at " + " and at ".join(
                    ", ".join(p) for p in parts.values()) + ": no fork joins them; a group's "
                    "chains share an input")
        # each unit's outer inputs as places in valid(c): a forked input at its first member's
        self.place, at, first = [], 0, {}
        for k, u in enumerate(units):
            mine = []
            for j in range(u["inputs"]):
                f = next((f for f in self.forks if (k, j) in f), None)
                if f is not None and f[0] != (k, j):
                    mine.append(first[f[0]])
                    continue
                if f is not None:
                    first[f[0]] = at
                mine.append(at)
                at += 1
            self.place.append(mine)
        self.n_valid = at

    def _check_forks(self):
        """Each fork: two or more members (its buffered links count), each a head's outer
        input, not a seed, of span 1, each input in one fork."""
        seen = set()
        for i, f in enumerate(self.forks):
            what = "fork " + ", ".join(f"{self.units[k]['name']}.{j}" for k, j in f)
            buffered = sum(1 for e in self.fork_links if e["fork"] == i)
            if len(f) + buffered < 2 or not f or len({k for k, _ in f}) < len(f):
                raise GroupError(f"{what}: a fork gives one input to two or more units")
            for k, j in f:
                u = self.units[k]
                if (k, j) in seen:
                    raise GroupError(f"{what}: {u['name']}.{j} is in another fork too")
                seen.add((k, j))
                if not 0 <= j < u["inputs"] or (u.get("seed") and j == u["inputs"] - 1):
                    raise GroupError(f"{what}: {u['name']} has no outer input {j} that is not "
                                     "its seed")
                if self.ins[k]:
                    raise GroupError(f"{what}: {u['name']} is fed by a link; a fork feeds "
                                     "chains' heads")
                if u["span"] != 1:
                    raise GroupError(f"{what}: {u['name']} has span {u['span']}; a forked "
                                     "input's units read it at span 1")

    def _check_fork_links(self):
        """Each buffered branch of a fork: a buffer of depth 1 or more into a unit after every
        member of its fork in the order (so the backward pass knows its firing), not a member."""
        pos = {k: i for i, k in enumerate(self.order)}
        for e in self.fork_links:
            members = [k for k, _ in self.forks[e["fork"]]]
            what = f"fork link to {e['to']}"
            if not isinstance(e["depth"], int) or e["depth"] < 1:
                raise GroupError(f"{what}: depth {e['depth']!r}; a fork's branch to a unit down "
                                 "a chain is a buffer of depth 1 or more")
            if e["dst"] in members or any(pos[e["dst"]] <= pos[k] for k in members):
                raise GroupError(f"{what}: it is not after the fork's units in the chain")

    def _check_banks(self):
        """A banked unit (rows > 1) is a sink; its held inputs are outer inputs, not its seed,
        not forked."""
        forked = {x for f in self.forks for x in f}
        for k, u in enumerate(self.units):
            rows, hold = u.get("rows", 1), list(u.get("hold", ()))
            if not isinstance(rows, int) or rows < 1:
                raise GroupError(f"unit {u['name']}: rows {rows!r}; a bank has one row or more")
            if rows > 1 and self.outs[k]:
                raise GroupError(f"unit {u['name']}: a bank of {rows} rows gives {rows} results a "
                                 "job; it is a chain's sink, not linked on")
            for i in self.ins[k]:
                e = self.links[i]
                if e.get("hold") and (rows == 1 or e["depth"] < 1):
                    raise GroupError(f"link {e['from']} -> {u['name']}: held, but {u['name']} "
                                     f"has {rows} row(s) and the link depth {e['depth']}; a held "
                                     "link is a buffer into a bank")
            for j in hold:
                if rows == 1:
                    raise GroupError(f"unit {u['name']}: input {j} held, but it has no bank; a "
                                     "hold counts the bank's rows")
                if not 0 <= j < u["inputs"] - (1 if u.get("seed") else 0) or (k, j) in forked:
                    raise GroupError(f"unit {u['name']}: input {j} held is not an outer input "
                                     "of its own (not its seed, not forked)")

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

    def _per_output(self, x, what):
        """``x`` per output: a list as given, a scalar for one output."""
        if isinstance(x, (list, tuple)):
            if len(x) != len(self.outputs):
                raise GroupError(f"{what} {list(x)}: one per output, {len(self.outputs)}")
            return list(x)
        if len(self.outputs) > 1:
            raise GroupError(f"{what} {x}: a group of {len(self.outputs)} chains takes one per "
                             "output")
        return [x]

    def firings_per_run(self, jobs, job_beats):
        """Each unit's firings n_k in a run of ``jobs`` (per output with several chains), unit
        k a result every job_beats[k] firings."""
        jobs = self._per_output(jobs, "jobs")
        n = [0] * len(self.units)
        for k in reversed(self.order):
            if not self.outs[k]:
                n[k] = jobs[self.chain[k]] * job_beats[k]
                continue
            e = self.links[self.outs[k][0]]
            per = self.units[e["dst"]].get("rows", 1) if e.get("hold") else 1
            n[k] = n[e["dst"]] // per * job_beats[k]  # a held link: one result a bank row
        return n

    def run(self, jobs, job_beats, valid, ready, cycles, d_out=1, d_in=()):
        """Steps a run started in cycle 0 for ``cycles`` cycles: valid(c) the outer inputs'
        valids (a unit with outer inputs has its beat when all are 1), ready(c) the outer
        outputs' (a scalar for one output), ``d_out`` a scalar for all or one per output;
        valid(c) gives every unit's outer inputs in unit
        and port order, a seeded unit's seed last among its own, a forked input once, a sliced
        input's its reader's. ``d_in`` the outer inputs' pops per word in that order (missing:
        1). Rows of (valids, ready, per unit (fire, give), per link its occupancy, busy,
        class, notes) and the run's last cycle E (None when it does not end); ``sent`` per
        cycle per output whether a word went to its writer, ``took`` per sliced input."""
        n, links, outs = len(self.units), self.links, self.outputs
        jobs_o = self._per_output(jobs, "jobs")
        d_out = (self._per_output(d_out, "d_out") if isinstance(d_out, (list, tuple))
                 else [d_out] * len(outs))
        firings_per_run = self.firings_per_run(jobs_o, job_beats)
        fired, lane = [0] * n, [0] * n
        slots = [[False] * u["L"] for u in self.units]
        last = [None] * n
        occ = [0] * len(links)
        focc = [0] * len(self.fork_links)
        rows, end = [], None
        empty = 0 in jobs_o or 0 in job_beats
        for k, u in enumerate(self.units):
            if job_beats[k] % u.get("rows", 1):
                raise GroupError(f"unit {u['name']}: T {job_beats[k]} is not a multiple of its "
                                 f"{u['rows']} rows")
        results = [0 if empty else firings_per_run[k] // job_beats[k] * self.units[k].get("rows", 1)
                   for k in outs]  # fmt: skip
        pushes, slice_ = [0] * len(outs), [0] * len(outs)
        self.sent = []
        # each place in valid(c): its first unit and whether it is that unit's seed
        port = [None] * self.n_valid
        for k, u in enumerate(self.units):
            for j, i in enumerate(self.place[k]):
                if port[i] is None:
                    port[i] = (k, "seed" if u.get("seed") and j == u["inputs"] - 1 else
                               "hold" if j in u.get("hold", ()) else None)  # fmt: skip
        sliced = {i: d for i, d in enumerate(d_in) if d > 1}
        full, count = dict.fromkeys(sliced, False), dict.fromkeys(sliced, 0)
        self.took = []
        for c in range(cycles):
            v, r = valid(c), ready(c)
            r_o = self._per_output(r, "ready")
            busy = c >= 1 and not empty and (end is None or c <= end)
            if not busy:
                rows.append((v, r, [(0, 0)] * n, list(occ) + list(focc), 0, "-", "idle"))
                self.sent.append([0] * len(outs))
                self.took.append([0] * len(sliced))
                continue
            sending = [slice_[o] == d_out[o] - 1 or pushes[o] + 1 == results[o]
                       for o in range(len(outs))]
            seen = [int(full[i]) if i in sliced else x for i, x in enumerate(v)]
            ins, seeds = [], []
            for k, (u, places) in enumerate(zip(self.units, self.place)):
                mine = [seen[i] for i in places]
                seeds.append(mine.pop() if u.get("seed") else 1)
                taking = fired[k] % u.get("rows", 1) == 0  # NB (D190): a held input's beat
                ins.append(all(x for j, x in enumerate(mine)
                               if j not in u.get("hold", ()) or taking))  # fmt: skip
            for k, u in enumerate(self.units):  # a job's first beats (a row's each) wait for
                first = fired[k] % job_beats[k] < u.get("rows", 1)  # their seed
                ins[k] = ins[k] and (not u.get("seed") or not first or bool(seeds[k]))
            # NB (D189): a forked input's members fire together; one that would fire waits
            # while another cannot, so the cycle is decided again with it blocked
            blocked = set()
            while True:
                step = self._decide(c, ins, blocked, fired, lane, slots, last, occ,
                                    firings_per_run, job_beats, r_o, sending, focc)
                held = {k for f in self.forks if not all(step["fire"][k] for k, _ in f)
                        for k, _ in f if step["fire"][k]}
                # a fork with a buffered branch takes a beat only when the buffer has room
                for i, e in enumerate(self.fork_links):
                    f = self.forks[e["fork"]]
                    full = focc[i] >= e["depth"] and not step["fire"][e["dst"]]
                    if full and any(step["fire"][k] for k, _ in f):
                        held |= {k for k, _ in f}
                if not held:
                    break
                blocked |= held
            out, notes = [None] * n, list(step["notes"])
            for k in reversed(self.order):
                u = self.units[k]
                fire, push, read = step["fire"][k], step["push"][k], step["read"][k]
                if not step["frozen"][k] and u["L"] > 0:
                    slots[k] = [step["gives"][k] and fire] + slots[k][:-1]
                if fire:
                    fired[k] += 1
                    last[k] = c
                    lane[k] = 0
                elif read:
                    lane[k] += 1
                out[k] = (int(fire), int(push))
                if push and k in outs:
                    o = outs.index(k)
                    pushes[o] += 1
                    slice_[o] = 0 if sending[o] else slice_[o] + 1
            fires, seeded, takes = step["fire"], step["seeded"], step["takes"]
            # NB (D180): a slicer pops on its unit's firing (a seed's on its take); it takes the
            # reader's word when empty or on its last pop, so the word shows the next cycle
            took = []
            for i, d in sliced.items():
                k, kind = port[i]
                pop = {"seed": seeded, "hold": takes}.get(kind, fires)[k]
                last_pop = pop and count[i] == d - 1
                take = bool(v[i]) and (not full[i] or last_pop)
                if last_pop:
                    full[i] = False
                elif pop:
                    count[i] += 1
                if take:
                    full[i], count[i] = True, 0
                    notes.append(f"input {i} takes a word")
                took.append(int(take))
            self.took.append(took)
            for i, e in enumerate(links):
                if e["depth"]:
                    taken = step["takes"][e["dst"]] if e.get("hold") else out[e["dst"]][0]
                    occ[i] += out[e["src"]][1] - int(taken)
            for i, e in enumerate(self.fork_links):
                head = self.forks[e["fork"]][0][0]
                focc[i] += int(step["fire"][head]) - int(step["fire"][e["dst"]])
            cls = ("stall_out" if any(step["frozen"][k] for k in outs) else
                   "busy" if step["busy"] else "stall_in" if step["waits"] else "flush")
            done = (all(fired[k] == firings_per_run[k] and not any(slots[k]) for k in range(n))
                    and not any(occ) and not any(focc))
            if done:
                end = c
            self.sent.append([int(out[k][1] and sending[o]) for o, k in enumerate(outs)])
            rows.append((v, r, out, list(occ) + list(focc), 1, cls,
                         "; ".join(reversed(notes)) or cls))
        return rows, end

    def _decide(self, c, ins, blocked, fired, lane, slots, last, occ, firings_per_run,
                job_beats, ready, sending, focc=()):
        """One cycle's choices, changing no state: the forward pass (what each unit offers)
        and the backward pass (room, frozen, fire, push, read), the units in ``blocked`` not
        firing."""
        n, links, outs = len(self.units), self.links, self.outputs
        avail, wants, wfire, gives, head, offer = ([None] * n for _ in range(6))
        for k in self.order:
            u = self.units[k]
            taking = fired[k] % u.get("rows", 1) == 0
            avail[k] = (ins[k]
                        and all(offer[links[i]["src"]] if links[i]["depth"] == 0
                                else occ[i] > 0 or (links[i].get("hold") and not taking)
                                for i in self.ins[k])
                        and all(focc[i] > 0 for i, e in enumerate(self.fork_links)
                                if e["dst"] == k))  # fmt: skip
            ii_ok = last[k] is None or c >= last[k] + u["ii"]
            wants[k] = fired[k] < firings_per_run[k] and ii_ok and k not in blocked
            wfire[k] = wants[k] and avail[k] and (u["span"] == 1 or lane[k] == u["span"] - 1)
            rows = u.get("rows", 1)  # NB (D191): a bank gives on a job's last ROWS firings
            gives[k] = wfire[k] and fired[k] % job_beats[k] >= job_beats[k] - rows
            head[k] = u["L"] > 0 and slots[k][-1]
            offer[k] = head[k] if u["L"] > 0 else gives[k]
        notes = []
        busy_cls = waits = False
        frozen, fires, seeded, takes = [False] * n, [False] * n, [False] * n, [False] * n
        pushes, reads = [False] * n, [False] * n
        for k in reversed(self.order):
            u = self.units[k]
            mine = ready[outs.index(k)] or not sending[outs.index(k)] if k in outs else True
            room = mine and all(
                fires[links[i]["dst"]] if links[i]["depth"] == 0
                else occ[i] < links[i]["depth"]
                or (takes[links[i]["dst"]] if links[i].get("hold") else fires[links[i]["dst"]])
                for i in self.outs[k])
            frozen[k] = (head[k] if u["L"] > 0 else gives[k]) and not room
            fire = push = read = False
            if not frozen[k]:
                fire = wfire[k]
                push = head[k] if u["L"] > 0 else gives[k]
                read = wants[k] and avail[k]
                gap = last[k] is not None and c < last[k] + u["ii"]
                busy_cls = busy_cls or fire or read or gap
                waits = waits or (wants[k] and not ins[k])
            else:
                notes.append(f"{u['name']} holds")
            if k in blocked and fired[k] < firings_per_run[k] and ins[k]:
                notes.append(f"{u['name']} waits for its fork")
            if read and not fire:
                notes.append(f"{u['name']} reads lane {lane[k]}")
            if fire:
                seed = u.get("seed") and fired[k] % job_beats[k] < u.get("rows", 1)
                held = bool(u.get("hold")) or any(links[i].get("hold") for i in self.ins[k])
                takes[k] = held and fired[k] % u.get("rows", 1) == 0
                notes.append(f"{u['name']} fires {fired[k]}" + (" (gives)" if gives[k] else "")
                             + (f", lane {lane[k]}" if u["span"] > 1 else "")
                             + (", takes its seed" if seed else ""))
                seeded[k] = bool(seed)
            if push:
                notes.append(f"{u['name']} pushes")
            fires[k], pushes[k], reads[k] = fire, push, read
        return {"fire": fires, "push": pushes, "read": reads, "frozen": frozen, "gives": gives,
                "seeded": seeded, "takes": takes, "notes": notes, "busy": busy_cls, "waits": waits}
