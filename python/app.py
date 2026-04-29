import asyncio
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
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeIndexingStateResponse,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeDebugQueryResponse,
    KnowledgeRelation,
    KnowledgeRelationsResponse,
    KnowledgeSource,
    KnowledgeStatusResponse,
    KnowledgeUploadResponse,
    Reminder,
    ReminderNotifiedResponse,
    RemindersDueResponse,
    ScheduledTask,
    ScheduledTaskCompletedRequest,
    ScheduledTaskCompletedResponse,
    ScheduledTasksDueResponse,
)
from service import AgentService
from tools.storage import ReminderItem, ScheduledTaskItem, tool_storage

agent_service = AgentService()
knowledge_service = get_knowledge_service()
app = FastAPI(title="AI Pet Agent Service", version="0.2.0")


@app.on_event("startup")
async def import_knowledge_on_startup() -> None:
    await agent_service.startup()

    if not settings.knowledge_enabled or not settings.knowledge_import_on_startup:
        return

    result = await knowledge_service.start_background_import(reason="startup")
    print(f"[Knowledge] startup_import {result.message}", flush=True)


@app.on_event("shutdown")
async def cleanup_agent_service() -> None:
    await agent_service.shutdown()


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
        indexing=to_indexing_state_response(status.indexing),
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


@app.post("/knowledge/index", response_model=KnowledgeIndexResponse)
async def knowledge_index(request: KnowledgeIndexRequest = KnowledgeIndexRequest()) -> KnowledgeIndexResponse:
    result = await knowledge_service.start_background_import(path=request.path, reason="manual")
    return KnowledgeIndexResponse(
        started=result.started,
        message=result.message,
        state=to_indexing_state_response(result.state),
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
                entities=result.entities,
                summaries=result.summaries,
            )
            for result in results
        ],
    )


@app.post("/knowledge/debug-query", response_model=KnowledgeDebugQueryResponse)
async def knowledge_debug_query(request: KnowledgeQueryRequest) -> KnowledgeDebugQueryResponse:
    results = await knowledge_service.query(request.query, top_k=request.top_k, debug=True)
    return KnowledgeDebugQueryResponse(
        query=request.query,
        results=[
            KnowledgeSource(
                document=result.document,
                chunk_index=result.chunk_index,
                score=result.score,
                content=result.content,
                relations=result.relations,
                entities=result.entities,
                summaries=result.summaries,
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
                description=relation.description,
                evidence=relation.evidence,
                extractor=relation.extractor,
                model=relation.model,
            )
            for relation in relations
        ]
    )


@app.get("/reminders/due", response_model=RemindersDueResponse)
async def reminders_due() -> RemindersDueResponse:
    reminders = await asyncio.to_thread(tool_storage.due_reminders)
    return RemindersDueResponse(reminders=[to_reminder_response(reminder) for reminder in reminders])


@app.post("/reminders/{reminder_id}/notified", response_model=ReminderNotifiedResponse)
async def reminder_notified(reminder_id: str) -> ReminderNotifiedResponse:
    reminder = await asyncio.to_thread(tool_storage.mark_reminder_notified, reminder_id)
    if reminder is None:
        return ReminderNotifiedResponse(success=False, reminder=None, message="没有找到该提醒。")

    return ReminderNotifiedResponse(
        success=True,
        reminder=to_reminder_response(reminder),
        message="提醒已标记为已通知。",
    )


@app.get("/scheduled-tasks/due", response_model=ScheduledTasksDueResponse)
async def scheduled_tasks_due() -> ScheduledTasksDueResponse:
    tasks = await asyncio.to_thread(tool_storage.due_scheduled_tasks)
    return ScheduledTasksDueResponse(tasks=[to_scheduled_task_response(task) for task in tasks])


@app.post("/scheduled-tasks/{task_id}/completed", response_model=ScheduledTaskCompletedResponse)
async def scheduled_task_completed(
    task_id: str,
    request: ScheduledTaskCompletedRequest,
) -> ScheduledTaskCompletedResponse:
    task = await asyncio.to_thread(
        tool_storage.mark_scheduled_task_completed,
        task_id,
        request.success,
        request.error,
    )
    if task is None:
        return ScheduledTaskCompletedResponse(success=False, task=None, message="没有找到该自动任务。")

    return ScheduledTaskCompletedResponse(
        success=True,
        task=to_scheduled_task_response(task),
        message="自动任务已更新下次执行时间。",
    )


def to_indexing_state_response(state) -> KnowledgeIndexingStateResponse | None:
    if state is None:
        return None
    return KnowledgeIndexingStateResponse(
        status=state.status,
        reason=state.reason,
        started_at=state.started_at,
        finished_at=state.finished_at,
        imported=state.imported,
        skipped=state.skipped,
        failed=state.failed,
        messages=state.messages or [],
        last_error=state.last_error,
    )


def to_reminder_response(reminder: ReminderItem) -> Reminder:
    return Reminder(
        id=reminder.id,
        title=reminder.title,
        remind_at=reminder.remind_at,
        completed=reminder.completed,
        created_at=reminder.created_at,
        completed_at=reminder.completed_at,
        notified_at=reminder.notified_at,
    )


def to_scheduled_task_response(task: ScheduledTaskItem) -> ScheduledTask:
    return ScheduledTask(
        id=task.id,
        title=task.title,
        enabled=task.enabled,
        schedule=task.schedule,
        action=task.action,
        next_run_at=task.next_run_at,
        created_at=task.created_at,
        last_run_at=task.last_run_at,
        last_status=task.last_status,
        last_error=task.last_error,
    )
