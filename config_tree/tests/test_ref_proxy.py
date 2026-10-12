"""
Tests for ConfigRefProxy - automatic field-to-reference conversion.

Tests cover:
- Basic attribute access returning ConfigFieldRef
- Comparison operators creating conditions
- Arithmetic operators on numeric fields
- Error handling for invalid fields
- Read-only enforcement
- Usage in conditionals
"""

import pytest
from config_tree import Config, cfg_field, ConfigRefProxy
from config_tree.expression import ConfigFieldRef
from config_tree.expression import (
    EqualityCondition,
    GreaterThanCondition,
    LessThanCondition,
    ArithmeticExpression,
    StringConcatExpression,
)


class RefProxyTestConfig(Config):
    """Config for testing ConfigRefProxy."""
    enabled: bool = cfg_field(default=True, read=True)
    debug: bool = cfg_field(default=False, read=True)
    value: int = cfg_field(default=42, read=True)
    count: int = cfg_field(default=10, read=True)
    name_field: str = cfg_field(default="test", read=True)


class TestConfigRefProxyBasic:
    """Tests for basic ConfigRefProxy functionality."""

    def test_refs_property_returns_proxy(self):
        """Test that config.refs returns a ConfigRefProxy."""
        config = RefProxyTestConfig("test")
        proxy = config.refs
        
        assert isinstance(proxy, ConfigRefProxy)

    def test_proxy_repr(self):
        """Test the string representation of ConfigRefProxy."""
        config = RefProxyTestConfig("test")
        proxy = config.refs
        
        assert repr(proxy) == "ConfigRefProxy(test)"

    def test_attribute_access_returns_field_ref(self):
        """Test that attribute access returns ConfigFieldRef."""
        config = RefProxyTestConfig("test")
        ref = config.refs.enabled
        
        assert isinstance(ref, ConfigFieldRef)
        assert ref.field_name == "enabled"
        assert ref.config is config

    def test_multiple_fields(self):
        """Test accessing multiple fields through proxy."""
        config = RefProxyTestConfig("test")
        
        enabled_ref = config.refs.enabled
        debug_ref = config.refs.debug
        value_ref = config.refs.value
        
        assert enabled_ref.field_name == "enabled"
        assert debug_ref.field_name == "debug"
        assert value_ref.field_name == "value"

    def test_field_ref_evaluate(self):
        """Test that field refs from proxy evaluate correctly."""
        config = RefProxyTestConfig("test")
        config.value = 100
        
        ref = config.refs.value
        assert ref.evaluate() == 100


class TestConfigRefProxyComparisons:
    """Tests for comparison operators on refs proxy."""

    def test_equality_condition(self):
        """Test == operator creates EqualityCondition."""
        config = RefProxyTestConfig("test")
        cond = config.refs.enabled == True
        
        assert isinstance(cond, EqualityCondition)
        assert cond.evaluate() == True
        
        config.enabled = False
        assert cond.evaluate() == False

    def test_greater_than_condition(self):
        """Test > operator creates GreaterThanCondition."""
        config = RefProxyTestConfig("test")
        cond = config.refs.value > 10
        
        assert isinstance(cond, GreaterThanCondition)
        assert cond.evaluate() == True  # 42 > 10
        
        config.value = 5
        assert cond.evaluate() == False  # 5 > 10 is False

    def test_less_than_condition(self):
        """Test < operator creates LessThanCondition."""
        config = RefProxyTestConfig("test")
        cond = config.refs.value < 100
        
        assert isinstance(cond, LessThanCondition)
        assert cond.evaluate() == True  # 42 < 100

    def test_combined_conditions(self):
        """Test combining conditions with logical methods."""
        config = RefProxyTestConfig("test")
        
        cond = (config.refs.value > 10).logical_and(config.refs.value < 100)
        assert cond.evaluate() == True  # 42 is between 10 and 100
        
        config.value = 5
        assert cond.evaluate() == False  # 5 is not > 10

    def test_or_condition(self):
        """Test combining conditions with logical_or."""
        config = RefProxyTestConfig("test")
        config.value = 5
        
        cond = (config.refs.value < 10).logical_or(config.refs.value > 100)
        assert cond.evaluate() == True  # 5 < 10


