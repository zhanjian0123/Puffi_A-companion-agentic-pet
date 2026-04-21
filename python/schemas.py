from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    response: str
    action: Any | None = None


class HealthResponse(BaseModel):
    status: str
    runtime: str
    configured: bool
    sdk_installed: bool
    api_key_configured: bool
    model: str
    base_url: str | None = None
