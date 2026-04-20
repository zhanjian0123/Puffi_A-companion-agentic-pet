from models.dashscope import DashScopeChatModel
from rag.knowledge_base import knowledge_base
from schemas.chat import ChatRequest, ChatResponse
from tools.registry import tool_registry


SYSTEM_PROMPT = """你是一个桌面宠物助手，性格活泼可爱。
你可以帮助用户：
1. 回答问题和聊天
2. 管理个人知识库
3. 执行各种任务（通过工具）
4. 提醒和日程管理

保持回复简洁有趣，像一个真正的宠物伙伴。"""


class AgentService:
    def __init__(self) -> None:
        self.model = DashScopeChatModel()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        tools = tool_registry.list_tools()
        if not self.model.is_configured:
            return ChatResponse(
                response="我还没有连接到 AI 服务。请配置 DASHSCOPE_API_KEY 或使用本地 Ollama。",
                action=None,
            )

        completion = await self.model.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=request.message,
            tools=tools,
        )
        return ChatResponse(response=completion, action=None)

    async def search_knowledge(self, query: str) -> list[dict]:
        return await knowledge_base.search(query)
