from typing import Any
from pydantic import BaseModel, Field


class ToolInvokeRequest(BaseModel):
    tool_name: str = Field(alias="toolName")
    params: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    result: Any
