"""Unit tests for :class:`repolens.ingestion.graph.SymbolGraphBuilder`."""

from __future__ import annotations

from repolens.ingestion.chunker import SemanticChunker
from repolens.ingestion.graph import SymbolGraphBuilder
from repolens.ingestion.parser import TreeSitterParser

PY_SOURCE = '''\
def helper(x):
    return x + 1


def driver(y):
    """Calls helper twice."""
    a = helper(y)
    b = helper(a)
    return a + b


class Service:
    def run(self):
        return driver(10)
'''


def _chunks(source: str, language: str, path: str):
    parser = TreeSitterParser()
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64, min_tokens=1)
    return chunker.chunk_all(parser.parse(path, source, language))


def _id_of(chunks, symbol: str) -> str:
    return next(c.chunk_id for c in chunks if c.symbol_name == symbol)


def _edge_type(graph, src: str, dst: str) -> str | None:
    if graph.has_edge(src, dst):
        return graph.edges[src, dst]["type"]
    return None


def test_call_edges_between_functions() -> None:
    chunks = _chunks(PY_SOURCE, "python", "svc.py")
    graph = SymbolGraphBuilder().build(chunks)

    driver = _id_of(chunks, "driver")
    helper = _id_of(chunks, "helper")
    assert _edge_type(graph, driver, helper) == "calls"


def test_method_calls_module_function() -> None:
    chunks = _chunks(PY_SOURCE, "python", "svc.py")
    graph = SymbolGraphBuilder().build(chunks)

    run = _id_of(chunks, "run")
    driver = _id_of(chunks, "driver")
    assert _edge_type(graph, run, driver) == "calls"


def test_method_implements_enclosing_class() -> None:
    chunks = _chunks(PY_SOURCE, "python", "svc.py")
    graph = SymbolGraphBuilder().build(chunks)

    run = _id_of(chunks, "run")
    service = _id_of(chunks, "Service")
    assert _edge_type(graph, run, service) == "implements"


def test_no_spurious_self_call_edge() -> None:
    chunks = _chunks(PY_SOURCE, "python", "svc.py")
    graph = SymbolGraphBuilder().build(chunks)
    helper = _id_of(chunks, "helper")
    assert not graph.has_edge(helper, helper)


def test_all_chunks_become_nodes() -> None:
    chunks = _chunks(PY_SOURCE, "python", "svc.py")
    graph = SymbolGraphBuilder().build(chunks)
    assert graph.number_of_nodes() == len(chunks)
    for chunk in chunks:
        assert graph.nodes[chunk.chunk_id]["symbol"] == chunk.symbol_name


def test_go_method_and_call_edges() -> None:
    go_source = (
        "package main\n\n"
        "type Server struct{ port int }\n\n"
        "func dispatch(p string) error { return nil }\n\n"
        "func (s *Server) Start() error { return dispatch(\"/\") }\n"
    )
    chunks = _chunks(go_source, "go", "server.go")
    graph = SymbolGraphBuilder().build(chunks)

    start = _id_of(chunks, "Start")
    dispatch = _id_of(chunks, "dispatch")
    server = _id_of(chunks, "Server")
    assert _edge_type(graph, start, dispatch) == "calls"
    assert _edge_type(graph, start, server) == "implements"
