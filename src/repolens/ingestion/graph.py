"""Symbol graph builder.

:class:`SymbolGraphBuilder` constructs a directed graph whose nodes are ``chunk_id`` values
and whose edges capture relationships between symbols:

* ``calls`` — the chunk's body invokes another indexed function/method.
* ``implements`` — a method/function is contained within a class/struct/interface/etc.
  (derived from line-range containment, so it works across all languages).
* ``imports`` — the chunk imports a name that resolves to another indexed symbol.

Graph expansion at query time (Step 6) uses this to pull a matched symbol's callers, callees,
and enclosing type alongside the primary hit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
from tree_sitter import Node, Parser

from repolens.ingestion.parser import load_language
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.ingestion.chunker import IndexChunk

logger = get_logger("ingestion.graph")

# Call-expression node types per language, plus the field holding the callee.
_CALL_TYPES: dict[str, set[str]] = {
    "python": {"call"},
    "go": {"call_expression"},
    "javascript": {"call_expression"},
    "typescript": {"call_expression"},
    "rust": {"call_expression", "macro_invocation"},
    "c": {"call_expression"},
    "cpp": {"call_expression"},
    "java": {"method_invocation"},
}
# Field name carrying the called symbol; defaults to "function".
_CALLEE_FIELD: dict[str, str] = {"java": "name"}

# Import statement node types per language.
_IMPORT_TYPES: dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement"},
    "go": {"import_declaration"},
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
    "rust": {"use_declaration"},
    "java": {"import_declaration"},
}

_CALLABLE_KINDS = {"function", "method", "constructor"}
_CONTAINER_KINDS = {"class", "struct", "interface", "impl", "trait", "type", "enum"}


class SymbolGraphBuilder:
    """Builds a :class:`networkx.DiGraph` of symbol relationships from index chunks."""

    def build(self, chunks: list[IndexChunk]) -> nx.DiGraph:
        graph: nx.DiGraph = nx.DiGraph()
        for chunk in chunks:
            graph.add_node(
                chunk.chunk_id,
                symbol=chunk.symbol_name,
                type=chunk.symbol_type,
                file=chunk.file_path,
            )

        # Index callable symbols by name so call sites can be resolved to a chunk.
        name_index: dict[str, list[str]] = {}
        for chunk in chunks:
            if chunk.symbol_type in _CALLABLE_KINDS:
                name_index.setdefault(chunk.symbol_name, []).append(chunk.chunk_id)

        # Container symbols indexed by name, for receiver-based method linking (Go, …).
        container_index: dict[str, str] = {
            c.symbol_name: c.chunk_id for c in chunks if c.symbol_type in _CONTAINER_KINDS
        }

        self._add_containment_edges(graph, chunks)
        for chunk in chunks:
            self._add_call_edges(graph, chunk, name_index)
            self._add_import_edges(graph, chunk, name_index)
            self._add_receiver_edge(graph, chunk, container_index)
        return graph

    def _add_receiver_edge(
        self, graph: nx.DiGraph, chunk: IndexChunk, container_index: dict[str, str]
    ) -> None:
        """Link a Go method to its receiver type when the two aren't physically nested."""
        if chunk.language != "go" or chunk.symbol_type != "method":
            return
        tree = self._parse(chunk)
        if tree is None:
            return
        source = chunk.body.encode("utf-8")
        for node in self._iter_nodes(tree, {"method_declaration"}):
            receiver = node.child_by_field_name("receiver")
            type_node = _first_descendant(receiver, "type_identifier") if receiver else None
            if type_node is None:
                continue
            type_name = source[type_node.start_byte : type_node.end_byte].decode("utf-8", "replace")
            target = container_index.get(type_name)
            if target and target != chunk.chunk_id and not graph.has_edge(chunk.chunk_id, target):
                graph.add_edge(chunk.chunk_id, target, type="implements")

    def _add_call_edges(
        self, graph: nx.DiGraph, chunk: IndexChunk, name_index: dict[str, list[str]]
    ) -> None:
        call_types = _CALL_TYPES.get(chunk.language)
        if not call_types:
            return
        tree = self._parse(chunk)
        if tree is None:
            return
        field = _CALLEE_FIELD.get(chunk.language, "function")
        source = chunk.body.encode("utf-8")
        for node in self._iter_nodes(tree, call_types):
            callee = node.child_by_field_name(field)
            name = _last_identifier(callee, source)
            if name is None:
                continue
            for target in name_index.get(name, ()):
                if target != chunk.chunk_id:
                    graph.add_edge(chunk.chunk_id, target, type="calls")

    def _add_import_edges(
        self, graph: nx.DiGraph, chunk: IndexChunk, name_index: dict[str, list[str]]
    ) -> None:
        import_types = _IMPORT_TYPES.get(chunk.language)
        if not import_types:
            return
        tree = self._parse(chunk)
        if tree is None:
            return
        source = chunk.body.encode("utf-8")
        for node in self._iter_nodes(tree, import_types):
            for ident in _all_identifiers(node, source):
                for target in name_index.get(ident, ()):
                    if target != chunk.chunk_id:
                        graph.add_edge(chunk.chunk_id, target, type="imports")

    @staticmethod
    def _add_containment_edges(graph: nx.DiGraph, chunks: list[IndexChunk]) -> None:
        """Link a symbol to the smallest container that encloses it in the same file."""
        by_file: dict[str, list[IndexChunk]] = {}
        for chunk in chunks:
            by_file.setdefault(chunk.file_path, []).append(chunk)

        for file_chunks in by_file.values():
            containers = [c for c in file_chunks if c.symbol_type in _CONTAINER_KINDS]
            for chunk in file_chunks:
                if chunk.symbol_type not in _CALLABLE_KINDS:
                    continue
                parent = _smallest_enclosing(chunk, containers)
                if parent is not None:
                    graph.add_edge(chunk.chunk_id, parent.chunk_id, type="implements")

    @staticmethod
    def _parse(chunk: IndexChunk) -> Node | None:
        ts_language = load_language(chunk.language)
        if ts_language is None:
            return None
        parser = Parser(ts_language)
        return parser.parse(chunk.body.encode("utf-8")).root_node

    @staticmethod
    def _iter_nodes(root: Node, types: set[str]) -> list[Node]:
        found: list[Node] = []
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in types:
                found.append(node)
            stack.extend(node.children)
        return found


