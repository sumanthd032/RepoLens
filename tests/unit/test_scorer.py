"""Unit tests for the NLI grounding scorer (Invariant 4) with an injected model."""

from __future__ import annotations

import re

from repolens.generation.scorer import GroundingScorer, split_sentences

_WORD = re.compile(r"[A-Za-z_]+")


class FakeNLI:
    """Fake NLI model: entailment rises with premise/hypothesis word overlap.

    Returns ``[contradiction, entailment, neutral]`` probabilities per pair so the scorer's
    column indexing and softmax-free aggregation are exercised exactly as with the real model.
    """

    def predict(self, sentences: list[list[str]], **kwargs: object) -> list[list[float]]:
        out = []
        for premise, hypothesis in sentences:
            p = {w.lower() for w in _WORD.findall(premise)}
            h = {w.lower() for w in _WORD.findall(hypothesis)}
            overlap = len(p & h) / len(h) if h else 0.0
            entail = round(overlap, 4)
            remainder = (1.0 - entail) / 2
            out.append([remainder, entail, remainder])  # contradiction, entailment, neutral
        return out


def test_split_sentences() -> None:
    assert split_sentences("One thing. Two things! Three?") == [
        "One thing.",
        "Two things!",
        "Three?",
    ]
    assert split_sentences("   ") == []


def test_grounded_answer_scores_high() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    premise = "the handle_route function returns resolve of the path"
    result = scorer.score("handle_route returns resolve of the path.", [premise])
    assert 0.0 <= result.score <= 1.0
    assert result.verdict == "high"
    assert result.score >= 0.75


def test_ungrounded_answer_scores_low() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    result = scorer.score(
        "Kubernetes orchestrates containers across many nodes.",
        ["def handle_route(path): return resolve(path)"],
    )
    assert result.verdict in {"none", "low"}
    assert result.score < 0.5


def test_score_is_mean_over_sentences() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    premise = "alpha beta gamma delta"
    # First sentence fully overlaps premise, second does not.
    result = scorer.score("alpha beta gamma delta. zzz yyy xxx www.", [premise])
    assert len(result.sentence_scores) == 2
    assert result.sentence_scores[0][1] > result.sentence_scores[1][1]


def test_best_chunk_wins_per_sentence() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    # The matching premise should drive the sentence score even alongside an irrelevant one.
    result = scorer.score(
        "alpha beta gamma.",
        ["totally unrelated text here", "alpha beta gamma"],
    )
    assert result.score >= 0.75


def test_empty_answer_scores_none() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    result = scorer.score("", ["some premise"])
    assert result.score == 0.0
    assert result.verdict == "none"


def test_no_premises_scores_none() -> None:
    scorer = GroundingScorer(model=FakeNLI())
    result = scorer.score("A grounded sentence.", [])
    assert result.score == 0.0
    assert result.verdict == "none"
