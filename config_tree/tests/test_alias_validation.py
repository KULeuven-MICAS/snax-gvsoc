# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for enhanced ConfigFieldAliasInterface with casting and validation."""

from typing import Annotated, Literal
from types import SimpleNamespace
import pytest
from config_tree import Config, cfg_field, IntRange, HexInt


def test_intrange_new_format():
    """Test IntRange with handler in annotation (new preferred format)."""
    class TestConfig(Config):
        # New format: handler class in annotation
        percentage: Annotated[int, IntRange, 0, 100] = cfg_field(default=50)
    
    config = TestConfig("test", percentage=75)
    assert config.percentage == 75
    
    # Test validation
    Config.override_fields(["test2/percentage=150"])
    with pytest.raises(ValueError, match="greater than maximum"):
        TestConfig("test2")


def test_intrange_subscript_syntax():
    """Test IntRange with subscript syntax IntRange[min, max]."""
    class TestConfig(Config):
        # Cleanest format: IntRange[min, max]
        percentage: IntRange[0, 100] = cfg_field(default=50)
        priority: IntRange[1, 10] = cfg_field(default=5)
    
    config = TestConfig("test", percentage=75, priority=8)
    assert config.percentage == 75
    assert config.priority == 8
    
    # Test validation with override
    Config.override_fields(["test2/percentage=150"])
    with pytest.raises(ValueError, match="greater than maximum"):
        TestConfig("test2")
    
    
    Config.override_fields(["test3/priority=-1"])
    with pytest.raises(ValueError, match="less than minimum"):
        TestConfig("test3")


def test_hexint_casting():
    """Test HexInt cast method."""
    # Test casting from string
    assert HexInt.cast("0x1000", SimpleNamespace(type=int)) == 4096
    assert HexInt.cast("0x1000_0000", SimpleNamespace(type=int)) == 268435456
    assert HexInt.cast("42", SimpleNamespace(type=int)) == 42
    
    # Test casting from int
    assert HexInt.cast(100, SimpleNamespace(type=int)) == 100


def test_hexint_validation():
    """Test HexInt validate method."""
    # Valid values
    HexInt.validate(42, SimpleNamespace(type=int))
    HexInt.validate(0, SimpleNamespace(type=int))
    HexInt.validate(-10, SimpleNamespace(type=int))
    
    # Invalid values
    with pytest.raises(ValueError, match="Expected integer"):
        HexInt.validate("not_an_int", SimpleNamespace(type=int))
    
    with pytest.raises(ValueError, match="Expected integer"):
        HexInt.validate(3.14, SimpleNamespace(type=int))
    
    with pytest.raises(ValueError, match="Expected integer"):
        HexInt.validate(True, SimpleNamespace(type=int))  # bool is not accepted


def test_intrange_basic():
    """Test IntRange type alias with range validation (backward compatible string format)."""
    class TestConfig(Config):
        # Old format: string marker (still supported for backward compatibility)
        percentage: Annotated[int, "range", 0, 100] = cfg_field(default=50)
    
    # Valid value within range
    config = TestConfig("test", percentage=75)
    assert config.percentage == 75


def test_intrange_casting():
    """Test IntRange casting."""
    assert IntRange.cast("50", SimpleNamespace(type=int)) == 50
    assert IntRange.cast("0x10", SimpleNamespace(type=int)) == 16
    assert IntRange.cast(42, SimpleNamespace(type=int)) == 42


def test_intrange_validation():
    """Test IntRange validation with min/max."""
    # Valid values
    IntRange.validate(50, SimpleNamespace(type=Annotated[int, "range", 0, 100]))
    IntRange.validate(0, SimpleNamespace(type=Annotated[int, "range", 0, 100]))
    IntRange.validate(100, SimpleNamespace(type=Annotated[int, "range", 0, 100]))
    
    # Out of range values
    with pytest.raises(ValueError, match="less than minimum"):
        IntRange.validate(-1, SimpleNamespace(type=Annotated[int, "range", 0, 100]))
    
    with pytest.raises(ValueError, match="greater than maximum"):
        IntRange.validate(101, SimpleNamespace(type=Annotated[int, "range", 0, 100]))
    
    # No min/max
    IntRange.validate(999, SimpleNamespace(type=Annotated[int, "range"]))
    
    # Only min
    IntRange.validate(50, SimpleNamespace(type=Annotated[int, "range", 10]))
    with pytest.raises(ValueError, match="less than minimum"):
        IntRange.validate(5, SimpleNamespace(type=Annotated[int, "range", 10]))
    
    # Only max (with min as None is tricky, so test with large range)
    IntRange.validate(50, SimpleNamespace(type=Annotated[int, "range", 0, 90]))
    with pytest.raises(ValueError, match="greater than maximum"):
        IntRange.validate(100, SimpleNamespace(type=Annotated[int, "range", 0, 90]))


