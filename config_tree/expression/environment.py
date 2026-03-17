# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from dataclasses import dataclass

from .base import NonePolicy
from .numeric import NumericExpression


@dataclass(frozen=True, eq=False)
class EnvironmentVariableExpression(NumericExpression):
    """Expression that evaluates to an environment variable value.

    Returns the variable value if present, otherwise ``default``.
    The result is typically ``str | None`` and can be combined with
    comparisons and arithmetic-expression concatenation.
    """

    key: str
    default: str | None = None

    def __repr__(self) -> str:
        if self.default is None:
            return f"env({self.key!r})"
        return f"env({self.key!r}, default={self.default!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> str | None:
        _ = none_policy
        return os.environ.get(self.key, self.default)


def env(key: str, default: str | None = None) -> EnvironmentVariableExpression:
    """Create an expression that resolves environment variable ``key``."""

    return EnvironmentVariableExpression(key=key, default=default)
