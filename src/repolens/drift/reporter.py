"""Drift report formatting.

:class:`DriftReporter` turns a list of :class:`DriftFinding` objects into the two artefacts the
product needs: a human-readable markdown report (doc location beside code location, grouped by
verdict) and a JSON payload for the UI and the API. :meth:`has_contradictions` drives the
``--ci`` exit code so CI can fail when documentation drifts from code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repolens.drift.checker import DriftFinding

_STATUS_ORDER = ("contradicted", "not_found", "supported")
_STATUS_HEADING = {
    "contradicted": "❌ Contradicted",
    "not_found": "⚠️ Not found in code",
    "supported": "✅ Supported",
}


class DriftReporter:
    """Formats drift findings as markdown or JSON."""

    def __init__(self, findings: list[DriftFinding], repo_name: str = "") -> None:
        self.findings = findings
        self.repo_name = repo_name

    def counts(self) -> dict[str, int]:
        counts = {status: 0 for status in _STATUS_ORDER}
        for finding in self.findings:
            counts[finding.status] += 1
        return counts

    def has_contradictions(self) -> bool:
        """True if any claim is contradicted by the code (used by ``--ci``)."""
        return any(f.status == "contradicted" for f in self.findings)

    def to_json(self) -> dict[str, object]:
        return {
            "repo": self.repo_name,
            "counts": self.counts(),
            "has_contradictions": self.has_contradictions(),
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_markdown(self) -> str:
        counts = self.counts()
        lines = [
            f"# Documentation Drift Report{f' — {self.repo_name}' if self.repo_name else ''}",
            "",
            f"- ❌ Contradicted: **{counts['contradicted']}**",
            f"- ⚠️ Not found: **{counts['not_found']}**",
            f"- ✅ Supported: **{counts['supported']}**",
            "",
        ]
        for status in _STATUS_ORDER:
            group = [f for f in self.findings if f.status == status]
            if not group:
                continue
            lines.append(f"## {_STATUS_HEADING[status]} ({len(group)})")
            lines.append("")
            for finding in group:
                lines.extend(self._render_finding(finding))
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_finding(finding: DriftFinding) -> list[str]:
        block = [
            f"### {finding.claim}",
            "",
            f"- **Doc:** `{finding.doc_file}:{finding.doc_line}`",
        ]
        if finding.code_file is not None:
            location = f"{finding.code_file}:{finding.code_start}-{finding.code_end}"
            symbol = f" (`{finding.code_symbol}`)" if finding.code_symbol else ""
            block.append(f"- **Code:** `{location}`{symbol} — score {finding.score:.2f}")
            if finding.code_excerpt:
                block += ["", "```", finding.code_excerpt.strip(), "```"]
        else:
            block.append("- **Code:** no relevant code retrieved")
        block.append("")
        return block
