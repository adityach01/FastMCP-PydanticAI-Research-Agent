from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Citation(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    snippet: str = Field(default="", max_length=2000)
    published_at: str | None = None


class Finding(BaseModel):
    claim: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(default="", max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)


class ResearchReport(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    executive_summary: str = Field(min_length=10, max_length=5000)
    key_findings: list[Finding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    generated_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model: str
    metadata: dict[str, Any] = Field(default_factory=dict)
