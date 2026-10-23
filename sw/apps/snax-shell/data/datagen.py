#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""data.h of snax-shell: DATA_LEN, LOOP_ITER (beats of 4 lanes), A, B and
OUT = A + B.

A and B are uint64 in [0, 100), drawn with NumPy's legacy random state seeded
with seed, A first: the values snax_cluster's snax-alu datagen.py gives in
mode 0 after np.random.seed(seed). Printed to stdout:

    python3 datagen.py --length=192 --seed=0 > data.h

with data_utils (sw/util) on PYTHONPATH.
"""

import argparse
import sys

import numpy as np
from data_utils import format_scalar_definition, format_vector_definition

LANES = 4


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--length', type=int, required=True, help='elements of A and B')
    p.add_argument('--seed', type=int, default=0, help='NumPy seed (default 0)')
    args = p.parse_args()
    if args.length < 1 or args.length % LANES:
        p.error(f'length {args.length} is not a positive multiple of {LANES}')

    np.random.seed(args.seed)
    a = np.random.randint(0, 100, args.length)
    b = np.random.randint(0, 100, args.length)

    print('\n\n'.join([
        format_scalar_definition('uint64_t', 'DATA_LEN', args.length),
        format_scalar_definition('uint64_t', 'LOOP_ITER', args.length // LANES),
        format_vector_definition('uint64_t', 'A', a),
        format_vector_definition('uint64_t', 'B', b),
        format_vector_definition('uint64_t', 'OUT', a + b),
    ]) + '\n')


if __name__ == '__main__':
    sys.exit(main())
