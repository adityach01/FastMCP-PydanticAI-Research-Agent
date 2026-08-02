from __future__ import annotations

import json
from pathlib import Path

from .models import ResearchReport


def write_artifacts(report: ResearchReport, out_dir: str) -> dict[str, str]:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / "report.json"
    md_path = base / "report.md"

    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def _to_markdown(report: ResearchReport) -> str:
    findings = "\n".join(
        f"- {f.claim} (confidence: {f.confidence:.2f})\n  - Rationale: {f.rationale}" for f in report.key_findings
    ) or "- No high-confidence findings available."

    limitations = "\n".join(f"- {item}" for item in report.limitations) or "- None reported."

    citations = "\n".join(
        f"- [{c.title}]({c.url})" for c in report.citations
    ) or "- No citations available."

    return (
        f"# Research Report\n\n"
        f"**Topic:** {report.topic}\n\n"
        f"## Executive Summary\n\n{report.executive_summary}\n\n"
        f"## Key Findings\n\n{findings}\n\n"
        f"## Limitations\n\n{limitations}\n\n"
        f"## Citations\n\n{citations}\n"
    )
