import json

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from schemas import ChatRequest, ChatResponse, HealthResponse, HistoryResponse
from service import AgentService

agent_service = AgentService()
app = FastAPI(title="AI Pet Agent Service", version="0.2.0")


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
