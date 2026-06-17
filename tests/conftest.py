"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a tiny fake repository tree on disk and return its root.

    The layout mixes source files that should be indexed with directories and generated
    files that a ``.repolensignore`` is expected to exclude, so it doubles as a fixture for
    walker/ignore tests in later steps.
    """
    files = {
        "src/main.py": "def main():\n    return 0\n",
        "src/router.go": "package main\n\nfunc handleRoute() {}\n",
        "src/api.pb.go": "// generated protobuf\n",
        "pkg/util.generated.go": "// generated\n",
        "vendor/lib/dep.go": "package lib\n",
        "node_modules/left-pad/index.js": "module.exports = () => {}\n",
        "dist/bundle.min.js": "console.log(1)\n",
        "README.md": "# Demo\n",
    }
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def cache_dir(tmp_path: Path) -> Iterator[Path]:
    """A clean directory for :class:`~repolens.utils.cache.DiskCache` tests."""
    target = tmp_path / "cache"
    yield target
