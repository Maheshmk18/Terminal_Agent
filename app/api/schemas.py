from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReadinessCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class ReadinessResponse(BaseModel):
    ready: bool
    checks: list[ReadinessCheck]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    awaiting_approval: bool = False
    approval_request: dict | None = None


class ApprovalDecision(BaseModel):
    thread_id: str
    approved: bool
    approved_ids: list[str] | None = None


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    thread_id: str
    messages: list[HistoryMessage]
