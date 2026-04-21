from agent.openai_sdk_service import OpenAIAgentsService
from rag.knowledge_base import knowledge_base
from schemas.chat import ChatRequest, ChatResponse


class AgentService:
    def __init__(self) -> None:
        self.openai_agents = OpenAIAgentsService()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.openai_agents.is_available:
            return ChatResponse(
                response=(
                    "我还没有连接到 OpenAI Agents SDK。请安装 openai-agents，"
                    "并配置 OPENAI_API_KEY 后再试。"
                ),
                action=None,
            )

        completion = await self.openai_agents.chat(request.message)
        return ChatResponse(response=completion, action=None)

    async def search_knowledge(self, query: str) -> list[dict]:
        return await knowledge_base.search(query)
