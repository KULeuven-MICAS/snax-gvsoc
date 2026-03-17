# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Tree building and dumping utilities for Config instances.

This module provides functions to build rich Tree representations of Config
hierarchies for display purposes.
"""

from __future__ import annotations
from dataclasses import fields
from typing import Any, TYPE_CHECKING, get_type_hints

from rich.tree import Tree
from rich.table import Table

from .field_type_alias import ConfigFieldTypeAliasInterface, ConfigDumpable, get_field_alias_formatter
from .register_types import Register
from .utils import hex_grouped

if TYPE_CHECKING:
    from .config import Config


def _register_address_str(reg: Register, bases: list[int]) -> str:
    """Format resolved address(es) for a register given mapping base addresses."""
    if reg.offset is not None and bases:
        return ', '.join(f'0x{b + reg.offset:x}' for b in bases)
    return '-'


def _render_dumpable_item(
    parent: Tree, item: ConfigDumpable, expand: bool, bases: list[int] | None = None,
) -> None:
    """Render a single ConfigDumpable item as a sub-tree node under *parent*."""
    row = list(item.dump_row())
    headers = list(type(item).dump_headers())
    # Inject Address column for Registers when base addresses are available.
    if bases and isinstance(item, Register) and 'Offset' in headers:
        idx = headers.index('Offset')
        headers.insert(idx, 'Address')
        row.insert(idx, _register_address_str(item, bases))
    name = row[0] if row else '?'
    node = parent.add(f"[green]{name}[/green]")
    if len(headers) > 1:
        tbl = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
        for h in headers[1:]:
            tbl.add_column(h, style="cyan")
        tbl.add_row(*row[1:])
        node.add(tbl)
    if expand:
        children = item.dump_children()
        if children:
            child_headers = type(children[0]).dump_headers()
            tbl = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
            for h in child_headers:
                tbl.add_column(h, style="cyan")
            for child in children:
                tbl.add_row(*child.dump_row())
            node.add(tbl)


def build_config_tree(
    config: "Config",
    show_all: bool = False,
    expand_lists: bool = False,
) -> Tree:
    """
    Build a rich Tree representation of a Config and its children.

    Args:
        config: The Config instance to build a tree for.
        show_all: If True, show all fields; if False, only show fields with dump=True.
        expand_lists: If True, expand ConfigDumpable list items into per-item
            sub-trees with nested children (e.g. register fields, command fields).
            If False, each list is shown as a flat table of rows.

    Returns:
        A rich Tree object representing the config hierarchy.
    """
    if config.path == '/':
        tree = Tree("[bold cyan]/[/bold cyan]")
    else:
        config_label = f"/{config.label}" if config.label else ""
        config_path = f"{config.path}{config_label}"
        tree = Tree(f"[bold cyan]{config.__class__.__name__}[/bold cyan] [dim]({config_path})[/dim]")
    try:
        type_hints = get_type_hints(type(config), include_extras=True)
    except Exception:
        type_hints = {}

    field_rows = []
    child_configs = []
    tabular_children: dict[type, list["Config"]] = {}
    dumpable_lists: list[tuple[str, list[ConfigDumpable]]] = []

    # Import here to avoid circular import
    from .config import Config as ConfigClass

    for f in fields(config):
        if f.name in ('parent', 'name', 'path', 'children'):
            continue
        if not hasattr(config, f.name):
            continue
        value = getattr(config, f.name)
        if isinstance(value, ConfigClass):
            if value.parent is config:
                if getattr(type(value), 'dump_as_table', False):
                    tabular_children.setdefault(type(value), []).append(value)
                else:
                    child_configs.append(value)
            continue
        if isinstance(value, list) and value and isinstance(value[0], ConfigClass):
            child_configs.extend(value)
            continue
        if isinstance(value, list) and value and isinstance(value[0], ConfigDumpable):
            if show_all or config._field_flags.get(f.name, {}).get('read', False):
                dumpable_lists.append((f.name, value))
            continue
        row = config.dump_field_row(f, show_all=show_all, type_hints=type_hints)
        if row is not None:
            field_rows.append(row)

    if field_rows:
        table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
        for header, style in type(config).dump_columns():
            table.add_column(header, style=style)
        for row in field_rows:
            table.add_row(*row)
        tree.add(table)

    bases = config.base_addresses
    for field_name, items in dumpable_lists:
        sub = tree.add(f"[green]{field_name}[/green] [dim]({len(items)} items)[/dim]")
        if expand_lists:
            for item in items:
                _render_dumpable_item(sub, item, expand=True, bases=bases)
        else:
            headers = list(type(items[0]).dump_headers())
            has_addr = bases and items and isinstance(items[0], Register) and 'Offset' in headers
            if has_addr:
                addr_idx = headers.index('Offset')
                headers.insert(addr_idx, 'Address')
            tbl = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
            for h in headers:
                tbl.add_column(h, style="cyan")
            for item in items:
                row = list(item.dump_row())
                if has_addr:
                    row.insert(addr_idx, _register_address_str(item, bases))
                tbl.add_row(*row)
            sub.add(tbl)

    tabular_set = {c for group in tabular_children.values() for c in group}

    for child in config.children:
        if child in child_configs or child in tabular_set:
            continue
        if getattr(type(child), 'dump_as_table', False):
            tabular_children.setdefault(type(child), []).append(child)
            tabular_set.add(child)
        else:
            child_configs.append(child)

    # Render tabular Config children (classes with dump_as_table = True)
    for child_cls, children in tabular_children.items():
        label = child_cls.__name__
        sub = tree.add(f"[green]{label}[/green] [dim]({len(children)} items)[/dim]")
        try:
            child_type_hints = get_type_hints(child_cls, include_extras=True)
        except Exception:
            child_type_hints = {}
        # Determine which fields to show as columns by probing the first child
        col_fields = []
        for f in fields(children[0]):
            row = children[0].dump_field_row(f, show_all=show_all, type_hints=child_type_hints)
            if row is not None:
                col_fields.append(f)
        tbl = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
        tbl.add_column("Name", style="green")
        for f in col_fields:
            tbl.add_column(f.name, style="cyan")
        for child in children:
            values = []
            for f in col_fields:
                row = child.dump_field_row(f, show_all=show_all, type_hints=child_type_hints)
                values.append(row[2] if row else "-")
            tbl.add_row(child.name, *values)
        sub.add(tbl)

    for child in child_configs:
        child_tree = build_config_tree(child, show_all=show_all, expand_lists=expand_lists)
        tree.add(child_tree)

    return tree


def format_value(value: Any, fmt: str | None, field_name: str, type_hints: dict) -> str:
    """
    Format a field value for display in the config tree.

    Args:
        value: The value to format.
        fmt: Optional format string (e.g., "hex").
        field_name: Name of the field (for type hint lookup).
        type_hints: Dictionary of type hints for the config class.

    Returns:
        Formatted string representation of the value.
    """
    if isinstance(value, ConfigFieldTypeAliasInterface):
        return str(value)

    formatter = None
    if field_name in type_hints:
        formatter = get_field_alias_formatter(type_hints[field_name])

    if formatter and isinstance(value, int):
        return formatter.format(value)
    elif fmt == "hex" and isinstance(value, int):
        return hex_grouped(value)
    elif value is None:
        return "[dim]not set[/dim]"
    elif isinstance(value, bool):
        return "[green]True[/green]" if value else "[red]False[/red]"
    elif isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, (list, tuple, set)):
        if len(value) == 0:
            return "[]" if isinstance(value, list) else "()" if isinstance(value, tuple) else "{}"
        elif len(value) <= 3:
            return str(value)
        else:
            return f"[{len(value)} items]"
    elif isinstance(value, dict):
        if len(value) == 0:
            return "{}"
        elif len(value) <= 3:
            return str(value)
        else:
            return f"{{{len(value)} items}}"
    else:
        return str(value)
