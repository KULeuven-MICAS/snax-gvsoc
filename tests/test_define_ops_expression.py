from __future__ import annotations

from config_tree.expression.numeric import ConstantValue
from config_tree import list_to_tuples


def test_define_tuples_from_string_list_expression_evaluate():
    expression = list_to_tuples(
        ConstantValue(['uart', 'rtc']),
        key_prefix='CONFIG_LOG_',
        value=1,
        key_upper=True,
    )

    assert expression.evaluate() == [
        ('CONFIG_LOG_UART', 1),
        ('CONFIG_LOG_RTC', 1),
    ]


def test_define_tuples_from_string_list_expression_none_propagation():
    expression = list_to_tuples(
        ConstantValue(None),
        key_prefix='CONFIG_LOG_',
    )

    assert expression.evaluate(none_policy='propagate') is None

