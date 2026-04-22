from fastapi import FastAPI, Query

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


@app.get("/history", response_model=HistoryResponse)
async def history(limit: int = Query(default=10, ge=1, le=50)) -> HistoryResponse:
    return await agent_service.history(limit)
