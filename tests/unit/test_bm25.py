"""Unit tests for :class:`repolens.ingestion.bm25.BM25Indexer`."""

from __future__ import annotations

from pathlib import Path

from repolens.ingestion.bm25 import BM25Indexer, tokenize_code
from repolens.ingestion.chunker import IndexChunk, count_tokens


def _chunk(symbol: str, body: str, signature: str = "") -> IndexChunk:
    return IndexChunk(
        file_path=f"{symbol}.go",
        symbol_name=symbol,
        symbol_type="function",
        signature=signature,
        docstring="",
        body=body,
        start_line=1,
        end_line=1 + body.count("\n"),
        language="go",
        token_count=count_tokens(body),
    )


def _corpus() -> list[IndexChunk]:
    return [
        _chunk("handleRoute", "func handleRoute(path string) error { return dispatch(path) }"),
        _chunk("parseConfig", "func parseConfig(data []byte) Config { return decode(data) }"),
        _chunk("Logger", "type Logger struct { level int }"),
    ]


def test_tokenizer_splits_camel_and_snake_case() -> None:
    assert tokenize_code("handleRoute") == ["handle", "route"]
    assert tokenize_code("parse_config_file") == ["parse", "config", "file"]
    assert tokenize_code("HTTPServer") == ["http", "server"]
    assert tokenize_code("parseURL2") == ["parse", "url", "2"]


def test_search_finds_camelcase_symbol_from_spaced_query() -> None:
    chunks = _corpus()
    indexer = BM25Indexer()
    indexer.build(chunks)
    results = indexer.search("handle route", top_k=3)
    assert results, "expected at least one hit"
    assert results[0][0] == chunks[0].chunk_id  # handleRoute


def test_search_ranks_relevant_chunk_first() -> None:
    chunks = _corpus()
    indexer = BM25Indexer()
    indexer.build(chunks)
    results = indexer.search("parse config", top_k=3)
    assert results
    best_id = results[0][0]
    assert best_id == chunks[1].chunk_id  # parseConfig


def test_scores_are_positive_and_sorted_descending() -> None:
    indexer = BM25Indexer()
    indexer.build(_corpus())
    results = indexer.search("handle route", top_k=3)
    scores = [s for _, s in results]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_empty_query_and_empty_index() -> None:
    indexer = BM25Indexer()
    indexer.build([])
    assert indexer.search("anything") == []

    indexer2 = BM25Indexer()
    indexer2.build(_corpus())
    assert indexer2.search("") == []
    # A query with no shared terms returns nothing (non-positive scores filtered).
    assert indexer2.search("xyzzy quux") == []


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    chunks = _corpus()
    indexer = BM25Indexer()
    indexer.build(chunks)
    path = indexer.save(tmp_path / "bm25.pkl")
    assert path.is_file()

    loaded = BM25Indexer.load(path)
    assert loaded.size == len(chunks)
    assert loaded.chunk_ids == [c.chunk_id for c in chunks]
    # Same query gives the same top result after a round-trip.
    assert loaded.search("parse config")[0][0] == indexer.search("parse config")[0][0]
