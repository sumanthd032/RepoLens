"""Unit tests for :class:`repolens.utils.cache.DiskCache`."""

from __future__ import annotations

from pathlib import Path

from repolens.utils.cache import DiskCache


def test_make_key_is_sha256_and_stable() -> None:
    key1 = DiskCache.make_key("hello world")
    key2 = DiskCache.make_key(b"hello world")
    assert key1 == key2
    assert len(key1) == 64
    assert key1 != DiskCache.make_key("hello world!")


def test_set_then_get_roundtrips_value(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    key = DiskCache.make_key("chunk-body")
    cache.set(key, {"vector": [1, 2, 3], "symbol": "handleRoute"})
    assert cache.get(key) == {"vector": [1, 2, 3], "symbol": "handleRoute"}


def test_hit_and_miss_counters(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    key = DiskCache.make_key("payload")

    assert cache.get(key) is None  # miss
    assert cache.misses == 1
    assert cache.hits == 0

    cache.set(key, 42)
    assert cache.get(key) == 42  # hit
    assert cache.get(key) == 42  # hit
    assert cache.hits == 2
    assert cache.misses == 1


def test_has_does_not_affect_counters(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    key = DiskCache.make_key("x")
    assert cache.has(key) is False
    cache.set(key, "y")
    assert cache.has(key) is True
    assert cache.hits == 0
    assert cache.misses == 0


def test_get_default_on_miss(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    assert cache.get("absent", default="fallback") == "fallback"


def test_invalidate_removes_entry(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    key = DiskCache.make_key("doomed")
    cache.set(key, "value")
    assert cache.invalidate(key) is True
    assert cache.has(key) is False
    assert cache.invalidate(key) is False  # already gone


def test_clear_empties_cache_and_resets_stats(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    cache.set(DiskCache.make_key("a"), 1)
    cache.set(DiskCache.make_key("b"), 2)
    cache.get(DiskCache.make_key("a"))
    cache.clear()
    assert cache.get(DiskCache.make_key("a")) is None
    assert cache.hits == 0
    # the post-clear miss above increments misses
    assert cache.misses == 1


def test_get_or_set_computes_once(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    calls = {"n": 0}

    def factory() -> str:
        calls["n"] += 1
        return "computed"

    key = DiskCache.make_key("lazy")
    assert cache.get_or_set(key, factory) == "computed"
    assert cache.get_or_set(key, factory) == "computed"
    assert calls["n"] == 1  # second call served from cache


def test_corrupt_entry_is_treated_as_miss(cache_dir: Path) -> None:
    cache = DiskCache(cache_dir)
    key = DiskCache.make_key("broken")
    cache.set(key, "good")
    # Corrupt the on-disk pickle.
    (cache.directory / f"{key}.pkl").write_bytes(b"not a pickle")
    assert cache.get(key) is None
    assert cache.misses == 1
    assert cache.has(key) is False  # corrupt entry was removed


def test_invalidation_on_content_change(cache_dir: Path) -> None:
    """A changed chunk body produces a new key, so stale embeddings are not reused."""
    cache = DiskCache(cache_dir)
    old_key = DiskCache.make_key("def f(): return 1")
    cache.set(old_key, "embedding-v1")

    new_key = DiskCache.make_key("def f(): return 2")
    assert new_key != old_key
    assert cache.get(new_key) is None  # content changed → cache miss → re-embed


def test_namespaces_are_isolated(tmp_path: Path) -> None:
    embeddings = DiskCache(tmp_path, namespace="embeddings")
    claims = DiskCache(tmp_path, namespace="claims")
    key = DiskCache.make_key("shared")
    embeddings.set(key, "emb")
    assert claims.get(key) is None
    assert embeddings.directory != claims.directory
