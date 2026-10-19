#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""data.h of forge-reduce: DATA_LEN, A and OUT, the sum of every RATE
consecutive elements of A.

A is int64 in [-1000, 1000), as snax-forge's vsum.py makes it, drawn with
NumPy's default_rng(seed); OUT has DATA_LEN / RATE sums. Printed to stdout:

    python3 datagen.py --length=64 --rate=64 --seed=0 > data.h

with data_utils (sw/util) on PYTHONPATH.
"""

import argparse
import sys

import numpy as np
from data_utils import format_scalar_definition, format_vector_definition


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--length', type=int, required=True, help='elements of A')
    p.add_argument('--rate', type=int, required=True, help='elements per sum')
    p.add_argument('--seed', type=int, default=0, help='NumPy seed (default 0)')
    args = p.parse_args()
    if args.length < 1 or args.rate < 1 or args.length % args.rate:
        p.error(f'length {args.length} is not a positive multiple of rate {args.rate}')

    a = np.random.default_rng(args.seed).integers(-1000, 1000, size=args.length,
                                                  dtype=np.int64)
    out = a.reshape(-1, args.rate).sum(axis=1)

    print('\n\n'.join([
        format_scalar_definition('uint64_t', 'DATA_LEN', args.length),
        format_vector_definition('int64_t', 'A', a),
        format_vector_definition('int64_t', 'OUT', out),
    ]) + '\n')


if __name__ == '__main__':
    sys.exit(main())
