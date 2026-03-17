"""
Pyright-checked examples of valid Config usage.
This file must produce zero errors when analysed by pyright.
"""
from typing import assert_type

from config_tree import Config, cfg_field


class MyConfig(Config):
    value: int = 42


class ChildConfig(Config):
    count: int = cfg_field(default=0)


# Correct construction
c1 = MyConfig(name='test')
assert_type(c1, MyConfig)

# Inherited base fields are typed correctly
assert_type(c1.name, str)
assert_type(c1.label, str | None)
assert_type(c1.path, str)

# Subclass fields are typed correctly
assert_type(c1.value, int)

# Optional label
c2 = MyConfig(name='test', label='lbl')
assert_type(c2.label, str | None)

# Subclass field value override
c3 = MyConfig(name='test', value=99)
assert_type(c3.value, int)

# ChildConfig
c4 = ChildConfig(name='child')
assert_type(c4.count, int)
