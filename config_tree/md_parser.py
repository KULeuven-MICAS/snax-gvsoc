# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Markdown parser for register/command map documents.

Parses GFM-flavoured markdown produced by register map documentation tools and
returns config-native dataclasses (Register, Regfield, Cmd, Cmdfield, Cmdmap).
"""

from dataclasses import dataclass, field, InitVar
from typing import Sequence

from markdown_it import MarkdownIt

from .register_types import Cmd, Cmdfield, Cmdmap, Regfield, Register

_MD = MarkdownIt('commonmark').enable('table')


@dataclass
class Node:
    is_table: bool = False
    children: list['Node'] = field(default_factory=list)
    level: int | None = None
    title: str = field(default='', init=False)
    tables: list['Table'] = field(default_factory=list)

    def get_table(self, index: int = 0) -> 'Table | None':
        if index >= len(self.tables):
            return None
        return self.tables[index]

    def add_header(self, node: 'Node') -> None:
        self.children.append(node)

    def add_children(self, node: 'Node') -> None:
        self.children.append(node)
        if node.is_table:
            self.tables.append(node)  # type: ignore[arg-type]

    def is_header(self) -> bool:
        return self.level is not None

    def dump(self, indent: str = '') -> None:
        if self.is_header():
            print(indent + self.title)
        for child in self.children:
            child.dump('  ' + indent)

    def get(self, name: str) -> 'Node | None':
        if self.is_header() and self.title == name:
            return self
        for child in self.children:
            result = child.get(name)
            if result is not None:
                return result
        return None


@dataclass
class Document(Node):
    md: InitVar[list | None] = None

    def __post_init__(self, md: list | None) -> None:
        if md is None:
            return
        last_headers: Sequence[Node | None] = [self] + [None] * 6
        last_header: Node | None = None
        i = 0
        while i < len(md):
            t = md[i]
            if t.type == 'heading_open':
                level = int(t.tag[1:])
                title = md[i + 1].content  # inline token
                node: Node = Heading()
                node.level = level
                node.title = title
                parent = last_headers[level - 1]
                if parent is not None:
                    parent.add_header(node)
                last_headers[level] = node
                last_header = node
                i += 3  # heading_open, inline, heading_close
            elif t.type == 'table_open':
                j = i + 1
                while j < len(md) and md[j].type != 'table_close':
                    j += 1
                table_node: Node = Table(md=md[i:j + 1])
                if last_header is not None:
                    last_header.add_children(table_node)
                i = j + 1
            else:
                i += 1


@dataclass
class Heading(Node):
    pass


@dataclass
class Table(Node):
    md: InitVar[list | None] = None
    table: list[list[str | None]] = field(default_factory=list, init=False)
    names: list[str] = field(default_factory=list, init=False)

    def __post_init__(self, md: list | None) -> None:
        self.is_table = True
        if not md:
            return

        # --- header row ---
        header_row: list[str | None] = []
        in_th = False
        in_header = False
        for t in md:
            if t.type == 'thead_open':
                in_header = True
            elif t.type == 'thead_close':
                break
            elif not in_header:
                continue
            elif t.type == 'th_open':
                in_th = True
                header_row.append('')
            elif t.type == 'th_close':
                in_th = False
            elif t.type == 'inline' and in_th:
                header_row[-1] = t.content
        self.table.append(header_row)

        # --- body rows ---
        in_tbody = False
        in_td = False
        current_row: list[str | None] = []
        for t in md:
            if t.type == 'tbody_open':
                in_tbody = True
            elif t.type == 'tbody_close':
                break
            elif not in_tbody:
                continue
            elif t.type == 'tr_open':
                current_row = []
            elif t.type == 'tr_close':
                self.table.append(current_row)
            elif t.type == 'td_open':
                in_td = True
                current_row.append('')
            elif t.type == 'td_close':
                in_td = False
            elif t.type == 'inline' and in_td:
                current_row[-1] = t.content

        self.names = [str(n).lower() for n in self.table[0]]

    def get_index(self, names: list[str]) -> int:
        for name in names:
            if name.lower() in self.names:
                return self.names.index(name.lower())
        return -1

    def get_elem(self, row: int, index: int | None) -> str | None:
        if index is None or index == -1:
            return None
        return self.table[row + 1][index]

    def get_elem_int(self, row: int, index: int | None) -> int | None:
        elem = self.get_elem(row, index)
        return int(elem, 0) if elem else None

    def get_size(self) -> int:
        return len(self.table) - 1


def parse_document(text: str) -> Document:
    """Parse GFM markdown text into a Document node tree."""
    return Document(md=_MD.parse(text))


def parse_registers(ast: Node) -> list[Register]:
    """Extract registers (and their fields) from a parsed document node.

    Args:
        ast: A Node (typically a Document or sub-section) to search within.

    Returns:
        List of Register dataclasses with nested Regfield dataclasses.

    Raises:
        RuntimeError: If the Registers section or its table is missing.
    """
    registers_ast = ast.get('Registers')
    if registers_ast is None:
        raise RuntimeError("Didn't find section 'Registers'")

    table = registers_ast.get_table()
    if table is None:
        raise RuntimeError("Didn't find table in section 'Registers'")

    name_index = table.get_index(['Register Name', 'Name'])
    offset_index = table.get_index(['Offset', 'Address'])
    width_index = table.get_index(['Size'])
    properties_index = table.get_index(['Properties'])
    reset_index = table.get_index(['Default', 'Reset Value'])
    description_index = table.get_index(['Description', 'Short description'])
    do_reset_index = table.get_index(['Reset'])

    registers: list[Register] = []
    for index in range(table.get_size()):
        reg = Register(
            name=table.get_elem(index, name_index) or '',
            offset=table.get_elem_int(index, offset_index),
        )

        if properties_index != -1:
            props_str = table.get_elem(index, properties_index)
            if props_str:
                for prop in props_str.split():
                    key, _, val = prop.partition('=')
                    if key == 'template':
                        reg.template = val

        if reg.template is None:
            reg.template = reg.name

        if width_index != -1:
            reg.width = table.get_elem_int(index, width_index)

        if reset_index != -1:
            reg.reset = table.get_elem_int(index, reset_index)

        if description_index != -1:
            reg.desc = table.get_elem(index, description_index)

        if do_reset_index != -1:
            reg.do_reset = bool(table.get_elem_int(index, do_reset_index))

        registers.append(reg)

    # Resolve fields for each register via its template section
    for reg in registers:
        reg_name = reg.get_field_template()
        register_ast = ast.get(reg_name) if reg_name else None
        if register_ast is None:
            continue

        fields_ast = register_ast.get('Fields')
        field_table = fields_ast.get_table() if fields_ast is not None else register_ast.get_table()

        if field_table is None:
            continue

        fname_index = field_table.get_index(['Field Name'])
        bit_index = field_table.get_index(['Offset', 'Bit', 'Bit Position'])
        fwidth_index = field_table.get_index(['Size', 'Width'])
        access_index = field_table.get_index(['Host Access Type', 'Access Type'])
        freset_index = field_table.get_index(['Default', 'Reset Value'])
        fdesc_index = field_table.get_index(['Description', 'Short description'])

        for fidx in range(field_table.get_size()):
            rf = Regfield(
                name=field_table.get_elem(fidx, fname_index) or '',
                width=field_table.get_elem_int(fidx, fwidth_index),
                bit=field_table.get_elem_int(fidx, bit_index),
                access=field_table.get_elem(fidx, access_index),
            )
            if freset_index != -1:
                rf.reset = field_table.get_elem_int(fidx, freset_index)
                rf.reset_txt = field_table.get_elem(fidx, freset_index)
            elif reg.reset is not None and rf.bit is not None and rf.width is not None:
                rf.reset = (reg.reset >> rf.bit) & ((1 << rf.width) - 1)
                rf.reset_txt = f'0x{rf.reset:x}'
            else:
                rf.reset_txt = '--'
            if fdesc_index != -1:
                rf.desc = field_table.get_elem(fidx, fdesc_index)
            reg.fields.append(rf)

    return registers


def parse_cmdmaps(ast: Node) -> list[Cmdmap]:
    """Extract command maps from a parsed document node.

    Args:
        ast: A Node (typically a Document or sub-section) to search within.

    Returns:
        List of Cmdmap dataclasses, each containing Cmd and Cmdfield dataclasses.
        Returns an empty list if no Commands section is found.
    """
    commands_ast = ast.get('Commands')
    if commands_ast is None:
        return []

    command_maps: list[Cmdmap] = []
    for command_ast in commands_ast.children:
        if not command_ast.is_header():
            continue

        cmdmap = Cmdmap(name=command_ast.title)

        table = command_ast.get_table()
        if table is None:
            raise RuntimeError(f"Didn't find table in Commands section '{command_ast.title}'")

        name_index = table.get_index(['Command Name'])
        size_index = table.get_index(['Size'])
        id_index = table.get_index(['Command field', 'id'])
        desc_index = table.get_index(['Description', 'Short description'])

        for index in range(table.get_size()):
            width = table.get_elem_int(index, size_index) if size_index != -1 else 32
            cmd = Cmd(
                name=table.get_elem(index, name_index) or '',
                code=table.get_elem(index, id_index),
                width=width or 32,
                desc=table.get_elem(index, desc_index),
            )
            cmdmap.cmds.append(cmd)

        for cmd in cmdmap.cmds:
            cmd_ast = ast.get(cmd.name)
            if cmd_ast is None:
                continue

            fields_ast = cmd_ast.get('Fields')
            field_table = fields_ast.get_table() if fields_ast is not None else cmd_ast.get_table()

            if field_table is None:
                continue

            fname_index = field_table.get_index(['Field Name'])
            bit_index = field_table.get_index(['Offset', 'Bit', 'Bit Position'])
            fwidth_index = field_table.get_index(['Size', 'Width'])
            value_index = field_table.get_index(['Value'])
            fdesc_index = field_table.get_index(['Description', 'Short description'])

            for fidx in range(field_table.get_size()):
                cf = Cmdfield(
                    name=field_table.get_elem(fidx, fname_index) or '',
                    width=field_table.get_elem_int(fidx, fwidth_index),
                    offset=field_table.get_elem_int(fidx, bit_index),
                    value=field_table.get_elem(fidx, value_index),
                    desc=field_table.get_elem(fidx, fdesc_index),
                )
                cmd.fields.append(cf)

        command_maps.append(cmdmap)

    return command_maps
