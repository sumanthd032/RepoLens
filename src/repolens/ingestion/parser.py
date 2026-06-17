"""Tree-sitter source parser.

:class:`TreeSitterParser` turns a source file into a list of :class:`ParsedChunk` objects,
one per semantic unit (function, method, class, struct, interface, …). Each chunk carries the
metadata downstream stages need: file path, symbol name, symbol kind, signature, docstring,
body, 1-based line range, and language.

Grammars are loaded lazily and cached. A file in an unsupported language — or one where no
semantic node is found — falls back to a single whole-file chunk so nothing is silently
dropped from the index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from tree_sitter import Language, Node, Parser

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = get_logger("ingestion.parser")

# language name → (importable module name, attribute returning the grammar pointer)
_GRAMMAR_MODULES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "go": ("tree_sitter_go", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "rust": ("tree_sitter_rust", "language"),
    "c": ("tree_sitter_c", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "java": ("tree_sitter_java", "language"),
}

# Per-language map of definition node type → symbol kind. Only these node types are emitted
# as their own chunk; everything else is traversed through to reach nested definitions.
_DEFINITION_TYPES: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "type",
    },
    "javascript": {
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "method_definition": "method",
        "abstract_method_signature": "method",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "impl_item": "impl",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "struct",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "struct",
    },
    "java": {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "method_declaration": "method",
        "constructor_declaration": "constructor",
    },
}

# Symbol kinds that act as containers: we recurse into them to extract nested methods, and
# methods found inside a "class" container are re-labelled accordingly.
_CONTAINER_KINDS = {"class", "struct", "interface", "impl", "trait", "type", "enum"}
_CLASS_LIKE_KINDS = {"class", "struct", "interface"}

_WS_RE = re.compile(r"\s+")


@dataclass
class ParsedChunk:
    """A semantic unit extracted from a source file (pre-tokenisation)."""

    file_path: str
    symbol_name: str
    symbol_type: str
    signature: str
    docstring: str
    body: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    language: str


@cache
def load_language(language: str) -> Language | None:
    """Import and cache the tree-sitter grammar for ``language`` (``None`` if unavailable)."""
    spec = _GRAMMAR_MODULES.get(language)
    if spec is None:
        return None
    module_name, attr = spec
    try:
        module = __import__(module_name)
        return Language(getattr(module, attr)())
    except Exception as exc:  # pragma: no cover - missing optional grammar
        logger.warning("Could not load grammar for %s: %s", language, exc)
        return None


class TreeSitterParser:
    """Parses source files into :class:`ParsedChunk` objects."""

    def parse(self, file_path: str, content: str, language: str) -> list[ParsedChunk]:
        """Parse ``content`` and return its semantic chunks.

        Falls back to a single whole-file chunk when the language is unsupported or no
        definition nodes are found.
        """
        ts_language = load_language(language)
        if ts_language is None:
            return [self._whole_file_chunk(file_path, content, language)]

        source = content.encode("utf-8")
        parser = Parser(ts_language)
        tree = parser.parse(source)

        definitions = _DEFINITION_TYPES[language]
        chunks: list[ParsedChunk] = []
        for node, container_kind in self._descend(tree.root_node, definitions, None):
            chunk = self._build_chunk(node, file_path, source, language, container_kind)
            if chunk is not None:
                chunks.append(chunk)

        if not chunks:
            return [self._whole_file_chunk(file_path, content, language)]
        return chunks

    def _descend(
        self, node: Node, definitions: dict[str, str], container: str | None
    ) -> Iterator[tuple[Node, str | None]]:
        for child in node.named_children:
            kind = definitions.get(child.type)
            if kind is not None:
                yield child, container
                next_container = kind if kind in _CONTAINER_KINDS else container
                yield from self._descend(child, definitions, next_container)
            else:
                yield from self._descend(child, definitions, container)

    def _build_chunk(
        self,
        node: Node,
        file_path: str,
        source: bytes,
        language: str,
        container_kind: str | None,
    ) -> ParsedChunk | None:
        kind = _DEFINITION_TYPES[language][node.type]
        # A bare function/method living directly inside a class-like container is a method.
        if kind in {"function", "method"} and container_kind in _CLASS_LIKE_KINDS:
            kind = "method"

        name = self._extract_name(node, language, source)
        if name is None:
            name = "<anonymous>"

        body = _text(source, node)
        signature = self._extract_signature(node, source)
        docstring = self._extract_docstring(node, language, source)

        return ParsedChunk(
            file_path=file_path,
            symbol_name=name,
            symbol_type=kind,
            signature=signature,
            docstring=docstring,
            body=body,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language=language,
        )

    def _extract_name(self, node: Node, language: str, source: bytes) -> str | None:
        """Best-effort symbol name extraction, with language-specific fallbacks."""
        # Go wraps the real name inside a type_spec child.
        if language == "go" and node.type == "type_declaration":
            spec = _first_child_of_type(node, "type_spec")
            if spec is not None:
                name_node = spec.child_by_field_name("name")
                return _text(source, name_node) if name_node else None

        # C/C++ functions hold the name inside the declarator subtree.
        if node.type == "function_definition":
            ident = _find_declarator_identifier(node)
            if ident is not None:
                return _text(source, ident)

        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _text(source, name_node)

        # Generic fallback: first identifier-ish named child.
        for child in node.named_children:
            if child.type.endswith("identifier"):
                return _text(source, child)
        return None

    def _extract_signature(self, node: Node, source: bytes) -> str:
        """Return the declaration line(s): node start up to the body, whitespace-collapsed."""
        body_node = node.child_by_field_name("body")
        if body_node is not None:
            raw = source[node.start_byte : body_node.start_byte]
        else:
            # No body field (e.g. interface signatures): use the first physical line.
            raw = source[node.start_byte : node.end_byte].split(b"\n", 1)[0]
        text = raw.decode("utf-8", errors="replace").strip().rstrip("{(:").strip()
        return _WS_RE.sub(" ", text)

    def _extract_docstring(self, node: Node, language: str, source: bytes) -> str:
        """Extract a Python docstring or the leading comment block of other languages."""
        if language == "python":
            body = node.child_by_field_name("body")
            if body is not None and body.named_children:
                first = body.named_children[0]
                if first.type == "expression_statement" and first.named_children:
                    string_node = first.named_children[0]
                    if string_node.type == "string":
                        return _clean_python_docstring(_text(source, string_node))
            return ""
        return self._leading_comments(node, source)

    @staticmethod
    def _leading_comments(node: Node, source: bytes) -> str:
        """Collect contiguous comment siblings immediately preceding ``node``."""
        comments: list[str] = []
        sibling = node.prev_named_sibling
        while sibling is not None and "comment" in sibling.type:
            # Only adjacent comments (no blank-line gap) count as documentation.
            if sibling.end_point[0] < node.start_point[0] - len(comments) - 1:
                break
            comments.append(_text(source, sibling))
            sibling = sibling.prev_named_sibling
        return "\n".join(reversed(comments)).strip()

    @staticmethod
    def _whole_file_chunk(file_path: str, content: str, language: str) -> ParsedChunk:
        line_count = content.count("\n") + 1 if content else 1
        return ParsedChunk(
            file_path=file_path,
            symbol_name=file_path,
            symbol_type="file",
            signature="",
            docstring="",
            body=content,
            start_line=1,
            end_line=line_count,
            language=language,
        )


def _text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _first_child_of_type(node: Node, type_name: str) -> Node | None:
    for child in node.named_children:
        if child.type == type_name:
            return child
    return None


def _find_declarator_identifier(node: Node) -> Node | None:
    """Descend through C/C++ declarator nodes to find the function's identifier."""
    declarator = node.child_by_field_name("declarator")
    seen = 0
    while declarator is not None and seen < 8:
        if declarator.type in {"identifier", "field_identifier"}:
            return declarator
        nested = declarator.child_by_field_name("declarator")
        if nested is None:
            # qualified_identifier (Foo::bar) and similar: take the last identifier-ish leaf.
            for child in reversed(declarator.named_children):
                if child.type.endswith("identifier"):
                    return child
            return None
        declarator = nested
        seen += 1
    return None


def _clean_python_docstring(raw: str) -> str:
    """Strip surrounding quotes and prefixes from a Python string literal."""
    text = raw.strip()
    for prefix in ("r", "R", "u", "U", "b", "B", "f", "F"):
        if text.startswith(prefix):
            text = text[1:]
            break
    for quote in ('"""', "'''", '"', "'"):
        if text.startswith(quote) and text.endswith(quote) and len(text) >= 2 * len(quote):
            text = text[len(quote) : -len(quote)]
            break
    return text.strip()
