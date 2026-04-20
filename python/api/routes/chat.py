from fastapi import APIRouter

from agent.service import AgentService
from schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
agent_service = AgentService()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent_service.chat(request)