class TestConfigRefProxyArithmetic:
    """Tests for arithmetic operations on numeric field refs."""

    def test_addition(self):
        """Test + operator on numeric refs."""
        config = RefProxyTestConfig("test")
        expr = config.refs.value + 10
        
        assert isinstance(expr, ArithmeticExpression)
        assert expr.evaluate() == 52  # 42 + 10

    def test_subtraction(self):
        """Test - operator on numeric refs."""
        config = RefProxyTestConfig("test")
        expr = config.refs.value - 10
        
        assert expr.evaluate() == 32  # 42 - 10

    def test_multiplication(self):
        """Test * operator on numeric refs."""
        config = RefProxyTestConfig("test")
        expr = config.refs.value * 2
        
        assert expr.evaluate() == 84  # 42 * 2

    def test_chained_arithmetic(self):
        """Test chaining arithmetic operations."""
        config = RefProxyTestConfig("test")
        expr = (config.refs.value + 8) * 2
        
        assert expr.evaluate() == 100  # (42 + 8) * 2

    def test_arithmetic_in_condition(self):
        """Test using arithmetic expressions in conditions."""
        config = RefProxyTestConfig("test")
        cond = (config.refs.value + 10) > 50
        
        assert cond.evaluate() == True  # (42 + 10) = 52 > 50


class TestConfigRefProxyErrors:
    """Tests for error handling in ConfigRefProxy."""

    def test_invalid_field_raises_error(self):
        """Test that accessing non-existent field raises AttributeError."""
        config = RefProxyTestConfig("test")
        
        with pytest.raises(AttributeError, match="has no field 'nonexistent'"):
            _ = config.refs.nonexistent

    def test_proxy_is_readonly(self):
        """Test that setting attributes on proxy raises error."""
        config = RefProxyTestConfig("test")
        
        with pytest.raises(AttributeError, match="read-only"):
            config.refs.value = 100


class TestConfigRefProxySyntaxComparison:
    """Tests comparing old and new syntax produce equivalent results."""

    def test_get_ref_vs_refs_attribute(self):
        """Test that get_ref() and refs.field produce equivalent refs."""
        config = RefProxyTestConfig("test")
        
        old_ref = config.get_ref("enabled")
        new_ref = config.refs.enabled
        
        # Both should be ConfigFieldRef with same field
        assert isinstance(old_ref, ConfigFieldRef)
        assert isinstance(new_ref, ConfigFieldRef)
        assert old_ref.field_name == new_ref.field_name
        assert old_ref.config is new_ref.config

    def test_conditions_evaluate_same(self):
        """Test that conditions built both ways evaluate the same."""
        config = RefProxyTestConfig("test")
        config.value = 50
        
        old_cond = config.get_ref("value") > 40
        new_cond = config.refs.value > 40
        
        assert old_cond.evaluate() == new_cond.evaluate() == True
        
        config.value = 30
        assert old_cond.evaluate() == new_cond.evaluate() == False


class TestConfigFieldRefStringConcat:
    """Tests for string concatenation via __add__ / __radd__ on ConfigFieldRef."""

    def test_str_plus_ref_returns_string_concat(self):
        """'prefix' + ref → StringConcatExpression."""
        config = RefProxyTestConfig("test")
        expr = '-O' + config.refs.value
        assert isinstance(expr, StringConcatExpression)

    def test_ref_plus_str_returns_string_concat(self):
        """ref + 'suffix' → StringConcatExpression."""
        config = RefProxyTestConfig("test")
        expr = config.refs.value + '_suffix'
        assert isinstance(expr, StringConcatExpression)

    def test_str_plus_ref_evaluates_as_prefix(self):
        """'prefix' + ref evaluates with prefix prepended."""
        config = RefProxyTestConfig("test")
        expr = '-O' + config.refs.name_field
        assert expr.evaluate() == '-Otest'

    def test_ref_plus_str_evaluates_as_suffix(self):
        """ref + 'suffix' evaluates with suffix appended."""
        config = RefProxyTestConfig("test")
        expr = config.refs.name_field + '_out'
        assert expr.evaluate() == 'test_out'

    def test_int_plus_ref_still_arithmetic(self):
        """int + ref still produces ArithmeticExpression."""
        config = RefProxyTestConfig("test")
        expr = 10 + config.refs.value
        assert isinstance(expr, ArithmeticExpression)
        assert expr.evaluate() == 52

    def test_ref_plus_int_still_arithmetic(self):
        """ref + int still produces ArithmeticExpression."""
        config = RefProxyTestConfig("test")
        expr = config.refs.value + 10
        assert isinstance(expr, ArithmeticExpression)
        assert expr.evaluate() == 52

    def test_chained_string_concat(self):
        """'prefix' + ref + 'suffix' chains correctly."""
        config = RefProxyTestConfig("test")
        expr = '-O' + config.refs.name_field + '!'
        assert isinstance(expr, StringConcatExpression)
        assert expr.evaluate() == '-Otest!'
