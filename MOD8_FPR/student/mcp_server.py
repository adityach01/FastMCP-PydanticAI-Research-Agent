from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Assignment FastMCP-Compatible Server", version="0.1.0")


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.get("/tools")
async def list_tools() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "search",
                "description": "Searches DuckDuckGo instant answer API.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ]
    }


@app.post("/tools/search")
async def tool_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    limit = int(payload.get("limit") or 5)
    return {"results": await _duckduckgo_search(query, limit=limit)}


@app.post("/tools/call")
async def tools_call(call: ToolCall) -> dict[str, Any]:
    if call.name in {"search", "web_search", "search_web", "research_search"}:
        query = str(call.arguments.get("query") or "").strip()
        limit = int(call.arguments.get("limit") or 5)
        return {"result": {"results": await _duckduckgo_search(query, limit=limit)}}
    return {"error": f"Unknown tool: {call.name}"}


@app.post("/mcp")
async def mcp_bridge(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") or {}
    name = params.get("name")
    args = params.get("arguments") or {}
    if name in {"search", "web_search", "search_web", "research_search"}:
        query = str(args.get("query") or "").strip()
        limit = int(args.get("limit") or 5)
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id", "1"),
            "result": {"results": await _duckduckgo_search(query, limit=limit)},
        }
    return {"jsonrpc": "2.0", "id": payload.get("id", "1"), "error": {"message": "Unknown tool"}}


async def _duckduckgo_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query:
        return []

    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, Any]] = []
    abstract_url = data.get("AbstractURL")
    abstract_text = data.get("AbstractText")
    heading = data.get("Heading")
    if abstract_url:
        results.append(
            {
                "title": heading or "DuckDuckGo Abstract",
                "url": abstract_url,
                "snippet": abstract_text or "",
                "published_at": None,
            }
        )

    for topic in data.get("RelatedTopics", []):
        if len(results) >= limit:
            break
        if isinstance(topic, dict) and topic.get("FirstURL"):
            results.append(
                {
                    "title": str(topic.get("Text") or "Related Topic")[:120],
                    "url": topic.get("FirstURL"),
                    "snippet": str(topic.get("Text") or ""),
                    "published_at": None,
                }
            )

    return results[:limit]
