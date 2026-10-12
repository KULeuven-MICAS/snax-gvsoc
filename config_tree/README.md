Read the agent.md file in the root of the project after reading this.

# Configuration System Module

This module provides a hierarchical, type-safe configuration system with dataclass-based configs, conditional evaluation, validation, and rich formatting.

## Core Concepts

### Config Class
The base class for all configuration objects. Configs form a parent-child hierarchy and are automatically registered in global registries.

**Key Features:**
- Hierarchical path construction (e.g., "parent/child/grandchild")
- Global registries by path, class, name, and label
- Command-line attribute override support
- Automatic validation with configurable none_policy
- Rich tree-based dumping/display

**Creation:**
```python
from config_tree import Config

class MyConfig(Config):
    value: int = 42
    name: str = "default"

# Create instance (name is positional-only)
config = MyConfig("my_instance")
```

### Configuration Fields (`cfg_field`)
Enhanced dataclass fields with metadata for documentation, formatting, and behavior control.

**Parameters:**
- `default` / `default_factory`: Default value or factory
- `desc`: Human-readable description
- `fmt`: Format string (e.g., "hex")
- `read`: Include in full dumps / generate defines
- `write`: Writable (can be overridden, affects conditions)
- `inlined_dump`: Include in `__repr__` output

**Example:**
```python
from config_tree import cfg_field, HexInt

class MemConfig(Config):
    base_addr: HexInt = cfg_field(
        default=0x80000000,
        desc="Base address of memory region",
        inlined_dump=True
    )
    size: int = cfg_field(
        default=0x10000,
        write=True,  # User can override this
        desc="Size in bytes"
    )
```

### Hierarchical Relationships

**Parent-Child:**
```python
class ParentConfig(Config):
    child_value: int = 10
    
    def __post_init__(self):
        super().__post_init__()
        # Children created in __post_init__ automatically have parent set
        self.child = ChildConfig("child")

parent = ParentConfig("parent")
# parent.path = "parent"
# parent.child.path = "parent/child"
```

**Deferred Adoption:**
```python
Config._defer_parent_init = True
orphan = MyConfig("orphan")
Config._defer_parent_init = False

# Later, adopt into parent
orphan.adopt(parent)
```

### Global Registries

**Access configs by path:**
```python
Config.get_config_by_path("parent/child")
Config.get_configs_by_path("parent/*")  # Glob pattern
```

**Access by class:**
```python
MyConfig.get_configs_by_class()  # All instances of MyConfig
```

**Access by label:**
```python
config = MyConfig("instance", label="main_config")
Config.get_config_by_label("main_config")
```

### Expressions

The expression system provides a flexible hierarchy for building configuration expressions
and conditions with proper type separation.

**Expression Hierarchy:**
- `Expression` (ABC) - Base class for all expressions
  - `BooleanExpression` - Boolean logic with explicit methods
  - `ValueExpression` - Expressions that produce comparable values
    - `NumericExpression` - Numeric/bitwise operations with operators

**Creating Field References:**

There are two ways to create field references:

```python
# Traditional syntax with get_ref()
config.get_ref("enabled")

# Preferred: refs proxy - cleaner, with IDE autocomplete
refs = config.refs    # shortcut
refs.enabled          # returns ConfigFieldRef
refs.value > 10       # returns BooleanExpression (GreaterThanCondition)

# Explicitly control dump visibility flags:
config.set_field_rw("enabled", read=True)
MyConfig.set_field_rw("enabled", read=True, write=False)
```

**Creating Boolean Expressions (Conditions):**
```python
refs = config.refs

# Comparisons (==, !=, <, <=, >, >=) produce BooleanExpressions
condition = refs.value > 10

# Logical operations use EXPLICIT METHODS (Python's and/or cannot be overloaded)
complex_cond = (refs.value > 10).logical_and(refs.enabled)
either_cond = condition1.logical_or(condition2)
negated = condition.logical_not()

# Class-level conditions (all instances)
class_cond = MyConfig.get_ref("value") > 5
```

**NumericExpression Operators:**

NumericExpressions support arithmetic and bitwise operators:
```python
# Arithmetic: +, -, *, /, //, %, **
total = value_ref + offset_ref

# Bitwise: &, |, ^, ~, <<, >>
masked = value_ref & 0xFF
shifted = value_ref << 2
```

Note: `&` and `|` are for bitwise operations on NumericExpressions only.
Use `logical_and()` and `logical_or()` for boolean logic.

**Evaluating Conditions:**
```python
result = condition.evaluate()  # Returns True/False

# none_policy controls None handling:
# - 'fail' (default): None values cause False
# - 'ignore': None values are skipped (treated as True)
# - 'propagate': Three-valued logic (returns None if indeterminate)
result = condition.evaluate(none_policy='propagate')
```

