# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Martin Croome (croomem@essilor.fr)

"""Config field type aliases for register and command map lists.

These types implement ConfigFieldTypeAliasInterface so that Config subclasses
can declare register or command map fields that are loaded from a markdown file
path via cast() (e.g. Config.override_fields).
"""

from __future__ import annotations

import os
import sys
from typing import Any

from .field_type_alias import ConfigFieldTypeAliasInterface
from .md_parser import parse_cmdmaps, parse_document, parse_registers
from .register_types import Cmdmap, Register


class MarkdownFieldList(list, ConfigFieldTypeAliasInterface):
    """Base class for lists of dataclasses loaded from markdown documents.

    Subclasses must set the following class attributes:

    - ``_format_label``: human-readable plural noun used in ``format()``
      (e.g. ``"registers"``).
    - ``_item_type``: the expected element type for validation
      (e.g. ``Register``).
    - ``_error_noun``: noun used in error messages (e.g. ``"registers"``).

    Subclasses must also implement ``_parse_ast()`` to extract domain objects
    from a parsed markdown AST.
    """

    _format_label: str   # e.g. "registers", "command maps"
    _item_type: type     # e.g. Register, Cmdmap
    _error_noun: str     # e.g. "registers", "commands"

    # Per-subclass cache keyed by (cls, absolute_path_or_url) -> parsed items
    _file_cache: dict[tuple[type, str], list] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the parsed-file cache for all subclasses."""
        MarkdownFieldList._file_cache.clear()

    # -- helpers -------------------------------------------------------------

    @classmethod
    def _resolve_base_dir(cls, config: Any, field: Any = None) -> str | None:
        """Get the directory of the file that defines the typed cfg_field."""
        metadata = getattr(field, 'metadata', None)
        if metadata is not None and 'source_file' in metadata:
            source_dir = os.path.dirname(metadata['source_file'])
            return source_dir
        return None

    @classmethod
    def _parse_ast(cls, ast: Any) -> list:
        """Extract domain objects from a parsed markdown AST.

        Must be overridden by subclasses.
        """
        raise NotImplementedError(f"{cls.__name__} must implement _parse_ast()")

    # -- file loading --------------------------------------------------------

    @classmethod
    def load_from_file(cls, path: str, *, config: Any = None, field: Any = None) -> 'MarkdownFieldList':
        """Load items from one or more GFM markdown files.

        Supports:
        - Single file paths
        - Directory paths (loads all ``*.md`` files within)
        - Bang-URL redirects: if the first line of a file starts with ``!``,
          the remainder is treated as a URL (``http(s)://`` or ``file://``)
          pointing to the real content.
        - Relative path resolution against the directory of the file that defines the typed cfg_field.

        Args:
            path: File or directory path.
            config: Optional Config instance for relative-path resolution.
            field: Optional field instance for context.
        Returns:
            A new instance of the subclass populated with parsed items.

        Raises:
            ValueError: If the file cannot be read or parsed.
        """
        try:
            if not os.path.isabs(path):
                # This could be modified to allow Config or cfg_field-relative paths. For now only cfg_field-relative.
                base_dir = cls._resolve_base_dir(config, field)
                if base_dir:
                    path = os.path.join(base_dir, path)
            if os.path.isdir(path):
                paths = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.md')]
            else:
                paths = [path]
            result = cls()
            for p in paths:
                with open(p, 'rt') as fh:
                    line = fh.readline()
                    if line.startswith('!'):
                        # read the actual url from the first line if it starts with '!' (e.g. for generated files)
                        url = line[1:].strip()
                        # read file from the url (supports local files and http/https)
                        if url.startswith('http://') or url.startswith('https://'):
                            cache_key = (cls, url)
                            if cache_key in MarkdownFieldList._file_cache:
                                result.extend(MarkdownFieldList._file_cache[cache_key])
                                continue
                            import requests
                            response = requests.get(url)
                            response.raise_for_status()
                            ast = parse_document(response.text)
                            items = cls._parse_ast(ast)
                            MarkdownFieldList._file_cache[cache_key] = items
                            result.extend(items)
                            continue
                        elif url.startswith('file://'):
                            new_p = url[7:].strip()
                            if not os.path.isabs(new_p):
                                p = os.path.normpath(os.path.join(os.path.dirname(p), new_p))
                            else:
                                p = new_p
                        else:
                            raise ValueError(f'Unsupported URL scheme in {p!r}: {url!r}')

                cache_key = (cls, os.path.abspath(p))
                if cache_key in MarkdownFieldList._file_cache:
                    result.extend(MarkdownFieldList._file_cache[cache_key])
                    continue

                with open(p, 'rt') as fh:
                    ast = parse_document(fh.read())
                items = cls._parse_ast(ast)
                MarkdownFieldList._file_cache[cache_key] = items
                result.extend(items)
            return result
        except (OSError, RuntimeError) as exc:
            raise ValueError(
                f'Cannot load {cls._error_noun} from {path!r}: {exc}'
            ) from exc

    # -- ConfigFieldTypeAliasInterface ---------------------------------------

    @classmethod
    def format(cls, value: Any) -> str:
        if isinstance(value, list):
            return f'[{len(value)} {cls._format_label}]'
        return str(value)

    @classmethod
    def cast(cls, value: Any, field: Any, *, config: Any = None) -> 'MarkdownFieldList':
        if isinstance(value, list):
            result = cls()
            result.extend(value)
            return result
        return cls.load_from_file(str(value), config=config, field=field)

    @classmethod
    def validate(cls, value: Any, field: Any, *, config: Any = None) -> Any:
        if isinstance(value, str):
            return cls.cast(value, field, config=config)
        if not isinstance(value, list):
            raise ValueError(
                f'Expected a list of {cls._item_type.__name__}, '
                f'got {type(value).__name__}'
            )
        for item in value:
            if not isinstance(item, cls._item_type):
                raise ValueError(
                    f'Expected {cls._item_type.__name__} instances, '
                    f'got {type(item).__name__}'
                )
        return value

    @classmethod
    def check_annotation(cls, field_type: Any) -> bool:
        return field_type is cls


class RegisterList(MarkdownFieldList):
    """A list of Register dataclasses loaded from a markdown register-map document.

    Usage as a type annotation::

        class MyConfig(Config):
            registers: RegisterList = cfg_field(default_factory=RegisterList, desc="...")

    Usage via CLI override (loads from a file path)::

        Config.override_fields(["my_config/registers=/path/to/README.md"])
    """

    _format_label = 'registers'
    _item_type = Register
    _error_noun = 'registers'

    @classmethod
    def _parse_ast(cls, ast: Any) -> list:
        return parse_registers(ast)

    @classmethod
    def resolve_addresses(cls, config: Any) -> 'RegisterList':
        """Return a copy of this config's registers with resolved base addresses.

        Follows all links on *config* and filters for ``AddressMapping``
        instances.  Each mapping's ``base`` is collected and attached to
        every register as ``base_addresses``, so that the absolute address
        can be computed as ``base + offset``.

        Args:
            config: A Config instance whose ``registers`` field (a
                RegisterList) should be resolved.

        Returns:
            A new RegisterList with ``base_addresses`` populated on each
            Register.  If *config* has no AddressMapping links the
            registers are returned unchanged.
        """
        from .mappings import AddressMapping
        from dataclasses import replace as dc_replace

        mappings = config.get_mapped_by(AddressMapping)
        bases = [m.base for m in mappings if m.base is not None]

        # Find the RegisterList field value
        regs = None
        for f_name in ('registers',):
            val = getattr(config, f_name, None)
            if isinstance(val, cls):
                regs = val
                break
        if regs is None:
            return cls()

        if not bases:
            return regs

        result = cls()
        for reg in regs:
            result.append(dc_replace(reg, base_addresses=bases))
        return result


class CommandList(MarkdownFieldList):
    """A list of Cmdmap dataclasses loaded from a markdown register-map document.

    Usage as a type annotation::

        class MyConfig(Config):
            commands: CommandList = cfg_field(default_factory=CommandList, desc="...")

    Usage via CLI override (loads from a file path)::

        Config.override_fields(["my_config/commands=/path/to/README.md"])
    """

    _format_label = 'command maps'
    _item_type = Cmdmap
    _error_noun = 'commands'

    @classmethod
    def _parse_ast(cls, ast: Any) -> list:
        return parse_cmdmaps(ast)
