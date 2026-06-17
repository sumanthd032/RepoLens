"""NLI grounding scorer.

Citations can be valid (the span exists) yet the sentence may still not *follow from* that span.
:class:`GroundingScorer` measures actual entailment: each answer sentence is treated as a
hypothesis and run through a natural-language-inference cross-encoder
(``nli-deberta-v3-small``) against its cited code as the premise. The per-sentence entailment
probabilities are averaged into a single grounding score (0–1) and a verdict, which the answer
contract requires for every response (Invariant 4).

The model is loaded lazily and injectable so unit tests run without the download.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import numpy as np

from repolens.generation.validator import _SENTENCE_RE
from repolens.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger("generation.scorer")

DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"
# Label order produced by the nli-deberta cross-encoders: contradiction, entailment, neutral.
_CONTRADICTION_INDEX = 0
_ENTAILMENT_INDEX = 1
_NEUTRAL_INDEX = 2

Verdict = str  # "high" | "medium" | "low" | "none"


class _NLIModel(Protocol):
    """Minimal interface the scorer needs from an NLI cross-encoder."""

    def predict(
        self, sentences: list[list[str]], **kwargs: object
    ) -> Sequence[Sequence[float]]: ...


@dataclass
class GroundingResult:
    """The grounding outcome for one answer."""

    score: float
    verdict: Verdict
    sentence_scores: list[tuple[str, float]] = field(default_factory=list)


def _verdict_for(score: float) -> Verdict:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    if score >= 0.25:
        return "low"
    return "none"


def split_sentences(text: str) -> list[str]:
    """Split answer text into trimmed, non-empty sentences."""
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]


class GroundingScorer:
    """Scores how well an answer's sentences are entailed by their cited code.

    Args:
        model_name: HuggingFace NLI cross-encoder id.
        device: Torch device string; ``None`` lets the model decide.
        model: Pre-built NLI model (injected in tests to avoid the download).
        entailment_index: Column of the model output holding the entailment probability.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        model: _NLIModel | None = None,
        entailment_index: int = _ENTAILMENT_INDEX,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.entailment_index = entailment_index
        self._model = model

    @property
    def model(self) -> _NLIModel:
        """Lazily load and cache the NLI cross-encoder."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading NLI model %s", self.model_name)
            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def score(self, answer_text: str, cited_chunks: list[str]) -> GroundingResult:
        """Return the grounding score for ``answer_text`` given its ``cited_chunks`` (premises).

        Each sentence is scored as the maximum entailment probability over all cited chunks; the
        answer score is the mean across sentences. An answer with no sentences or no premises
        scores ``0.0`` / ``"none"``.
        """
        sentences = split_sentences(answer_text)
        if not sentences or not cited_chunks:
            return GroundingResult(score=0.0, verdict="none")

        # One (premise, hypothesis) pair per sentence × chunk, scored in a single batch.
        pairs = [[chunk, sentence] for sentence in sentences for chunk in cited_chunks]
        probs = np.asarray(self.model.predict(pairs), dtype=np.float32)
        entail = probs[:, self.entailment_index].reshape(len(sentences), len(cited_chunks))
        per_sentence = entail.max(axis=1)

        sentence_scores = [
            (sentence, float(value))
            for sentence, value in zip(sentences, per_sentence, strict=True)
        ]
        mean = float(per_sentence.mean())
        return GroundingResult(
            score=mean, verdict=_verdict_for(mean), sentence_scores=sentence_scores
        )

    def classify(self, premise: str, hypothesis: str) -> dict[str, float]:
        """Return ``{contradiction, entailment, neutral}`` probabilities for one NLI pair.

        Used by drift detection, which needs the full three-way verdict (a claim can be
        *contradicted* by code, not merely unsupported) rather than a single grounding number.
        """
        probs = np.asarray(self.model.predict([[premise, hypothesis]]), dtype=np.float32)[0]
        return {
            "contradiction": float(probs[_CONTRADICTION_INDEX]),
            "entailment": float(probs[self.entailment_index]),
            "neutral": float(probs[_NEUTRAL_INDEX]),
        }
