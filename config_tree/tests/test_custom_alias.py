# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for custom ConfigFieldAliasInterface types."""

from typing import Any, Annotated, get_origin, get_args
from config_tree import Config, cfg_field, ConfigFieldTypeAliasInterface, HexInt


class BinaryInt(int, ConfigFieldTypeAliasInterface):
    """Integer that displays in binary format with underscore grouping."""
    
    def __str__(self) -> str:
        return self.format(int(self))
    
    def __repr__(self) -> str:
        return self.format(int(self))
    
    @classmethod
    def format(cls, value: int, group: int = 4) -> str:
        """Format an integer as binary string with underscore grouping."""
        s = f"{value:b}"
        parts = [s[max(i - group, 0):i] for i in range(len(s), 0, -group)]
        return "0b" + "_".join(reversed(parts))
    
    @classmethod
    def check_annotation(cls, field_type: Any) -> bool:
        """Check if a type annotation is BinaryInt."""
        if field_type is cls:
            return True
        
        if get_origin(field_type) is Annotated:
            args = get_args(field_type)
            if args and args[0] is int and "binary" in args[1:]:
                return True
        
        return False


def test_hexint_as_value():
    """Test HexInt as a runtime value."""
    class TestConfig(Config):
        addr: int = cfg_field(default=0x80000000, inlined_dump=True)
    
    config = TestConfig("test")
    # Convert to HexInt
    config.addr = HexInt(config.addr)
    
    # Should use HexInt's __str__ method
    assert str(config.addr) == "0x8000_0000"
    assert repr(config) == "TestConfig(addr=0x8000_0000)"


def test_hexint_as_annotation():
    """Test HexInt used with Annotated annotation."""
    class TestConfig(Config):
        addr: Annotated[int, HexInt] = cfg_field(default=0x12345678, inlined_dump=True)
    
    config = TestConfig("test")
    
    # Should automatically format as hex due to annotation
    assert repr(config) == "TestConfig(addr=0x1234_5678)"


def test_hexint_direct_annotation():
    """Test HexInt used as direct type hint."""
    class TestConfig(Config):
        addr: HexInt = cfg_field(default=0xABCD, inlined_dump=True)
    
    config = TestConfig("test")
    
    # Should automatically format as hex
    assert repr(config) == "TestConfig(addr=0xabcd)"


def test_custom_binary_alias():
    """Test creating a custom BinaryInt alias."""
    # Register BinaryInt in the formatter helper
    # In a real implementation, we'd modify _get_field_alias_formatter
    # For now, just test the BinaryInt class itself
    
    value = BinaryInt(0b1010_1100)
    assert str(value) == "0b1010_1100"
    assert BinaryInt.format(0b11110000) == "0b1111_0000"
    
    # Test check_annotation
    assert BinaryInt.check_annotation(BinaryInt)
    assert BinaryInt.check_annotation(Annotated[int, "binary"])
    assert not BinaryInt.check_annotation(int)
    assert not BinaryInt.check_annotation(Annotated[int, "hex"])


def test_interface_not_implemented():
    """Test that ConfigFieldAliasInterface requires implementation."""
    import pytest
    
    class BadAlias(int, ConfigFieldTypeAliasInterface):
        """Alias that doesn't implement required methods."""
        pass
    
    # Should raise NotImplementedError when calling format
    with pytest.raises(NotImplementedError, match="BadAlias must implement format"):
        BadAlias.format(42)
    
    # Should raise NotImplementedError when calling check_annotation
    with pytest.raises(NotImplementedError, match="BadAlias must implement check_annotation"):
        BadAlias.check_annotation(int)


def test_hexint_in_dump():
    """Test that HexInt formatting works in dump() output."""
    class TestConfig(Config):
        addr: Annotated[int, HexInt] = cfg_field(default=0x80000000, read=True)
        size: HexInt = cfg_field(default=0x10000, read=True)
    
    config = TestConfig("test")
    
    # Get the formatted values
    from typing import get_type_hints
    from config_tree.dump import format_value
    type_hints = get_type_hints(type(config), include_extras=True)
    
    # Test format_value for addr
    addr_str = format_value(config.addr, None, "addr", type_hints)
    assert addr_str == "0x8000_0000"
    
    # Test format_value for size (no leading zeros padding)
    size_str = format_value(config.size, None, "size", type_hints)
    assert size_str == "0x1_0000"


def test_fallback_fmt_hex():
    """Test fallback to fmt='hex' metadata still works."""
    class TestConfig(Config):
        addr: int = cfg_field(default=0x1234, fmt="hex", inlined_dump=True)
    
    config = TestConfig("test")
    
    # Should use fallback hex formatting
    assert repr(config) == "TestConfig(addr=0x1234)"
