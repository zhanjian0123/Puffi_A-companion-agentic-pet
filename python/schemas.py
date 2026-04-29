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
    type: Literal["delta", "done", "error", "state"]
    delta: str | None = None
    message: str | None = None
    pet_state: Literal["idle", "thinking", "searching", "tooling", "success", "error", "sleepy"] | None = None


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
    model_api: str = "responses"
    base_url: str | None = None
    mcp_enabled: bool = False
    mcp_servers: list[str] = Field(default_factory=list)


class KnowledgeImportRequest(BaseModel):
    path: str | None = Field(default=None, description="Optional file or directory path to import.")


class KnowledgeImportResponse(BaseModel):
    imported: int
    skipped: int
    failed: int
    messages: list[str]


class KnowledgeIndexRequest(BaseModel):
    path: str | None = Field(default=None, description="Optional file or directory path to index.")


class KnowledgeIndexingStateResponse(BaseModel):
    status: str
    reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    messages: list[str] = Field(default_factory=list)
    last_error: str | None = None


class KnowledgeIndexResponse(BaseModel):
    started: bool
    message: str
    state: KnowledgeIndexingStateResponse


class KnowledgeUploadResponse(BaseModel):
    message: str
    filename: str
    imported: int
    skipped: int
    failed: int
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class KnowledgeSource(BaseModel):
    document: str
    chunk_index: int
    score: float
    content: str
    relations: list[str] | None = None
    entities: list[str] | None = None
    summaries: list[str] | None = None


class KnowledgeQueryResponse(BaseModel):
    query: str
    results: list[KnowledgeSource]


class KnowledgeDebugQueryResponse(BaseModel):
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
    indexing: KnowledgeIndexingStateResponse | None = None


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
    description: str | None = None
    evidence: str | None = None
    extractor: str | None = None
    model: str | None = None


class KnowledgeRelationsResponse(BaseModel):
    relations: list[KnowledgeRelation]


class Reminder(BaseModel):
    id: str
    title: str
    remind_at: str
    completed: bool
    created_at: str
    completed_at: str | None = None
    notified_at: str | None = None


class RemindersDueResponse(BaseModel):
    reminders: list[Reminder]


class ReminderNotifiedResponse(BaseModel):
    success: bool
    reminder: Reminder | None = None
    message: str


class ScheduledTask(BaseModel):
    id: str
    title: str
    enabled: bool
    schedule: dict[str, Any]
    action: dict[str, Any]
    next_run_at: str
    created_at: str
    last_run_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None


class ScheduledTaskRun(BaseModel):
    id: str
    task_id: str
    task_title: str
    started_at: str
    status: str
    prompt: str
    finished_at: str | None = None
    response: str | None = None
    error: str | None = None
    knowledge_document: str | None = None


class ScheduledTasksDueResponse(BaseModel):
    tasks: list[ScheduledTask]


class ScheduledTaskRunsResponse(BaseModel):
    runs: list[ScheduledTaskRun]


class ScheduledTaskRunCreateRequest(BaseModel):
    task_id: str = Field(min_length=1)
    task_title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class ScheduledTaskRunCreateResponse(BaseModel):
    success: bool
    run: ScheduledTaskRun | None = None
    message: str


class ScheduledTaskRunFinishRequest(BaseModel):
    status: Literal["success", "error"] = "success"
    response: str | None = None
    error: str | None = None
    knowledge_document: str | None = None


class ScheduledTaskRunFinishResponse(BaseModel):
    success: bool
    run: ScheduledTaskRun | None = None
    message: str


class ScheduledTaskCompletedRequest(BaseModel):
    success: bool = True
    error: str | None = None


class ScheduledTaskCompletedResponse(BaseModel):
    success: bool
    task: ScheduledTask | None = None
    message: str
