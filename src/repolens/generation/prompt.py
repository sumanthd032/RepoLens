"""Grounded prompt construction.

The system prompt is RepoLens's grounding contract turned into instructions: answer only from the
supplied code, cite every sentence with a ``[path:start-end]`` span copied from the context, and
emit a fixed not-found marker when the context is insufficient rather than answering from memory.
:func:`build_user_message` lays out the retrieved chunks so each one's exact citable span is
visible for the model to copy verbatim — which is what makes the Step-7 citation validator able
to re-open and verify every span.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repolens.ingestion.chunker import IndexChunk

# Emitted verbatim by the model when retrieval context cannot answer the question. The API layer
# detects this marker and returns a structured "not found" response (Invariant 3).
NOT_FOUND_MARKER = "NOT_FOUND_IN_CODEBASE"

_SYSTEM_PROMPT = f"""\
You are RepoLens, a code comprehension assistant. You answer questions about ONE specific \
repository using ONLY the code excerpts provided in the user message. You have no other \
knowledge of this repository.

Rules — follow every one:
1. Use ONLY the provided code excerpts. Never use prior knowledge of this or any library, and \
never invent files, symbols, or behaviour that is not present in the excerpts.
2. Every sentence you write MUST end with one or more citations of the form [path:start-end], \
copied exactly from the excerpt headers (e.g. [src/router.py:42-67]). A sentence without a \
citation is not allowed.
3. Cite only spans that actually appear in the provided excerpts. Do not alter the line numbers.
4. If the excerpts do not contain enough information to answer, reply with exactly this single \
line and nothing else:
{NOT_FOUND_MARKER}
5. Be concise and technical. Prefer explaining what the code does over restating the question.
"""

_CHUNK_TEMPLATE = """\
[{path}:{start}-{end}]  {symbol} ({symbol_type}, {language})
{body}"""


def build_system_prompt() -> str:
    """Return the grounded system prompt (citations required, null path defined)."""
    return _SYSTEM_PROMPT


def format_chunk(chunk: IndexChunk) -> str:
    """Render a single chunk with its citable span header for the prompt."""
    return _CHUNK_TEMPLATE.format(
        path=chunk.file_path,
        start=chunk.start_line,
        end=chunk.end_line,
        symbol=chunk.symbol_name or "<module>",
        symbol_type=chunk.symbol_type,
        language=chunk.language,
        body=chunk.body,
    )


def build_user_message(query: str, chunks: list[IndexChunk]) -> str:
    """Format the retrieved ``chunks`` followed by ``query`` into the user message."""
    if not chunks:
        excerpts = "(no code excerpts were retrieved)"
    else:
        excerpts = "\n\n".join(format_chunk(c) for c in chunks)
    return (
        "Code excerpts from the repository:\n\n"
        f"{excerpts}\n\n"
        "----\n"
        f"Question: {query}\n\n"
        "Answer using only the excerpts above, citing [path:start-end] after every sentence."
    )
