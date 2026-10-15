#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The SNAX accelerators' ports into the TCDM banks (snax_tcdm_xbar.cpp)."""

import gvsoc.systree


class SnaxTcdmXbar(gvsoc.systree.Component):
    """Per-bank arbitration of the SNAX TCDM ports.

    As one of snax_cluster's interconnects: plain (sparse_interconnect false),
    one rr_arb_tree per bank; or sparse (sparse_interconnect true), per bank
    the highest priority first, then round robin from the last pick
    (snax_sparse_arb.hpp). One grant per bank and cycle, read data one cycle
    after the grant. A request that loses is dropped and sent again by its
    master the next cycle.

    Parameters
    ----------
    nb_inputs : int
        SNAX TCDM ports, numbered as on the RTL (at most 64).
    nb_banks : int
        TCDM banks, a power of two.
    bank_width : int
        Bytes per bank word, a power of two; every request is one word.
    input_names : list[str]
        The owner of each input, for the trace; in_<i> when not given.
    interconnect : str
        'plain' or 'sparse'.
    sparse_config : list[list[int]]
        Sparse only: the ports in input order, [width, granularity] each, as
        snaxgen builds the module's sparse_config; the widths add up to
        nb_inputs.

    Ports
    -----
    in_<i> : io slave
        SNAX port i, TCDM offsets.
    out_<b> : io master
        Bank b, bank-local offsets.
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str, nb_inputs: int,
            nb_banks: int, bank_width: int, input_names: list[str] | None = None,
            interconnect: str = 'plain', sparse_config: list[list[int]] | None = None):
        super().__init__(parent, name)

        if interconnect not in ('plain', 'sparse'):
            raise RuntimeError(f'Interconnect not modelled: {interconnect}')
        if interconnect == 'sparse':
            if sparse_config is None or sum(width for width, _ in sparse_config) != nb_inputs:
                raise RuntimeError(f'sparse_config {sparse_config} does not cover the '
                    f'{nb_inputs} inputs')

        self.add_sources(['snax_tcdm_xbar.cpp'])

        self.add_properties({
            'nb_inputs': nb_inputs,
            'nb_banks': nb_banks,
            'bank_width': bank_width,
            'input_names': list(input_names) if input_names is not None
                else [f'in_{i}' for i in range(0, nb_inputs)],
            'interconnect': interconnect,
            'sparse_config': [list(port) for port in sparse_config or []],
        })

    def i_INPUT(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'in_{port}', signature='io')

    def o_BANK(self, bank: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'out_{bank}', itf, signature='io')
