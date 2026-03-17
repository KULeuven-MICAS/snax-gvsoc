# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Martin Croome (croomem@essilor.fr)

"""Generate C ``#define`` headers from the Config tree.

Provides an abstract :class:`ConfigTreeHeaderWalker` that walks the config
tree, accumulates a hierarchical prefix, and calls an abstract method for
each matching node.  Two concrete implementations are supplied:

* :class:`MemoryMapHeaderGen` — emits ``_BASE``, ``_OFFSET``, and ``_SIZE``
  constants for :class:`MemoryMapped` nodes.
* :class:`IrqHeaderGen` — emits IRQ number constants for :class:`HasIrq`
  nodes whose fields use the :class:`IrqNumber` type alias.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import fields
from datetime import datetime
from typing import Any

from code_block import CodeBlock

from .config import Config, HasIrq, MemoryMapped
from .field_type_alias import IrqNumber

HEADER = f"""/* SPDX-FileCopyrightText: {datetime.now().year}, ETH Zurich, University of Bologna and EssilorLuxottica SAS
*
* SPDX-License-Identifier: Apache-2.0
*
* THIS FILE HAS BEEN GENERATED, DO NOT MODIFY IT.
*/
"""


def _hex(value: int, width: int = 8) -> str:
    """Format an integer as a zero-padded hex literal."""
    return f'0x{value:0{width}x}'


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ConfigTreeHeaderWalker(ABC):
    """Walk a Config tree and emit C ``#define`` headers.

    Subclasses implement :meth:`_node_filter` to select which nodes to
    process and :meth:`_process_node` to emit defines for each matching
    node together with its direct matching children.

    The walker accumulates a hierarchical prefix as it recurses.  A node
    with a ``label`` resets the prefix to that label (uppercased).

    A *has_parent* flag is threaded through recursion so that
    implementations can distinguish top-level nodes from nested ones.

    Args:
        root: The root Config to start traversal from.
        prefix: Initial prefix for define names (defaults to the first
                matching node's label or name, uppercased).
        recurse: If True, recursively walk into matching children.
    """

    def __init__(self, root: Config, *, prefix: str | None = None, recurse: bool = True):
        self._root = root
        self._prefix = prefix.upper() if prefix else None
        self._recurse = recurse
        self._cb = CodeBlock()
        self._visited: set[int] = set()
        self._emitted_names: set[str] = set()

    # -- public API ----------------------------------------------------------

    def generate(self) -> str:
        """Generate a standalone header (with preamble) and return as a string."""
        self._cb.write(HEADER)
        self._cb.write('#pragma once')
        self._cb.nl()
        self._generate_body()
        self._cb.nl()
        return str(self._cb)

    def generate_to(self, cb: CodeBlock) -> None:
        """Emit defines into an external *cb* (no header/footer)."""
        self._cb = cb
        self._generate_body()

    # -- abstract interface --------------------------------------------------

    @abstractmethod
    def _node_filter(self, node: Config) -> bool:
        """Return ``True`` if *node* should be processed by this walker."""

    @abstractmethod
    def _process_node(
        self,
        node: Config,
        prefix: str,
        children: list[Config],
        has_parent: bool,
    ) -> None:
        """Process *node* with accumulated *prefix*.

        *children* contains the direct children of *node* that also pass
        :meth:`_node_filter`.  *has_parent* is ``False`` for top-level
        matches and ``True`` when the node is nested inside another match.
        """

    # -- hooks ---------------------------------------------------------------

    def _post_walk(self) -> None:
        """Called after the tree walk completes (e.g. for deferred output)."""

    # -- tree walking --------------------------------------------------------

    def _generate_body(self) -> None:
        """Find top-level matching nodes and walk each sub-tree."""
        for node in self._root.find_from(
            fn=self._node_filter,
            direct_only=True,
        ):
            if id(node) in self._visited:
                continue
            if self._prefix is None:
                prefix = (node.label if node.label is not None else node.name).upper()
            else:
                prefix = self._prefix
            self._walk(node, prefix)

        self._post_walk()

    def _walk(self, node: Config, prefix: str, has_parent: bool = False) -> None:
        """Recursively walk *node*, calling :meth:`_process_node` at each level."""
        node_id = id(node)
        if node_id in self._visited:
            return
        self._visited.add(node_id)

        children: list[Config] = list(node.find_from(
            fn=lambda c: c is not node and self._node_filter(c),
            direct_only=True,
        ))

        self._process_node(node, prefix, children, has_parent)

        if not self._recurse:
            return

        for child in children:
            if id(child) in self._visited:
                continue
            child_alias = f'{prefix}_{child.name}'.upper()
            child_prefix = self._resolve_prefix(child, child_alias)
            self._walk(child, child_prefix, has_parent=True)

    # -- prefix helpers ------------------------------------------------------

    def _resolve_prefix(self, target: Config, fallback: str) -> str:
        """Return *target*'s label (uppercased) if set, else *fallback*."""
        label = getattr(target, 'label', None)
        if label:
            return label.upper()
        return fallback

    def _has_matching_children(self, node: Config) -> bool:
        """Return ``True`` if *node* has any children passing the filter."""
        for _ in node.find_from(
            fn=lambda c: c is not node and self._node_filter(c),
            direct_only=True,
        ):
            return True
        return False

    # -- emit helpers --------------------------------------------------------

    def _emit_define(
        self,
        name: str,
        value: str,
        *,
        comment: str | None = None,
    ) -> None:
        """Emit a single ``#define`` line, skipping duplicates."""
        if name in self._emitted_names:
            return
        self._emitted_names.add(name)

        pad = max(32, len(name) + 2)
        define = f'#define {name:<{pad}s}( {value} )'
        if comment:
            define = f'{define}  /* {comment} */'
        self._cb.write_raw(define)


# ---------------------------------------------------------------------------
# MemoryMapped implementation
# ---------------------------------------------------------------------------

class MemoryMapHeaderGen(ConfigTreeHeaderWalker):
    """Generate a C memory-map header by walking ``MemoryMapped`` configs.

    Emits ``_BASE``, ``_OFFSET``, and ``_SIZE`` defines.  When a child is
    nested inside another ``MemoryMapped``, the child's ``_BASE`` is
    expressed as ``PARENT_BASE + CHILD_OFFSET`` with the resolved literal
    in a trailing comment.

    Children must have addresses within the parent's range; a
    ``ValueError`` is raised otherwise.

    Args:
        root: The root Config to start traversal from.
        prefix: Initial prefix for define names.
        recurse: If True, recursively walk into ``MemoryMapped`` children.
    """

    # -- abstract overrides --------------------------------------------------

    def _node_filter(self, node: Config) -> bool:
        return isinstance(node, MemoryMapped)

    def _process_node(
        self,
        node: Config,
        prefix: str,
        children: list[Config],
        has_parent: bool,
    ) -> None:
        if not children:
            return

        # Section comment
        self._cb.write('/*')
        self._cb.write(f' * {node.name}')
        self._cb.write(' */')

        # Build entries for each child
        entries: list[dict] = []
        for child in children:
            child_alias = f'{prefix}_{child.name}'.upper() if prefix else child.name.upper()
            child_base: int = getattr(child, 'base', 0) or 0
            child_size: int = getattr(child, 'size', 0) or 0
            entries.append({
                'node': child,
                'alias': child_alias,
                'base_value': child_base,
                'size_value': child_size,
            })

        if has_parent:
            node_base: int = getattr(node, 'base', 0) or 0
            parent_base_name = f'{prefix}_BASE'

            # Emit all offsets
            for entry in entries:
                offset = entry['base_value'] - node_base
                if offset < 0:
                    raise ValueError(
                        f"{entry['node'].name} base {_hex(entry['base_value'])} "
                        f"is outside parent {node.name} base {_hex(node_base)}"
                    )
                entry['offset_name'] = f'{entry["alias"]}_OFFSET'
                self._emit_define(entry['offset_name'], _hex(offset))

            self._cb.nl()

            # Emit BASE expressions, sizes, and label aliases
            for entry in entries:
                addr_name = f'{entry["alias"]}_BASE'
                resolved = _hex(entry['base_value'])
                expr = f'{parent_base_name} + {entry["offset_name"]}'
                self._emit_define(addr_name, expr, comment=resolved)
                self._emit_size(entry)
                self._emit_label_aliases(entry)
        else:
            # Top-level: emit BASE defines directly
            for entry in entries:
                addr_name = f'{entry["alias"]}_BASE'
                self._emit_define(addr_name, _hex(entry['base_value']))
                self._emit_size(entry)
                self._emit_label_aliases(entry)

        self._cb.nl()

    def _emit_size(self, entry: dict) -> None:
        """Emit a ``_SIZE`` define for an entry."""
        size = entry['size_value']
        if size:
            self._emit_define(f'{entry["alias"]}_SIZE', _hex(size))

    def _emit_label_aliases(self, entry: dict) -> None:
        """Emit label-scoped alias defines (``_BASE``, ``_SIZE``) when the node has a label."""
        node = entry['node']
        label = getattr(node, 'label', None)
        if not label:
            return
        lp = label.upper()
        alias = entry['alias']
        if lp == alias:
            return
        self._emit_define(f'{lp}_BASE', f'{alias}_BASE')
        size_name = f'{alias}_SIZE'
        if size_name in self._emitted_names:
            self._emit_define(f'{lp}_SIZE', size_name)


# ---------------------------------------------------------------------------
# HasIrq implementation
# ---------------------------------------------------------------------------

class IrqHeaderGen(ConfigTreeHeaderWalker):
    """Generate C ``#define`` headers for IRQ numbers from ``HasIrq`` configs.

    For each :class:`HasIrq` node in the tree, emits a ``#define`` for every
    field whose type is :data:`IrqNumber`.  The define name is built from
    the accumulated prefix and the field name.

    Args:
        root: The root Config to start traversal from.
        prefix: Initial prefix for define names.
        recurse: If True, recursively walk into ``HasIrq`` children.
    """

    def _node_filter(self, node: Config) -> bool:
        return isinstance(node, HasIrq)

    def _process_node(
        self,
        node: Config,
        prefix: str,
        children: list[Config],
        has_parent: bool,
    ) -> None:
        for f in fields(node):
            if f.type is IrqNumber:
                value = getattr(node, f.name)
                if value is not None:
                    define_name = f'{prefix}_{f.name}'.upper()
                    self._emit_define(define_name, str(value))


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def generate_memory_map(
    root: Config,
    output_path: str | None = None,
    *,
    prefix: str | None = None,
    recurse: bool = True,
) -> str:
    """Generate a C memory-map header from a Config tree.

    Walks the tree finding :class:`MemoryMapped` instances and emits
    ``#define`` lines for addresses, sizes, and offsets.

    Args:
        root: The root Config to start traversal from.
        output_path: If provided, write the header to this file path.
        prefix: Initial prefix for define names.
        recurse: If True, recurse into MemoryMapped children.

    Returns:
        The generated header content as a string.
    """

    gen = MemoryMapHeaderGen(root, prefix=prefix, recurse=recurse)
    content = gen.generate()

    if output_path is not None:
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as fh:
            fh.write(content)

    return content


def generate_irq_header(
    root: Config,
    output_path: str | None = None,
    *,
    prefix: str | None = None,
    recurse: bool = True,
) -> str:
    """Generate a C IRQ-number header from a Config tree.

    Walks the tree finding :class:`HasIrq` instances and emits ``#define``
    lines for each :data:`IrqNumber` field.

    Args:
        root: The root Config to start traversal from.
        output_path: If provided, write the header to this file path.
        prefix: Initial prefix for define names.
        recurse: If True, recurse into HasIrq children.

    Returns:
        The generated header content as a string.
    """

    gen = IrqHeaderGen(root, prefix=prefix, recurse=recurse)
    content = gen.generate()

    if output_path is not None:
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as fh:
            fh.write(content)

    return content
