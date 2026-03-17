# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import Expression, NonePolicy
from .numeric import ConstantValue


@dataclass(frozen=True, eq=False)
class ListToTuplesExpression(Expression):
    """Map a list expression to ``(key, value)`` tuples.

    The key is derived from each list item after optional case transform and
    prefix/suffix decoration.
    """

    values: Expression
    value: Expression
    key_prefix: str = ""
    key_suffix: str = ""
    key_upper: bool = False
    key_lower: bool = False

    def __repr__(self) -> str:
        step = "ref('x')"
        if self.key_upper:
            step += ".upper()"
        if self.key_lower:
            step += ".lower()"
        if self.key_prefix:
            step += f".prefix({self.key_prefix!r})"
        if self.key_suffix:
            step += f".suffix({self.key_suffix!r})"
        step += f".as_define(value={self.value!r})"
        return f"{self.values!r}.map(fn('x', {step}))"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> list[tuple[str, Any]] | None:
        list_value = self.values.evaluate(none_policy)
        if list_value is None:
            return None

        if not isinstance(list_value, list):
            raise TypeError(f"Expected list value, got {type(list_value).__name__}")

        define_value = self.value.evaluate(none_policy)
        mapped: list[tuple[str, Any]] = []
        for item in list_value:
            item_text = str(item)
            if self.key_upper:
                item_text = item_text.upper()
            elif self.key_lower:
                item_text = item_text.lower()
            mapped.append((f"{self.key_prefix}{item_text}{self.key_suffix}", define_value))
        return mapped


def list_to_tuples(
    values: Expression | list[str],
    *,
    key_prefix: str = "",
    key_suffix: str = "",
    value: Expression | str | int = 1,
    key_upper: bool = False,
    key_lower: bool = False,
) -> ListToTuplesExpression:
    """Create a deferred expression that maps list items to ``(key, value)`` tuples."""

    if key_upper and key_lower:
        raise ValueError("key_upper and key_lower are mutually exclusive")

    source_expr = values if isinstance(values, Expression) else ConstantValue(values)
    value_expr = value if isinstance(value, Expression) else ConstantValue(value)

    return ListToTuplesExpression(
        values=source_expr,
        key_prefix=key_prefix,
        key_suffix=key_suffix,
        value=value_expr,
        key_upper=key_upper,
        key_lower=key_lower,
    )