def test_intrange_with_override():
    """Test IntRange with command-line override."""
    class TestConfig(Config):
        percentage: Annotated[int, IntRange, 0, 100] = cfg_field(default=50)
    
    # Override with valid value
    Config.override_fields(["test/percentage=80"])
    config = TestConfig("test")
    assert config.percentage == 80
    
    Config.reset()  # Clear registry before creating another config with same name
    
    # Override with invalid value (out of range)
    Config.override_fields(["test/percentage=150"])
    with pytest.raises(ValueError, match="greater than maximum"):
        TestConfig("test")


def test_literal_basic():
    """Test Literal type with validation."""
    class TestConfig(Config):
        status: Literal['idle', 'running', 'stopped'] = cfg_field(default='idle')
    
    config = TestConfig("test", status='running')
    assert config.status == 'running'


def test_literal_with_override():
    """Test Literal with command-line override."""
    class TestConfig(Config):
        mode: Literal['debug', 'release', 'test'] = cfg_field(default='debug')
    
    # Override with valid value
    Config.override_fields(["test/mode=release"])
    config = TestConfig("test")
    assert config.mode == 'release'
    
    Config.reset()  # Clear registry before creating another config with same name
    
    # Override with invalid value
    Config.override_fields(["test/mode=production"])
    with pytest.raises(ValueError, match="not in allowed values"):
        TestConfig("test")


def test_multiple_alias_types():
    """Test config with multiple alias types."""
    class TestConfig(Config):
        base_addr: HexInt = cfg_field(default=0x1000, inlined_dump=True)
        percentage: Annotated[int, "range", 0, 100] = cfg_field(default=50)
        mode: Literal['on', 'off'] = cfg_field(default='on')
    
    config = TestConfig("test", base_addr=HexInt(0x2000), percentage=75, mode='off')
    
    assert config.base_addr == 0x2000
    assert config.percentage == 75
    assert config.mode == 'off'
    
    # Check repr formatting for HexInt
    assert '0x2000' in repr(config)


def test_intrange_get_range():
    """Test IntRange.get_range helper method."""
    # Full range
    typ1 = Annotated[int, "range", 0, 100]
    assert IntRange.get_range(typ1) == (0, 100)
    
    # Only min
    typ2 = Annotated[int, "range", 10]
    assert IntRange.get_range(typ2) == (10, None)
    
    # No range info (shouldn't happen in practice)
    typ3 = Annotated[int, "range"]
    assert IntRange.get_range(typ3) == (None, None)


def test_alias_interface_not_implemented():
    """Test that ConfigFieldAliasInterface requires implementation."""
    from config_tree.field_type_alias import ConfigFieldTypeAliasInterface
    
    class BadAlias(int, ConfigFieldTypeAliasInterface):
        """Alias that doesn't implement required methods."""
        pass
    
    # Should raise NotImplementedError for unimplemented methods
    with pytest.raises(NotImplementedError, match="must implement format"):
        BadAlias.format(42)
    
    with pytest.raises(NotImplementedError, match="must implement cast"):
        BadAlias.cast("42", SimpleNamespace(type=int))
    
    with pytest.raises(NotImplementedError, match="must implement check_annotation"):
        BadAlias.check_annotation(int)
    
    # validate() has a default implementation that does nothing
    BadAlias.validate(42, SimpleNamespace(type=int))  # Should not raise


def test_intrange_in_repr():
    """Test that IntRange values show in repr correctly."""
    class TestConfig(Config):
        priority: Annotated[int, "range", 1, 10] = cfg_field(default=5, inlined_dump=True)
    
    config = TestConfig("test", priority=7)
    assert 'priority=7' in repr(config)
