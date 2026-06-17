"""Unit tests for :class:`repolens.ingestion.parser.TreeSitterParser`."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.ingestion.parser import ParsedChunk, TreeSitterParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def parser() -> TreeSitterParser:
    return TreeSitterParser()


def _by_name(chunks: list[ParsedChunk]) -> dict[str, ParsedChunk]:
    return {c.symbol_name: c for c in chunks}


def test_parse_python_extracts_symbols(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.py").read_text(encoding="utf-8")
    chunks = parser.parse("sample.py", source, "python")
    by_name = _by_name(chunks)

    assert "top_level" in by_name
    assert by_name["top_level"].symbol_type == "function"
    assert "Greeter" in by_name
    assert by_name["Greeter"].symbol_type == "class"
    # Methods inside the class are labelled "method", not "function".
    assert by_name["greet"].symbol_type == "method"
    assert by_name["__init__"].symbol_type == "method"


def test_python_line_numbers_are_one_based_and_correct(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.py").read_text(encoding="utf-8")
    chunks = parser.parse("sample.py", source, "python")
    top = _by_name(chunks)["top_level"]

    lines = source.splitlines()
    # The reported start line should actually contain the def.
    assert lines[top.start_line - 1].lstrip().startswith("def top_level")
    assert top.start_line < top.end_line
    # Body text matches the cited line range.
    assert top.body == "\n".join(lines[top.start_line - 1 : top.end_line])


def test_python_docstring_and_signature(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.py").read_text(encoding="utf-8")
    by_name = _by_name(parser.parse("sample.py", source, "python"))

    assert by_name["top_level"].docstring == "Add two integers."
    assert by_name["top_level"].signature == "def top_level(a: int, b: int) -> int"
    assert by_name["Greeter"].docstring == "Greets people by name."


def test_parse_go_extracts_symbols(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.go").read_text(encoding="utf-8")
    by_name = _by_name(parser.parse("sample.go", source, "go"))

    assert by_name["handleRoute"].symbol_type == "function"
    assert by_name["Start"].symbol_type == "method"
    assert by_name["Server"].symbol_type == "type"
    assert by_name["Router"].symbol_type == "type"


def test_go_leading_comment_becomes_docstring(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.go").read_text(encoding="utf-8")
    by_name = _by_name(parser.parse("sample.go", source, "go"))

    assert "processes a single route" in by_name["handleRoute"].docstring
    assert by_name["handleRoute"].signature.startswith("func handleRoute(path string)")


def test_unsupported_language_falls_back_to_whole_file(parser: TreeSitterParser) -> None:
    chunks = parser.parse("notes.txt", "line one\nline two\n", "plaintext")
    assert len(chunks) == 1
    assert chunks[0].symbol_type == "file"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3


def test_file_with_no_symbols_falls_back_to_whole_file(parser: TreeSitterParser) -> None:
    chunks = parser.parse("consts.py", "X = 1\nY = 2\n", "python")
    assert len(chunks) == 1
    assert chunks[0].symbol_type == "file"


def test_all_chunks_carry_file_and_language(parser: TreeSitterParser) -> None:
    source = (FIXTURES / "sample.py").read_text(encoding="utf-8")
    for chunk in parser.parse("sample.py", source, "python"):
        assert chunk.file_path == "sample.py"
        assert chunk.language == "python"
        assert chunk.body
