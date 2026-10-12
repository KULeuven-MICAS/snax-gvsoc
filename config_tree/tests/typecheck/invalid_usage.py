"""
Intentionally invalid Config usage.
This file must produce exactly the errors annotated with # E: below.
"""
from config_tree import Config, cfg_field


class MyConfig(Config):
    value: int = 42


class ChildConfig(Config):
    count: int = cfg_field(default=0)
    label_str: str = cfg_field(default='x')


# Wrong type for inherited 'name' field
MyConfig(name=42)  # E: Argument of type "Literal[42]" cannot be assigned to parameter "name"

# Wrong type for subclass field
MyConfig(name='ok', value='not_an_int')  # E: Argument of type "Literal['not_an_int']" cannot be assigned to parameter "value"

# Wrong type for 'count'
ChildConfig(name='c', count='hi')  # E: Argument of type "Literal['hi']" cannot be assigned to parameter "count"

# Wrong type for 'label_str'
ChildConfig(name='c', label_str=99)  # E: Argument of type "Literal[99]" cannot be assigned to parameter "label_str"
