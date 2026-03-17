# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Martin Croome (croomem@essilor.fr)

"""Config-native dataclasses mirroring the regmap data model.

These types live in config so that configs can declare register/command fields
without depending on the regmap package.
"""

from dataclasses import dataclass, field

from .field_type_alias import ConfigDumpable


@dataclass
class Regfield(ConfigDumpable):
    """A single bit-field within a register."""
    name: str
    width: int | None
    bit: int | None
    access: str | None
    desc: str | None = None
    reset: int | None = None
    reset_txt: str | None = None

    @classmethod
    def dump_headers(cls) -> list[str]:
        return ['Field', 'Bit', 'Width', 'Access', 'Reset', 'Description']

    def dump_row(self) -> list[str]:
        reset = f'0x{self.reset:x}' if self.reset is not None else '-'
        return [
            self.name,
            str(self.bit) if self.bit is not None else '-',
            str(self.width) if self.width is not None else '-',
            self.access or '-',
            reset,
            self.desc or '',
        ]


@dataclass
class Register(ConfigDumpable):
    """A hardware register."""
    name: str
    offset: int | None = None
    width: int | None = None
    desc: str | None = None
    reset: int | None = None
    do_reset: bool = True
    template: str | None = None
    fields: list[Regfield] = field(default_factory=list)

    def get_field_template(self) -> str | None:
        return self.template if self.template is not None else self.name

    def get_fields(self) -> list[Regfield]:
        return self.fields

    @classmethod
    def dump_headers(cls) -> list[str]:
        return ['Name', 'Offset', 'Width', 'Reset', 'Fields', 'Description']

    def dump_row(self) -> list[str]:
        offset = f'0x{self.offset:x}' if self.offset is not None else '-'
        reset  = f'0x{self.reset:08x}' if self.reset is not None else '-'
        width  = str(self.width) if self.width is not None else '-'
        return [self.name, offset, width, reset, str(len(self.fields)), self.desc or '']

    def dump_children(self) -> list[ConfigDumpable]:
        return list(self.fields)


@dataclass
class Cmdfield(ConfigDumpable):
    """A single bit-field within a command."""
    name: str
    width: int | None
    offset: int | None
    value: str | None
    desc: str | None = None

    @classmethod
    def dump_headers(cls) -> list[str]:
        return ['Field', 'Bit', 'Width', 'Value', 'Description']

    def dump_row(self) -> list[str]:
        return [
            self.name,
            str(self.offset) if self.offset is not None else '-',
            str(self.width) if self.width is not None else '-',
            self.value or '-',
            self.desc or '',
        ]


@dataclass
class Cmd(ConfigDumpable):
    """A hardware command."""
    name: str
    code: str | None
    width: int
    desc: str | None = None
    fields: list[Cmdfield] = field(default_factory=list)

    @classmethod
    def dump_headers(cls) -> list[str]:
        return ['Command', 'Code', 'Width', 'Fields', 'Description']

    def dump_row(self) -> list[str]:
        return [self.name, self.code or '-', str(self.width), str(len(self.fields)), self.desc or '']

    def dump_children(self) -> list[ConfigDumpable]:
        return list(self.fields)


@dataclass
class Cmdmap(ConfigDumpable):
    """A named group of commands."""
    name: str
    cmds: list[Cmd] = field(default_factory=list)

    @classmethod
    def dump_headers(cls) -> list[str]:
        return ['Command Map', 'Commands']

    def dump_row(self) -> list[str]:
        return [self.name, str(len(self.cmds))]

    def dump_children(self) -> list[ConfigDumpable]:
        return list(self.cmds)