def _smallest_enclosing(chunk: IndexChunk, containers: list[IndexChunk]) -> IndexChunk | None:
    """Return the tightest container whose line range strictly encloses ``chunk``."""
    best: IndexChunk | None = None
    for container in containers:
        if container.chunk_id == chunk.chunk_id:
            continue
        if (
            container.start_line <= chunk.start_line
            and container.end_line >= chunk.end_line
            and (container.end_line - container.start_line)
            > (chunk.end_line - chunk.start_line)
        ):
            if best is None or (best.end_line - best.start_line) > (
                container.end_line - container.start_line
            ):
                best = container
    return best


def _first_descendant(node: Node, type_name: str) -> Node | None:
    """Return the first descendant of ``node`` whose type is ``type_name`` (DFS)."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == type_name:
            return current
        stack.extend(reversed(current.children))
    return None


def _last_identifier(node: Node | None, source: bytes) -> str | None:
    """Return the rightmost identifier text under ``node`` (the called symbol's name)."""
    if node is None:
        return None
    if node.type.endswith("identifier"):
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    last: str | None = None
    for child in node.named_children:
        if child.type.endswith("identifier"):
            last = source[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
        else:
            nested = _last_identifier(child, source)
            if nested is not None:
                last = nested
    return last


def _all_identifiers(node: Node, source: bytes) -> list[str]:
    out: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type.endswith("identifier"):
            out.append(source[current.start_byte : current.end_byte].decode("utf-8", "replace"))
        stack.extend(current.children)
    return out
