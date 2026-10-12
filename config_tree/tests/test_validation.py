#!/usr/bin/env python3
"""Test the validation system."""

import pytest
from config_tree import Config, cfg_field, ConditionError

class ServerConfig(Config):
    """Server configuration with validation."""
    port: int = cfg_field(default=8080, inlined_dump=True)
    max_connections: int = cfg_field(default=100, inlined_dump=True)
    timeout: int = cfg_field(default=30, inlined_dump=True)
    
    def _validators(self):
        return [
            (self.get_ref('port') >= 1024).logical_and(self.get_ref('port') <= 65535).message(
                "Port must be between 1024 and 65535"
            ),
            (self.get_ref('max_connections') > 0).logical_and(self.get_ref('max_connections') <= 10000).message(
                "Max connections must be between 1 and 10000"
            ),
            (self.get_ref('timeout') > 0).message("Timeout must be positive")
        ]

class ExplicitValidatingConfig(Config):
    """Config that explicitly validates with 'fail' policy in __post_init__."""
    port: int = cfg_field(default=8080)
    
    def __post_init__(self):
        super().__post_init__()
        # Explicitly validate with 'fail' policy (in addition to auto-validation with 'ignore')
        self.validate('fail')
    
    def _validators(self):
        return [
            (self.get_ref('port') >= 1024).logical_and(self.get_ref('port') <= 65535).message(
                "Port must be between 1024 and 65535"
            )
        ]

class NoValidatorsConfig(Config):
    """Config with no validators."""
    value: int = 42

def test_valid_config_auto_validates():
    """Test that valid config is created and auto-validated."""
    server = ServerConfig("server1", port=8080, max_connections=100, timeout=30)
    # No exception raised means auto-validation passed
    assert server.port == 8080

def test_invalid_port_raises_on_creation():
    """Test that invalid port raises ConditionError during creation (auto-validation)."""
    with pytest.raises(ConditionError) as exc_info:
        ServerConfig("server1", port=80)  # Auto-validation fails
    assert "Port must be between 1024 and 65535" in str(exc_info.value)

def test_explicit_fail_policy_validation():
    """Test config that explicitly validates with 'fail' policy in __post_init__."""
    with pytest.raises(ConditionError) as exc_info:
        ExplicitValidatingConfig("server1", port=80)
    assert "Port must be between 1024 and 65535" in str(exc_info.value)

def test_invalid_max_connections_raises_on_creation():
    """Test that invalid max_connections raises ConditionError during creation."""
    with pytest.raises(ConditionError) as exc_info:
        ServerConfig("server1", max_connections=50000)
    assert "Max connections must be between 1 and 10000" in str(exc_info.value)

def test_invalid_timeout_raises_on_creation():
    """Test that invalid timeout raises ConditionError during creation."""
    with pytest.raises(ConditionError) as exc_info:
        ServerConfig("server1", timeout=-5)
    assert "Timeout must be positive" in str(exc_info.value)

def test_manual_instance_validate():
    """Test manually calling validate on an instance."""
    # Create with valid values
    server = ServerConfig("server1", port=8080)
    
    # Modify to invalid value
    server.port = 80
    
    # Manual validate should fail
    with pytest.raises(ConditionError) as exc_info:
        server.validate()
    assert "Port must be between 1024 and 65535" in str(exc_info.value)

def test_class_level_validate_all_instances():
    """Test class-level validate checks all instances."""
    # Create multiple valid instances
    s1 = ServerConfig("server1", port=8080)
    s2 = ServerConfig("server2", port=9000)
    
    # All should be valid
    ServerConfig.validate()  # Should not raise
    
    # Modify one to be invalid
    s1.port = 80
    
    # Class-level validate should fail
    with pytest.raises(ConditionError) as exc_info:
        ServerConfig.validate()
    assert "Port must be between 1024 and 65535" in str(exc_info.value)

def test_no_validators_config_works():
    """Test that config with no validators works fine."""
    cfg = NoValidatorsConfig("test", value=42)
    assert cfg.value == 42
    cfg.validate()  # Should not raise

def test_validate_with_none_policy_ignore():
    """Test validate with none_policy='ignore'."""
    class OptionalConfig(Config):
        value: int = None
        
        def _validators(self):
            return [
                (self.get_ref('value') > 0).message("Value must be positive")
            ]
    
    # With None value and ignore policy, should pass
    cfg = OptionalConfig("test")
    cfg.value = None
    cfg.validate(none_policy='ignore')  # Should not raise

def test_validate_with_none_policy_fail():
    """Test validate with none_policy='fail' (default)."""
    class RequiredConfig(Config):
        value: int = None
        
        def _validators(self):
            return [
                (self.get_ref('value') > 0).message("Value must be positive")
            ]
    
    cfg = RequiredConfig("test")
    cfg.value = None
    
    # With None value and fail policy, should raise
    with pytest.raises(Exception):  # Will raise TypeError or similar
        cfg.validate(none_policy='fail')

def test_multiple_validators_first_failure():
    """Test that first failing validator raises its message during creation."""
    class MultiValidatorConfig(Config):
        a: int = 0
        b: int = 0
        
        def _validators(self):
            return [
                (self.get_ref('a') > 5).message("A must be > 5"),
                (self.get_ref('b') > 10).message("B must be > 10")
            ]
    
    # Both invalid, but first one should raise during auto-validation
    with pytest.raises(ConditionError) as exc_info:
        MultiValidatorConfig("test", a=1, b=2)
    assert "A must be > 5" in str(exc_info.value)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
