from typing import Literal
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    mode: str = Field(default="chat", min_length=1, max_length=40)


class ChatResponse(BaseModel):
    response: str
    action: Any | None = None


class ChatStreamEvent(BaseModel):
    type: Literal["delta", "done", "error"]
    delta: str | None = None
    message: str | None = None


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]


class HealthResponse(BaseModel):
    status: str
    runtime: str
    configured: bool
    sdk_installed: bool
    api_key_configured: bool
    model: str
    base_url: str | None = None


class KnowledgeImportRequest(BaseModel):
    path: str | None = Field(default=None, description="Optional file or directory path to import.")


class KnowledgeImportResponse(BaseModel):
    imported: int
    skipped: int
    failed: int
    messages: list[str]


class KnowledgeUploadResponse(BaseModel):
    message: str
    filename: str
    imported: int
    skipped: int
    failed: int


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class KnowledgeSource(BaseModel):
    document: str
    chunk_index: int
    score: float
    content: str
    relations: list[str] | None = None


class KnowledgeQueryResponse(BaseModel):
    query: str
    results: list[KnowledgeSource]


class KnowledgeDocument(BaseModel):
    path: str
    title: str
    hash: str
    size: int
    status: str
    indexed_at: str | None = None
    chunk_count: int = 0


class KnowledgeDocumentsResponse(BaseModel):
    documents: list[KnowledgeDocument]


class KnowledgeStatusResponse(BaseModel):
    enabled: bool
    document_dir: str
    index_db_path: str
    document_count: int
    chunk_count: int
    entity_count: int = 0
    relation_count: int = 0


class KnowledgeEntity(BaseModel):
    name: str
    normalized_name: str
    type: str
    document_count: int
    chunk_count: int
    updated_at: str | None = None


class KnowledgeEntitiesResponse(BaseModel):
    entities: list[KnowledgeEntity]


class KnowledgeRelation(BaseModel):
    source_entity: str
    relation: str
    target_entity: str
    document: str | None = None
    chunk_index: int | None = None
    confidence: float


class KnowledgeRelationsResponse(BaseModel):
    relations: list[KnowledgeRelation]
