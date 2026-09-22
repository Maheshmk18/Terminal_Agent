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
