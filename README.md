# FastMCP x PydanticAI Research Agent

A Python research pipeline that:

- searches the web through an MCP-compatible HTTP server,
- fetches and cleans page content,
- extracts snippets,
- performs a PII safety check,
- generates a structured policy brief (LLM or deterministic fallback),
- writes machine-readable artifacts for review and grading.

The default model target in this project is `gemini-3.6-flash`.

## What This Project Produces

For each run, the CLI writes incremental and final artifacts into an output folder:

- `report.json`: run metadata and counters
- `search_results.json`: deduplicated search results
- `selected_urls.json`: final URL shortlist
- `snippets.json`: extracted snippets used for synthesis
- `brief.md`: generated brief when no PII is flagged
- `hitl_ticket.json`: generated instead of `brief.md` when PII is flagged
- `notes.sqlite`: append-only local notes database

Example output is available in `artifacts/` and `artifacts_pii_test/`.

## Repository Layout

```text
student/
	run.py          # CLI entrypoint and artifact orchestration
	agent.py        # Research pipeline + brief generation
	mcp_client.py   # MCP tool calling (multiple HTTP compatibility shapes)
	mcp_server.py   # Minimal MCP-compatible FastAPI tool server
	config.py       # Environment-based settings
	models.py       # Structured report models (legacy/auxiliary)
	artifacts.py    # Markdown/JSON report writer helper (legacy/auxiliary)
	prompts.py      # Prompt helpers (legacy/auxiliary)
tests/
	...             # Unit tests
```

## Requirements

- Python 3.12+
- Internet access (for live search/fetch)
- Optional: Gemini API key for LLM brief generation

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Environment Configuration

Create `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Supported variables:

- `GEMINI_API_KEY`: primary API key used by the LLM path
- `GOOGLE_API_KEY`: alternate key name supported by config
- `GEMINI_MODEL`: currently enforced to `gemini-3.6-flash`
- `MCP_HTTP_URL`: MCP server base URL (default `http://127.0.0.1:8000`)

If no API key is provided (or LLM generation fails), the agent falls back to a deterministic brief builder.

## Quick Start

### 1) Start the MCP-compatible server

```powershell
python -m uvicorn student.mcp_server:app --host 127.0.0.1 --port 8000
```

### 2) Run the research agent (in another terminal)

```powershell
python -m student.run --topic "US semiconductor export controls (2024-2025) overview" --out artifacts
```

The CLI prints a final JSON summary and writes artifacts to the selected output directory.

## How The Pipeline Works

1. Build a query set from the topic.
2. Call MCP search tools and deduplicate URLs.
3. Select up to 15 URLs and fetch page content.
4. Clean extracted content using BeautifulSoup.
5. Save snippets and upsert notes.
6. Run PII guard check.
7. If safe, generate brief via Gemini (or fallback builder).
8. Persist run metadata and notes to artifact files and SQLite.

## Running Tests

```powershell
pytest -q
```

If tests fail, verify your branch is aligned with the current runtime flow in `student/run.py` and `student/agent.py`.

## Troubleshooting

- `MCP tool call failed ...`
	- Ensure the MCP server is running and `MCP_HTTP_URL` matches host/port.

- Empty or low-quality snippets
	- Some sources block scraping or return limited text. Re-run with a more specific topic.

- `brief.md` not created
	- Check whether `hitl_ticket.json` was created due to PII detection.

- LLM path not used
	- Confirm `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is set in your environment.

## Notes

- The client intentionally tries multiple MCP HTTP call shapes for compatibility (`/tools/{name}`, `/tools/call`, JSON-RPC `/mcp`).
- Artifact files for search results, selected URLs, and snippets are initialized early and updated incrementally during execution.
