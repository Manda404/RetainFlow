"""Pydantic schemas used by the RetainFlow API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ResponseType = Literal["text", "table", "plotly", "email_draft", "records"]


class ChatRequest(BaseModel):
    """Natural-language request sent by a business user."""

    message: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=200)


class ChatResponse(BaseModel):
    """Standard API response built from an AgentResponse."""

    agent_name: str
    answer: str
    response_type: ResponseType
    data: Any | None = None
    figure: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGSearchRequest(BaseModel):
    """Request used to retrieve targeted marketing strategy documents."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SQLRequest(BaseModel):
    """Explicit SQL request for trusted local exploration.

    The API still routes the query through SQLTool, so only read-only SQL is
    accepted.
    """

    sql: str = Field(..., min_length=1)
    limit: int = Field(default=100, ge=1, le=500)
