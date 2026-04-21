from fastapi import APIRouter
from agent.service import AgentService

router = APIRouter(tags=["health"])
agent_service = AgentService()


@router.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "runtime": "openai-agents-sdk",
        "configured": agent_service.openai_agents.is_available,
    }
