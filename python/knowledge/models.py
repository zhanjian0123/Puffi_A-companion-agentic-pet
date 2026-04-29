from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeImportResult:
    imported: int
    skipped: int
    failed: int
    messages: list[str]


@dataclass(slots=True)
class KnowledgeIndexingState:
    status: str = "idle"
    reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    messages: list[str] | None = None
    last_error: str | None = None


@dataclass(slots=True)
class KnowledgeIndexStartResult:
    started: bool
    state: KnowledgeIndexingState
    message: str


@dataclass(slots=True)
class KnowledgeUploadResult:
    filename: str
    source_path: str
    markdown_path: str
    imported: int
    skipped: int
    failed: int
    messages: list[str]


@dataclass(slots=True)
class KnowledgeDeleteResult:
    deleted: bool
    path: str
    chunks_deleted: int
    relations_deleted: int
    summaries_deleted: int
    orphan_entities_deleted: int
    message: str


@dataclass(slots=True)
class KnowledgeDocument:
    path: str
    title: str
    hash: str
    size: int
    status: str
    indexed_at: str | None
    chunk_count: int


@dataclass(slots=True)
class KnowledgeSearchResult:
    document: str
    chunk_index: int
    score: float
    content: str
    relations: list[str] | None = None
    entities: list[str] | None = None
    summaries: list[str] | None = None


@dataclass(slots=True)
class KnowledgeStatus:
    enabled: bool
    document_dir: str
    index_db_path: str
    document_count: int
    chunk_count: int
    entity_count: int
    relation_count: int
    indexing: KnowledgeIndexingState | None = None


@dataclass(slots=True)
class KnowledgeEntity:
    name: str
    normalized_name: str
    type: str
    document_count: int
    chunk_count: int
    updated_at: str | None


@dataclass(slots=True)
class KnowledgeRelation:
    source_entity: str
    relation: str
    target_entity: str
    document: str | None
    chunk_index: int | None
    confidence: float
    description: str | None = None
    evidence: str | None = None
    extractor: str | None = None
    model: str | None = None


@dataclass(slots=True)
class KnowledgeDebugResult:
    query: str
    results: list[KnowledgeSearchResult]
