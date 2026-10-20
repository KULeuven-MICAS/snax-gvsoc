#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""The SNAX crossbar: the accelerators', cores', AXI's and the DMA's ports into the
TCDM banks (snax_tcdm_xbar.cpp)."""

import gvsoc.systree


class SnaxTcdmXbar(gvsoc.systree.Component):
    """Per-bank arbitration of the TCDM ports of a SNAX cluster.

    As one of snax_cluster's interconnects: plain (sparse_interconnect false),
    one rr_arb_tree per bank (snax_plain_arb.hpp); or sparse (sparse_interconnect true), per bank
    the highest priority first, then round robin from the last pick
    (snax_sparse_arb.hpp). One grant per bank and cycle, read data one cycle
    after the grant. A request that loses is dropped and sent again by its
    master the next cycle, or, on an input that holds, kept for the next
    cycle's arbitration. The DMA's beat takes every bank of its superbank in its
    cycle, and a narrow winner there is refused and locked in (docs/plans/SG7.md).

    Parameters
    ----------
    nb_inputs : int
        TCDM ports, numbered as on the RTL: the SNAX ports, the cores, AXI (at
        most 64).
    nb_banks : int
        TCDM banks, a power of two.
    bank_width : int
        Bytes per bank word, a power of two; a request is 1, 2, 4 or 8 bytes
        inside one word.
    input_names : list[str]
        The owner of each input, for the trace; in_<i> when not given.
    holds : list[bool]
        Per input, whether it holds a losing request (cores, AXI) rather than
        resend it (SNAX ports); False when not given.
    interconnect : str
        'plain' or 'sparse'.
    sparse_config : list[list[int]]
        Sparse only: the ports in input order, [width, granularity] each, as
        snaxgen builds the module's sparse_config; the widths add up to
        nb_inputs.
    superbank_banks : int
        Banks per DMA beat (the hjson's dma_data_width / data_width), dividing
        nb_banks; 0 for no dma port.

    Ports
    -----
    in_<i> : io slave
        Input i, TCDM offsets.
    prio_<i> : wire<bool> slave
        The priority bit of the request input i sends next in the cycle; 0 for
        an input whose wire is not set. Sparse only.
    out_<b> : io master
        Bank b, bank-local offsets.
    dma : io slave
        The DMA, TCDM offsets: one beat per request, inside one aligned line
        of superbank_banks * bank_width bytes. Only with superbank_banks.
    """

    def __init__(self, parent: gvsoc.systree.Component, name: str, nb_inputs: int,
            nb_banks: int, bank_width: int, input_names: list[str] | None = None,
            holds: list[bool] | None = None, interconnect: str = 'plain',
            sparse_config: list[list[int]] | None = None, superbank_banks: int = 0):
        super().__init__(parent, name)

        if interconnect not in ('plain', 'sparse'):
            raise RuntimeError(f'Interconnect not modelled: {interconnect}')
        if interconnect == 'sparse':
            if sparse_config is None or sum(width for width, _ in sparse_config) != nb_inputs:
                raise RuntimeError(f'sparse_config {sparse_config} does not cover the '
                    f'{nb_inputs} inputs')

        if superbank_banks < 0 or (superbank_banks and nb_banks % superbank_banks):
            raise RuntimeError(f'superbank_banks {superbank_banks} does not divide the '
                f'{nb_banks} banks')
        if holds is not None and len(holds) != nb_inputs:
            raise RuntimeError(f'holds has {len(holds)} inputs, the crossbar {nb_inputs}')

        self.add_sources(['snax_tcdm_xbar.cpp'])

        self.add_properties({
            'nb_inputs': nb_inputs,
            'nb_banks': nb_banks,
            'bank_width': bank_width,
            'input_names': list(input_names) if input_names is not None
                else [f'in_{i}' for i in range(0, nb_inputs)],
            'holds': [bool(hold) for hold in holds or []],
            'interconnect': interconnect,
            'sparse_config': [list(port) for port in sparse_config or []],
            'superbank_banks': superbank_banks,
        })

    def i_INPUT(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'in_{port}', signature='io')

    def i_PRIORITY(self, port: int) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, f'prio_{port}', signature='wire<bool>')

    def i_DMA(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'dma', signature='io')

    def o_BANK(self, bank: int, itf: gvsoc.systree.SlaveItf):
        self.itf_bind(f'out_{bank}', itf, signature='io')
