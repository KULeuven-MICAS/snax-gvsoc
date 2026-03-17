# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from abc import ABC

from .base import Expression, NonePolicy
from .numeric import ConstantValue


_lambda_scope: ContextVar[dict[str, Any]] = ContextVar("_lambda_scope", default={})


class StringExpression(Expression, ABC):
    """Abstract base for expressions that produce string values."""


@dataclass(frozen=True, eq=False)
class StringConcatExpression(StringExpression):
    """Concatenation of two sub-expressions evaluated as strings."""
    left: Expression
    right: Expression

    def __repr__(self) -> str:
        return f"({self.left!r} + {self.right!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> str | None:
        left_value = self.left.evaluate(none_policy)
        if left_value is None:
            return None
        right_value = self.right.evaluate(none_policy)
        if right_value is None:
            return None
        return f"{left_value}{right_value}"


@dataclass(frozen=True, eq=False)
class LambdaRefExpression(Expression):
    name: str

    def __repr__(self) -> str:
        return f"ref({self.name!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        _ = none_policy
        scope = _lambda_scope.get()
        if self.name not in scope:
            raise KeyError(f"Lambda reference {self.name!r} not found in scope")
        return scope[self.name]


@dataclass(frozen=True, eq=False)
class LambdaFunctionExpression(Expression):
    arg_name: str
    body: Expression

    def __repr__(self) -> str:
        return f"fn({self.arg_name!r}, {self.body!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        _ = none_policy
        return self


@dataclass(frozen=True, eq=False)
class MapExpression(Expression):
    source: Expression
    fn: LambdaFunctionExpression

    def __repr__(self) -> str:
        return f"{self.source!r}.map({self.fn!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> list[Any] | None:
        source_value = self.source.evaluate(none_policy)
        if source_value is None:
            return None
        if not isinstance(source_value, list):
            raise TypeError(f"map() source must evaluate to a list, got {type(source_value).__name__}")

        previous_scope = _lambda_scope.get()
        result: list[Any] = []
        try:
            for item in source_value:
                item_scope = dict(previous_scope)
                item_scope[self.fn.arg_name] = item
                token = _lambda_scope.set(item_scope)
                try:
                    result.append(self.fn.body.evaluate(none_policy))
                finally:
                    _lambda_scope.reset(token)
        finally:
            _lambda_scope.set(previous_scope)
        return result


@dataclass(frozen=True, eq=False)
class UpperExpression(StringExpression):
    source: Expression

    def __repr__(self) -> str:
        return f"{self.source!r}.upper()"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> str | None:
        source_value = self.source.evaluate(none_policy)
        if source_value is None:
            return None
        return str(source_value).upper()


@dataclass(frozen=True, eq=False)
class LowerExpression(StringExpression):
    source: Expression

    def __repr__(self) -> str:
        return f"{self.source!r}.lower()"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> str | None:
        source_value = self.source.evaluate(none_policy)
        if source_value is None:
            return None
        return str(source_value).lower()


@dataclass(frozen=True, eq=False)
class TupleExpression(Expression):
    key: Expression
    value: Expression

    def __repr__(self) -> str:
        return f"{self.key!r}.as_define(value={self.value!r})"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> tuple[str, Any] | None:
        key = self.key.evaluate(none_policy)
        if key is None:
            return None
        value = self.value.evaluate(none_policy)
        return (str(key), value)


class Expressions:
    """Factory helpers for functional expression syntax."""

    @staticmethod
    def ref(name: str) -> LambdaRefExpression:
        return LambdaRefExpression(name=name)

    @staticmethod
    def fn(arg_name: str, body: Expression | Any) -> LambdaFunctionExpression:
        body_expr = body if isinstance(body, Expression) else ConstantValue(body)
        return LambdaFunctionExpression(arg_name=arg_name, body=body_expr)
