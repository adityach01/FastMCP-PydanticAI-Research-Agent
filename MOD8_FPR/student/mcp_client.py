from __future__ import annotations

import json
import re
from dataclasses import dataclass
from os import getenv
from typing import Any

import httpx


class MCPClientError(RuntimeError):
    """Raised when FastMCP HTTP calls fail."""


@dataclass(slots=True)
class MCPClient:
    base_url: str | None = None
    timeout_s: float = 12.0

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or getenv("MCP_HTTP_URL") or "http://127.0.0.1:8000").rstrip("/")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        errors: list[str] = []
        assert self.base_url is not None

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            attempts: list[tuple[str, str, dict[str, Any]]] = [
                ("POST", f"{self.base_url}/tools/{name}", arguments),
                ("POST", f"{self.base_url}/tools/call", {"name": name, "arguments": arguments}),
                (
                    "POST",
                    f"{self.base_url}/mcp",
                    {
                        "jsonrpc": "2.0",
                        "id": "1",
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                ),
            ]
            for method, url, payload in attempts:
                try:
                    response = await client.request(method, url, json=payload)
                    response.raise_for_status()
                    return _extract_result(response.json())
                except Exception as exc:
                    errors.append(f"{url}: {exc}")

        raise MCPClientError("MCP tool call failed | " + " | ".join(errors))

    async def call_tool_stream(self, name: str, arguments: dict[str, Any]) -> Any:
        assert self.base_url is not None
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                async with client.stream("POST", f"{self.base_url}/mcp/stream", json=payload) as response:
                    response.raise_for_status()
                    chunks: list[dict[str, Any]] = []
                    async for line in response.aiter_lines():
                        text = line.strip()
                        if not text:
                            continue
                        if text.startswith("data:"):
                            text = text[5:].strip()
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict):
                                chunks.append(parsed)
                        except Exception:
                            continue
                    if chunks:
                        return _extract_result(chunks[-1])
            except Exception:
                pass

        return await self.call_tool(name, arguments)

    async def web_search(self, q: str, max_results: int = 8) -> list[dict[str, Any]]:
        for name, payload in (
            ("web.search", {"q": q, "max_results": max_results}),
            ("web_search", {"query": q, "limit": max_results}),
            ("search", {"query": q, "limit": max_results}),
        ):
            try:
                data = await self.call_tool_stream(name, payload)
                normalized = _normalize_search_items(data)
                if normalized:
                    return normalized[:max_results]
            except Exception:
                continue
        return []

    async def web_fetch(self, url: str) -> dict[str, Any]:
        for name, payload in (
            ("web.fetch", {"url": url}),
            ("fetch", {"url": url}),
        ):
            try:
                data = await self.call_tool_stream(name, payload)
                if isinstance(data, dict):
                    html = str(data.get("html") or data.get("content") or data.get("text") or "")
                    return {
                        "url": url,
                        "title": str(data.get("title") or "").strip(),
                        "html": html,
                        "text": str(data.get("text") or "").strip(),
                    }
                if isinstance(data, str):
                    return {"url": url, "title": "", "html": data, "text": ""}
            except Exception:
                continue
        return {"url": url, "title": "", "html": "", "text": ""}

    async def notes_upsert(self, key: str, text: str) -> dict[str, Any]:
        for name, payload in (
            ("notes.upsert", {"key": key, "text": text}),
            ("notes_upsert", {"key": key, "text": text}),
        ):
            try:
                data = await self.call_tool(name, payload)
                if isinstance(data, dict):
                    return data
                return {"ok": True}
            except Exception:
                continue
        return {"ok": False}

    async def notes_query(self, q: str) -> list[dict[str, Any]]:
        for name, payload in (
            ("notes.query", {"q": q}),
            ("notes_query", {"query": q}),
        ):
            try:
                data = await self.call_tool(name, payload)
                if isinstance(data, dict) and isinstance(data.get("items"), list):
                    return [x for x in data["items"] if isinstance(x, dict)]
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
            except Exception:
                continue
        return []

    async def guard_pii_check(self, text: str) -> dict[str, Any]:
        for name, payload in (
            ("guard.pii_check", {"text": text}),
            ("pii_check", {"text": text}),
        ):
            try:
                data = await self.call_tool(name, payload)
                if isinstance(data, dict) and "pii_flagged" in data:
                    return {"pii_flagged": bool(data.get("pii_flagged")), "details": data}
                if isinstance(data, dict) and "flagged" in data:
                    return {"pii_flagged": bool(data.get("flagged")), "details": data}
            except Exception:
                continue

        pii_flagged = bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text))
        return {"pii_flagged": pii_flagged, "details": {"fallback": True}}


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")


def _extract_result(data: Any) -> Any:
    if isinstance(data, dict):
        if "result" in data:
            return data["result"]
        if "content" in data:
            return data["content"]
    return data


def _normalize_search_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            items = data["results"]
        elif isinstance(data.get("items"), list):
            items = data["items"]
        else:
            items = [data] if all(k in data for k in ("title", "url")) else []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title") or item.get("name") or "Untitled").strip(),
                "url": str(item.get("url") or item.get("link") or "").strip(),
                "snippet": str(item.get("snippet") or item.get("summary") or item.get("text") or "").strip(),
            }
        )
    return normalized