**Three-Valued Logic (propagate policy):**
- `logical_or(None, True) = True`
- `logical_or(None, False) = None`
- `logical_and(None, False) = False`
- `logical_and(None, True) = None`
- `logical_not(None) = None`
- Any comparison with None returns None: 1 > None = None, None < 1 = None, etc.

**Writable Fields and Build-Time vs Run-Time Values:**

The `write=True` flag on a field signals that its value is only resolved at run time (e.g. via
kconfig or a CLI override).  This drives two distinct evaluation modes:

- **Define emission** (`none_policy='fail'`, the default): the `write` flag is ignored and the
  concrete Python default is always returned.  This makes the Python default the visible
  build-time value — for example, a hardware ceiling like `default=3, write=True` will always
  produce `#define UART_COUNT_MAX 3` in generated headers.

- **Condition evaluation** (`none_policy='propagate'`, used by the builder): a writable field
  returns `None` (indeterminate) regardless of its Python default.  The builder then defers
  the whole conditional block to run time (e.g. emits `if(HAS_UART) … endif()`).

Two canonical patterns for numeric fields:

```python
class UartConfig(Config):
    # No meaningful default yet — conditions are indeterminate, define not emitted.
    baud_rate: int | None = cfg_field(default=None, write=False, desc="Baud rate (set at init)")

    # Hardware ceiling — build scripts always see 4; conditions deferred to run time.
    max_instances: int = cfg_field(default=4, write=True, desc="Maximum UART instances")
```

**Backward Compatibility:**
`Condition` is an alias for `BooleanExpression`.

**Expression Operand Resolution:**
When building composite expressions (e.g., comparisons, arithmetic), operands are resolved via the `as_operand()` method:
- `Expression.as_operand()` returns `self` by default
- This polymorphic pattern allows the config module to remain independent of builder: builder wrapper types can override `as_operand()` to customise how they participate in expressions (e.g. returning a reference rather than the wrapper itself)

### Validation

**Field Validation:**
Automatic validation checks:
- None values (configurable with none_policy)
- Type alias validation (HexInt, IntRange, etc.)

**Custom Validators:**
```python
class MyConfig(Config):
    value: int = 10
    
    def _validators(self):
        return [
            (self.get_ref('value') > 0).message("Value must be positive")
        ]

# Validation runs automatically during __post_init__
config = MyConfig("test")

# Manual validation
config.validate()  # Raises ConditionError if invalid
MyConfig.validate()  # Validates all instances
```

### Type Aliases

**HexInt:** Integer displayed as grouped hexadecimal
```python
addr: HexInt = 0x80000000  # Displays as "0x8000_0000"
```

**IntRange:** Integer with min/max constraints
```python
from typing import Annotated
from config_tree import IntRange

port: Annotated[int, IntRange(1024, 65535)] = 8080
```

**RegisterList:** List of `Register` dataclasses loaded from a GFM markdown file
```python
from config_tree import RegisterList, cfg_field

class MyConfig(Config):
    registers: RegisterList = cfg_field(
        default_factory=RegisterList,
        desc="Register map",
        write=True,  # allow CLI override
    )

# Override via CLI path:
Config.override_fields(["my_config/registers=/path/to/README.md"])
```

**CommandList:** List of `Cmdmap` dataclasses (each containing `Cmd` and `Cmdfield` entries)
```python
from config_tree import CommandList, cfg_field

class MyConfig(Config):
    commands: CommandList = cfg_field(
        default_factory=CommandList,
        desc="Command map",
        write=True,
    )
```

Both types parse GFM markdown documents that follow the register-map documentation
format (Registers / Commands sections with standard column names).

**Custom Type Aliases:**
Implement `ConfigFieldTypeAliasInterface`:
- `format(value) -> str`: How to display
- `cast(value, py_type) -> Any`: How to convert from string
- `validate(value, py_type) -> None`: Validation (raise on error)
- `check_annotation(py_type) -> bool`: Check if applies to type

### Dumping / Display

**Simple Dump:**
```python
config.dump()  # Prints rich tree to console
```

**Custom Console:**
```python
from rich.console import Console
console = Console()
config.dump(console=console, show_all=True)
```

**Tree Building:**
```python
from config_tree.dump import build_config_tree
tree = build_config_tree(config, show_all=False)
```

**Customising Dump Rows:**
```python
class MyConfig(Config):
    value: int = cfg_field(default=1, read=False)

    @classmethod
    def dump_columns(cls):
        return [("Field", "green"), ("Value", "cyan")]

    def dump_field_row(self, f, show_all: bool, type_hints: dict):
        if f.name != "value":
            return None  # Skip this field entirely
        return ("custom_value", f"<{self.value}>")
```

`dump_field_row()` decides both whether a field is emitted (`None` means skip)
and how values are formatted for the row.

### Command-Line Overrides

