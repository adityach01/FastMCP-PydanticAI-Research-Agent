from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv

load_dotenv()


def _pick_model() -> str:
    explicit = getenv("GEMINI_MODEL")
    if explicit and explicit.strip() == "gemini-3.6-flash":
        return "gemini-3.6-flash"

    # Assignment-enforced default model.
    return "gemini-3.6-flash"


@dataclass(frozen=True, slots=True)
class Settings:
    gemini_model: str
    gemini_api_key: str | None
    mcp_http_url: str
    request_timeout_s: float = 12.0
    total_budget_s: float = 90.0

    @property
    def has_api_key(self) -> bool:
        return bool(self.gemini_api_key)


def load_settings() -> Settings:
    key = getenv("GEMINI_API_KEY") or getenv("GOOGLE_API_KEY")
    mcp_url = (getenv("MCP_HTTP_URL") or "http://127.0.0.1:8000").rstrip("/")
    return Settings(
        gemini_model=_pick_model(),
        gemini_api_key=(key.strip() if key else None),
        mcp_http_url=mcp_url,
    )
