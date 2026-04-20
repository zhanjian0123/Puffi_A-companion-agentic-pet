from typing import Any
from pydantic import BaseModel


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 5


class KnowledgeResult(BaseModel):
    id: str
    content: str
    metadata: dict[str, Any]


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeResult]
