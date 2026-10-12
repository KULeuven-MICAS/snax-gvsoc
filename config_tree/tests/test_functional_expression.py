from __future__ import annotations

from config_tree.expression.numeric import ConstantValue
from config_tree import Expressions


def test_map_functional_chain_to_tuple():
    expression = ConstantValue(['uart', 'rtc']).map(
        Expressions.fn(
            'x',
            Expressions.ref('x').upper().prefix('CONFIG_LOG_').as_define(value=1),
        )
    )

    assert expression.evaluate() == [
        ('CONFIG_LOG_UART', 1),
        ('CONFIG_LOG_RTC', 1),
    ]


def test_map_functional_repr():
    expression = ConstantValue(['uart']).map(
        Expressions.fn(
            'x',
            Expressions.ref('x').upper().prefix('CONFIG_LOG_').as_define(value=1),
        )
    )

    assert ".map(fn('x'" in repr(expression)
    assert ".as_define(value=1)" in repr(expression)
