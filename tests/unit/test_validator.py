"""Unit tests for citation parsing and validation (Invariant 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.generation.validator import (
    Citation,
    CitationValidator,
    parse_citations,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "router.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 11)) + "\n", encoding="utf-8"
    )
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "auth.py").write_text(
        "def hash_password(pw):\n    return pw[::-1]\n", encoding="utf-8"
    )
    return tmp_path


# --- parse_citations ----------------------------------------------------------


def test_parse_citations_extracts_ranges_and_single_lines() -> None:
    text = "Routing is handled here [router.py:1-5]. Auth lives there [pkg/auth.py:2]."
    cites = parse_citations(text)
    assert cites == [
        Citation("router.py", 1, 5),
        Citation("pkg/auth.py", 2, 2),
    ]


def test_parse_citations_deduplicates() -> None:
    text = "A [router.py:1-5]. B [router.py:1-5]."
    assert len(parse_citations(text)) == 1


def test_parse_citations_none_when_absent() -> None:
    assert parse_citations("no citations here at all") == []


# --- CitationValidator --------------------------------------------------------


def test_valid_citation_passes(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate("Routing is defined here [router.py:1-5].")
    assert result.ok
    assert result.invalid_citations == []
    assert result.checks[0].exists


def test_out_of_range_line_is_caught(repo: Path) -> None:
    # router.py has 10 lines; line 999 must be rejected (the definition-of-done case).
    validator = CitationValidator(repo)
    result = validator.validate("This is wrong [router.py:999].")
    assert not result.ok
    assert Citation("router.py", 999, 999) in result.invalid_citations
    assert "outside" in result.checks[0].reason


def test_end_past_eof_is_caught(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate("Spills over [router.py:8-50].")
    assert not result.ok
    assert result.checks[0].exists is False


def test_missing_file_is_caught(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate("Ghost file [does_not_exist.py:1-2].")
    assert not result.ok
    assert result.checks[0].reason == "file not found"


def test_inverted_range_is_caught(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate("Backwards [router.py:5-2].")
    assert not result.ok


def test_no_citations_rejected(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate("An answer with no citations whatsoever.")
    assert not result.ok
    assert "no citations" in result.reason.lower()


def test_similarity_reflects_overlap(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate(
        "The hash_password function reverses the pw value [pkg/auth.py:1-2]."
    )
    assert result.ok
    # Sentence shares identifiers (hash_password, pw) with the cited code → non-zero similarity.
    assert result.checks[0].similarity > 0.0


def test_mixed_valid_and_invalid(repo: Path) -> None:
    validator = CitationValidator(repo)
    result = validator.validate(
        "Good [router.py:1-3]. Bad [router.py:900-905]."
    )
    assert not result.ok
    assert len(result.invalid_citations) == 1
    assert result.invalid_citations[0].start == 900
