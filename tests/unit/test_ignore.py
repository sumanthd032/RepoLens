"""Unit tests for :class:`repolens.utils.ignore.IgnoreFilter`."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.utils.ignore import DEFAULT_PATTERNS, IgnoreFilter


@pytest.mark.parametrize(
    "path",
    [
        "vendor/lib/dep.go",
        "node_modules/left-pad/index.js",
        "dist/bundle.min.js",
        "pkg/util.generated.go",
        "src/api.pb.go",
        ".git/config",
        "src/__pycache__/main.cpython-311.pyc",
        # Regression: Python virtualenvs must be excluded by default, otherwise indexing a
        # repo with a local venv sweeps in tens of thousands of dependency files.
        "venv/lib/python3.14/site-packages/isympy.py",
        ".venv/lib/python3.12/site-packages/numpy/core/_methods.py",
        "env/lib/python3.11/site-packages/pkg/mod.py",
        "some/nested/site-packages/dep.py",
        "target/debug/build.rs",
    ],
)
def test_default_patterns_exclude_junk(path: str) -> None:
    flt = IgnoreFilter()
    assert flt.is_ignored(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "src/main.py",
        "src/router.go",
        "README.md",
        "pkg/handler.go",
    ],
)
def test_source_files_are_kept(path: str) -> None:
    flt = IgnoreFilter()
    assert flt.is_ignored(path) is False


def test_user_patterns_extend_defaults() -> None:
    flt = IgnoreFilter(["*.md", "secret/"])
    assert flt.is_ignored("README.md") is True
    assert flt.is_ignored("secret/key.txt") is True
    # Defaults still apply alongside user patterns.
    assert flt.is_ignored("vendor/x.go") is True
    assert flt.is_ignored("src/main.py") is False


def test_negation_reincludes_a_path() -> None:
    flt = IgnoreFilter(["!keep.generated.go"])
    assert flt.is_ignored("other.generated.go") is True
    assert flt.is_ignored("keep.generated.go") is False


def test_disabling_defaults() -> None:
    flt = IgnoreFilter(["*.log"], use_defaults=False)
    assert flt.patterns == ["*.log"]
    # Without defaults, vendor/ is no longer ignored.
    assert flt.is_ignored("vendor/x.go") is False
    assert flt.is_ignored("app.log") is True


def test_comments_and_blank_lines_are_skipped() -> None:
    flt = IgnoreFilter(["# a comment", "", "   ", "*.tmp"], use_defaults=False)
    assert flt.patterns == ["*.tmp"]
    assert flt.is_ignored("scratch.tmp") is True


def test_from_file_missing_falls_back_to_defaults(tmp_path: Path) -> None:
    flt = IgnoreFilter.from_file(tmp_path / "does-not-exist")
    assert flt.is_ignored("vendor/x.go") is True
    assert flt.is_ignored("src/main.py") is False


def test_from_file_reads_patterns(tmp_path: Path) -> None:
    ignore = tmp_path / ".repolensignore"
    ignore.write_text("*.csv\ndata/\n", encoding="utf-8")
    flt = IgnoreFilter.from_file(ignore)
    assert flt.is_ignored("rows.csv") is True
    assert flt.is_ignored("data/dump.json") is True
    assert flt.is_ignored("src/main.py") is False


def test_for_repo_loads_repo_ignore_file(temp_repo: Path) -> None:
    (temp_repo / ".repolensignore").write_text("*.md\n", encoding="utf-8")
    flt = IgnoreFilter.for_repo(temp_repo)
    assert flt.is_ignored("README.md") is True
    assert flt.is_ignored("vendor/lib/dep.go") is True
    assert flt.is_ignored("src/main.py") is False


def test_filter_returns_only_kept_paths() -> None:
    flt = IgnoreFilter()
    paths: list[str | Path] = [
        "src/main.py",
        "vendor/lib/dep.go",
        "README.md",
        "dist/bundle.min.js",
    ]
    assert flt.filter(paths) == ["src/main.py", "README.md"]


def test_paths_accept_pathlib_and_leading_dot_slash() -> None:
    flt = IgnoreFilter()
    assert flt.is_ignored(Path("vendor/lib/dep.go")) is True
    assert flt.is_ignored("./vendor/lib/dep.go") is True
    assert flt.is_ignored("./src/main.py") is False


def test_default_patterns_constant_is_nonempty() -> None:
    assert "vendor/" in DEFAULT_PATTERNS
    assert "node_modules/" in DEFAULT_PATTERNS
