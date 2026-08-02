from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from .agent import ResearchAgent
from .config import load_settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FastMCP x PydanticAI research agent")
    parser.add_argument("--topic", required=True, help="Research topic prompt")
    parser.add_argument("--out", default="artifacts", help="Output artifact directory")
    return parser


async def _amain(topic: str, out: str) -> int:
    settings = load_settings()
    agent = ResearchAgent(settings)

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    brief_path = out_dir / "brief.md"
    hitl_path = out_dir / "hitl_ticket.json"
    report_path = out_dir / "report.json"
    search_results_path = out_dir / "search_results.json"
    selected_urls_path = out_dir / "selected_urls.json"
    snippets_path = out_dir / "snippets.json"

    search_results_live: list[dict[str, Any]] = []
    selected_urls_live: list[str] = []
    snippets_live: list[dict[str, str]] = []

    # Initialize artifacts so they exist early and update incrementally.
    search_results_path.write_text("[]", encoding="utf-8")
    selected_urls_path.write_text("[]", encoding="utf-8")
    snippets_path.write_text("[]", encoding="utf-8")

    async def on_event(kind: str, payload: Any) -> None:
        if kind == "search.result" and isinstance(payload, dict):
            search_results_live.append(payload)
            search_results_path.write_text(json.dumps(search_results_live, indent=2), encoding="utf-8")
        elif kind == "select.url" and isinstance(payload, dict):
            url = str(payload.get("url") or "").strip()
            if url:
                selected_urls_live.append(url)
                selected_urls_path.write_text(json.dumps(selected_urls_live, indent=2), encoding="utf-8")
        elif kind == "snippet" and isinstance(payload, dict):
            snippets_live.append(payload)
            snippets_path.write_text(json.dumps(snippets_live, indent=2), encoding="utf-8")

    result = await agent.run(topic, on_event=on_event)

    report: dict[str, Any] = {
        "topic": result.topic,
        "model": result.model,
        "generated_at_utc": result.generated_at_utc,
        "mcp_http_url": settings.mcp_http_url,
        "pii_flagged": result.pii_flagged,
        "source_count": len(result.search_results),
        "selected_url_count": len(result.selected_urls),
        "raw_log_count": len(result.raw_logs),
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Ensure final artifact files reflect full final state.
    search_results_path.write_text(json.dumps(result.search_results, indent=2), encoding="utf-8")
    selected_urls_path.write_text(json.dumps(result.selected_urls, indent=2), encoding="utf-8")
    snippets_path.write_text(json.dumps(result.snippets, indent=2), encoding="utf-8")

    if result.pii_flagged:
        hitl_ticket = {
            "topic": result.topic,
            "reason": "PII flagged by guard.pii_check",
            "status": "open",
        }
        hitl_path.write_text(json.dumps(hitl_ticket, indent=2), encoding="utf-8")
        if brief_path.exists():
            brief_path.unlink()
    else:
        if result.brief_md:
            brief_path.write_text(result.brief_md, encoding="utf-8")
        if hitl_path.exists():
            hitl_path.unlink()

    await _append_notes_entry(
        db_path=Path("notes.sqlite"),
        topic=result.topic,
        model=result.model,
        pii_flagged=result.pii_flagged,
        brief_md=result.brief_md or "",
        report=report,
        selected_urls=result.selected_urls,
    )

    summary = {
        "topic": result.topic,
        "model": result.model,
        "sources": len(result.search_results),
        "mode": "hitl" if result.pii_flagged else "ok",
        "artifacts": {
            "report": str(report_path),
            "search_results": str(search_results_path),
            "selected_urls": str(selected_urls_path),
            "snippets": str(snippets_path),
            "notes_db": "notes.sqlite",
        },
    }
    if result.pii_flagged:
        summary["artifacts"]["hitl_ticket"] = str(hitl_path)
    else:
        summary["artifacts"]["brief"] = str(brief_path)

    print(json.dumps(summary, indent=2))
    return 0


async def _append_notes_entry(
    *,
    db_path: Path,
    topic: str,
    model: str,
    pii_flagged: bool,
    brief_md: str,
    report: dict[str, Any],
    selected_urls: list[str],
) -> None:
    await asyncio.to_thread(
        _append_notes_entry_sync,
        db_path,
        topic,
        model,
        pii_flagged,
        brief_md,
        report,
        selected_urls,
    )


def _append_notes_entry_sync(
    db_path: Path,
    topic: str,
    model: str,
    pii_flagged: bool,
    brief_md: str,
    report: dict[str, Any],
    selected_urls: list[str],
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                topic TEXT NOT NULL,
                model TEXT NOT NULL,
                pii_flagged INTEGER NOT NULL,
                note_key TEXT NOT NULL,
                brief_md TEXT NOT NULL,
                note_text TEXT NOT NULL,
                selected_urls_json TEXT NOT NULL,
                report_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notes (
                topic, model, pii_flagged, note_key, brief_md, note_text, selected_urls_json, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic,
                model,
                1 if pii_flagged else 0,
                f"brief:{topic}",
                brief_md,
                brief_md,
                json.dumps(selected_urls),
                json.dumps(report),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    args = _build_parser().parse_args()

    # Ensure the output path can be created before running external calls.
    Path(args.out).mkdir(parents=True, exist_ok=True)

    return asyncio.run(_amain(args.topic, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
