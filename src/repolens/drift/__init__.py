"""Doc-drift detection: claim extractor, NLI entailment checker, and report generator."""

from repolens.drift.checker import DriftChecker, DriftFinding, DriftStatus
from repolens.drift.extractor import ClaimExtractor, DocClaim, iter_doc_files
from repolens.drift.reporter import DriftReporter

__all__ = [
    "ClaimExtractor",
    "DocClaim",
    "DriftChecker",
    "DriftFinding",
    "DriftReporter",
    "DriftStatus",
    "iter_doc_files",
]
