"""Drift checking.

For each documentation claim, :class:`DriftChecker` retrieves the code most relevant to it and
runs NLI to decide whether the code **supports**, **contradicts**, or simply does **not_found**
(does not address) the claim. Retrieval reuses the exact Step-6 hybrid engine, so a claim is
checked against the same code a user question would surface; NLI reuses the Step-7 scorer's
three-way classifier. The result is one :class:`DriftFinding` per claim, pairing the doc location
with the code location and the verdict.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from repolens.drift.extractor import DocClaim
    from repolens.generation.scorer import GroundingScorer
    from repolens.ingestion.chunker import IndexChunk
    from repolens.retrieval.hybrid import HybridRetriever

logger = get_logger("drift.checker")

DriftStatus = Literal["supported", "contradicted", "not_found"]


@dataclass
class DriftFinding:
    """The drift verdict for a single documentation claim."""

    claim: str
    doc_file: str
    doc_line: int
    status: DriftStatus
    score: float
    code_file: str | None = None
    code_start: int | None = None
    code_end: int | None = None
    code_symbol: str | None = None
    code_excerpt: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DriftChecker:
    """Classifies documentation claims as supported / contradicted / not found against code."""

    def __init__(
        self,
        retriever: HybridRetriever,
        nli_scorer: GroundingScorer,
        top_k: int = 5,
        support_threshold: float = 0.5,
        contradict_threshold: float = 0.5,
    ) -> None:
        self.retriever = retriever
        self.scorer = nli_scorer
        self.top_k = top_k
        self.support_threshold = support_threshold
        self.contradict_threshold = contradict_threshold

    async def check(self, claim: DocClaim) -> DriftFinding:
        """Retrieve code for ``claim`` and classify the relationship between them."""
        chunks = await self.retriever.retrieve(claim.claim, top_k=self.top_k)
        if not chunks:
            return DriftFinding(
                claim=claim.claim,
                doc_file=claim.doc_file,
                doc_line=claim.doc_line,
                status="not_found",
                score=0.0,
            )

        best_entail = (-1.0, chunks[0])
        best_contra = (-1.0, chunks[0])
        for chunk in chunks:
            probs = self.scorer.classify(premise=chunk.body, hypothesis=claim.claim)
            if probs["entailment"] > best_entail[0]:
                best_entail = (probs["entailment"], chunk)
            if probs["contradiction"] > best_contra[0]:
                best_contra = (probs["contradiction"], chunk)

        if best_entail[0] >= self.support_threshold:
            return self._finding(claim, "supported", best_entail[0], best_entail[1])
        if best_contra[0] >= self.contradict_threshold:
            return self._finding(claim, "contradicted", best_contra[0], best_contra[1])
        return self._finding(claim, "not_found", best_entail[0], best_entail[1])

    async def check_all(self, claims: list[DocClaim]) -> list[DriftFinding]:
        """Check every claim and return all findings."""
        return [await self.check(claim) for claim in claims]

    @staticmethod
    def _finding(
        claim: DocClaim, status: DriftStatus, score: float, chunk: IndexChunk
    ) -> DriftFinding:
        return DriftFinding(
            claim=claim.claim,
            doc_file=claim.doc_file,
            doc_line=claim.doc_line,
            status=status,
            score=round(score, 4),
            code_file=chunk.file_path,
            code_start=chunk.start_line,
            code_end=chunk.end_line,
            code_symbol=chunk.symbol_name or None,
            code_excerpt=chunk.body,
        )