```python
# Set overrides before creating configs
Config.override_fields(["parent/child/value=100", "config/name=custom"])

# Later configs will use overridden values
config = MyConfig("config")
```

**Reset all state:**
```python
Config.reset()  # Clears all registries and state
```

## Module Files

- `config.py`: Config base class
- `condition.py`: Re-exports from expression package (backward compatibility)
- `expression/`: Expression system subpackage
  - `base.py`: Expression ABC, ConditionError, ConditionResultList, NonePolicy
  - `boolean.py`: BooleanExpression, LogicalAnd, LogicalOr, LogicalNot, ConditionEvaluator
  - `comparison.py`: Comparison expressions (EqualityCondition, LessThanCondition, etc.)
  - `numeric.py`: ValueExpression, NumericExpression, arithmetic/bitwise expressions
  - `field_ref.py`: ConfigFieldRef for field references
- `fields.py`: cfg_field() function and ConfigLink
- `field_type_alias.py`: HexInt, IntRange, type casting/validation
- `mappings.py`: AddressMapping, InterruptMapping mixin types for typed link discovery
- `register_types.py`: Register, Regfield, Cmd, Cmdfield, Cmdmap dataclasses
- `register_field_types.py`: RegisterList, CommandList ConfigFieldTypeAliasInterface types
- `md_parser.py`: GFM markdown parser producing register/command dataclasses
- `decorators.py`: class_or_instance_method decorator
- `dump.py`: Tree building and display formatting
- `utils.py`: Utility functions (hex_grouped, parse_bool)

## Common Patterns

### Creating a Config Hierarchy
```python
class SystemConfig(Config):
    name: str = "system"
    
    def __post_init__(self):
        super().__post_init__()
        self.cpu = CPUConfig("cpu")
        self.memory = MemoryConfig("memory")

system = SystemConfig("main")
# system.path = "main"
# system.cpu.path = "main/cpu"
# system.memory.path = "main/memory"
```

### Conditional Configuration
```python
class FeatureConfig(Config):
    enabled: bool = True
    param: int = 10
    
    def _validators(self):
        # Only validate param if enabled
        if self.enabled:
            return [(self.get_ref('param') > 0).message("Param must be positive")]
        return []

# Combining multiple validators
def _validators(self):
    return [
        (self.get_ref('min') < self.get_ref('max')).message("min must be less than max"),
        (self.get_ref('value') > 0).logical_and(
            self.get_ref('value') < 100
        ).message("value must be between 0 and 100")
    ]
```

### Config Linking
```python
from config_tree import ConfigLink

class RouterConfig(Config):
    def __post_init__(self):
        super().__post_init__()
        # Create link to another config
        link = ConfigLink(
            name="target",
            target=other_config,
            desc="Routes to this config"
        )
        self.links.append(link)
```

### Typed Mapping Discovery (`get_mapped_by`)

Any `Config` can declare itself as a mapping by inheriting a mixin from `mappings.py`
alongside `Config`.  The target can then discover all things mapped to it via
`get_mapped_by(kind)`, fully decoupled from any concrete router implementation.

```python
from config_tree import Config, cfg_field, AddressMapping, InterruptMapping
from config_tree.fields import ConfigLink
from typing import ClassVar

# ---- Define a mapping type ----
class BusMapping(Config, AddressMapping):  # inherits AddressMapping mixin
    _defer_parent_init: ClassVar[bool] = True
    base: int = cfg_field(default=0, fmt="hex")
    size: int = cfg_field(default=0, fmt="hex")
    to: Config = cfg_field(default=None)

    def __post_init__(self):
        super().__post_init__()
        if self.to is not None:
            self.to.links.append(ConfigLink(self.name, self))

# ---- Wire a peripheral ----
class UartConfig(Config):
    @property
    def addresses(self) -> list[AddressMapping]:
        return self.get_mapped_by(AddressMapping)

uart = UartConfig("uart")
bus  = Config("bus")
mapping = BusMapping("uart_bus", base=0x1A10_0000, size=0x1000, to=uart)
mapping.adopt(bus)

assert uart.addresses[0].base == 0x1A10_0000

# with_typehint makes self a Config — use the full Config API directly on the mapping:
uart_base_ref = uart.addresses[0].get_ref("base")  # lazy ConfigFieldRef
```

Multiple mapping kinds are supported on the same peripheral:
```python
uart.get_mapped_by(AddressMapping)    # -> list[AddressMapping]
uart.get_mapped_by(InterruptMapping)  # -> list[InterruptMapping]
```

New mapping types need only a new mixin in `mappings.py` and inheritance in the
concrete config — no changes to `Config` or `ConfigLink`.

## Dependencies

This module has **no dependencies** on the build system. It can be used standalone for configuration management without any build functionality.

The `md_parser` module depends on `marko` (GFM markdown parser) for loading register maps from documentation files.
