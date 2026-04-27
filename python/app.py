import json

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

from config import settings
from knowledge import get_knowledge_service
from schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    HistoryResponse,
    KnowledgeDocument,
    KnowledgeDocumentsResponse,
    KnowledgeEntitiesResponse,
    KnowledgeEntity,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeRelation,
    KnowledgeRelationsResponse,
    KnowledgeSource,
    KnowledgeStatusResponse,
    KnowledgeUploadResponse,
)
from service import AgentService

agent_service = AgentService()
knowledge_service = get_knowledge_service()
app = FastAPI(title="AI Pet Agent Service", version="0.2.0")


@app.on_event("startup")
async def import_knowledge_on_startup() -> None:
    if not settings.knowledge_enabled or not settings.knowledge_import_on_startup:
        return

    result = await knowledge_service.import_documents()
    if result.imported or result.failed:
        print(
            "[Knowledge] startup_import "
            f"imported={result.imported} skipped={result.skipped} failed={result.failed}",
            flush=True,
        )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return agent_service.health()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent_service.chat(request)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        async for event in agent_service.chat_stream(request):
            yield json.dumps(event.model_dump(), ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/history", response_model=HistoryResponse)
async def history(limit: int = Query(default=10, ge=1, le=50)) -> HistoryResponse:
    return await agent_service.history(limit)


@app.get("/knowledge/status", response_model=KnowledgeStatusResponse)
async def knowledge_status() -> KnowledgeStatusResponse:
    status = await knowledge_service.status()
    return KnowledgeStatusResponse(
        enabled=status.enabled,
        document_dir=status.document_dir,
        index_db_path=status.index_db_path,
        document_count=status.document_count,
        chunk_count=status.chunk_count,
        entity_count=status.entity_count,
        relation_count=status.relation_count,
    )


@app.get("/knowledge/documents", response_model=KnowledgeDocumentsResponse)
async def knowledge_documents() -> KnowledgeDocumentsResponse:
    documents = await knowledge_service.list_documents()
    return KnowledgeDocumentsResponse(
        documents=[
            KnowledgeDocument(
                path=document.path,
                title=document.title,
                hash=document.hash,
                size=document.size,
                status=document.status,
                indexed_at=document.indexed_at,
                chunk_count=document.chunk_count,
            )
            for document in documents
        ]
    )


@app.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def knowledge_import(request: KnowledgeImportRequest) -> KnowledgeImportResponse:
    result = await knowledge_service.import_documents(request.path)
    return KnowledgeImportResponse(
        imported=result.imported,
        skipped=result.skipped,
        failed=result.failed,
        messages=result.messages,
    )


@app.post("/knowledge/upload", response_model=KnowledgeUploadResponse)
async def knowledge_upload(request: Request) -> KnowledgeUploadResponse:
    filename = "document"
    try:
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise ValueError("上传请求缺少 file 字段。")

        filename = file.filename or "document"
        content = await file.read()
        result = await knowledge_service.upload_document(
            filename=filename,
            content=content,
        )
    except Exception as error:
        print(f"[Knowledge] upload error filename={filename} error={error}", flush=True)
        raise HTTPException(status_code=400, detail=str(error)) from error

    return KnowledgeUploadResponse(
        message="我记得这个文件了，它已经存在我的知识库里。",
        filename=result.filename,
        imported=result.imported,
        skipped=result.skipped,
        failed=result.failed,
    )


@app.post("/knowledge/query", response_model=KnowledgeQueryResponse)
async def knowledge_query(request: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
    results = await knowledge_service.query(request.query, top_k=request.top_k)
    return KnowledgeQueryResponse(
        query=request.query,
        results=[
            KnowledgeSource(
                document=result.document,
                chunk_index=result.chunk_index,
                score=result.score,
                content=result.content,
                relations=result.relations,
            )
            for result in results
        ],
    )


@app.get("/knowledge/entities", response_model=KnowledgeEntitiesResponse)
async def knowledge_entities(limit: int = Query(default=100, ge=1, le=500)) -> KnowledgeEntitiesResponse:
    entities = await knowledge_service.list_entities(limit=limit)
    return KnowledgeEntitiesResponse(
        entities=[
            KnowledgeEntity(
                name=entity.name,
                normalized_name=entity.normalized_name,
                type=entity.type,
                document_count=entity.document_count,
                chunk_count=entity.chunk_count,
                updated_at=entity.updated_at,
            )
            for entity in entities
        ]
    )


@app.get("/knowledge/relations", response_model=KnowledgeRelationsResponse)
async def knowledge_relations(
    query: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> KnowledgeRelationsResponse:
    relations = await knowledge_service.list_relations(query=query, limit=limit)
    return KnowledgeRelationsResponse(
        relations=[
            KnowledgeRelation(
                source_entity=relation.source_entity,
                relation=relation.relation,
                target_entity=relation.target_entity,
                document=relation.document,
                chunk_index=relation.chunk_index,
                confidence=relation.confidence,
            )
            for relation in relations
        ]
    )
