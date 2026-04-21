from __future__ import annotations

import json
from typing import Any

from config import settings
from rag.knowledge_base import knowledge_base
from tools.registry import tool_registry

try:
    from agents import Agent, Runner, function_tool
except ImportError:  # pragma: no cover - optional dependency
    Agent = None
    Runner = None
    function_tool = None


SYSTEM_PROMPT = """你是一个桌面宠物助手，性格活泼可爱。
你可以帮助用户：
1. 回答问题和聊天
2. 管理个人知识库
3. 执行各种任务（通过工具）
4. 提醒和日程管理

保持回复简洁有趣，像一个真正的宠物伙伴。"""


class OpenAIAgentsService:
    def __init__(self) -> None:
        self._agent = self._build_agent() if self.is_available else None

    @property
    def is_available(self) -> bool:
        return bool(
            settings.openai_api_key
            and Agent is not None
            and Runner is not None
            and function_tool is not None
        )

    async def chat(self, message: str) -> str:
        if not self._agent or Runner is None:
            raise RuntimeError("OpenAI Agents SDK is not available.")

        result = await Runner.run(self._agent, message)
        final_output = getattr(result, "final_output", "")

        if isinstance(final_output, str):
            return final_output

        if final_output is None:
            return ""

        return json.dumps(final_output, ensure_ascii=False)

    def _build_agent(self) -> Agent:
        if Agent is None or function_tool is None:
            raise RuntimeError("OpenAI Agents SDK is not installed.")

        tools = self._build_tools()
        return Agent(
            name="AI Pet Assistant",
            instructions=SYSTEM_PROMPT,
            model=settings.openai_model,
            tools=tools,
        )

    def _build_tools(self) -> list[Any]:
        if function_tool is None:
            return []

        @function_tool
        async def search_knowledge(query: str) -> dict[str, Any]:
            """Search the local knowledge base for notes related to the user's request."""
            return {"results": await knowledge_base.search(query)}

        @function_tool
        async def add_todo(text: str) -> dict[str, Any]:
            """Add a new todo item to the assistant's local task list."""
            return await tool_registry.invoke("todo.add", {"text": text})

        @function_tool
        async def list_todos() -> dict[str, Any]:
            """List the current todo items stored by the assistant."""
            return await tool_registry.invoke("todo.list", {})

        @function_tool
        async def notify_user(title: str, body: str) -> dict[str, Any]:
            """Create a local user notification request."""
            return await tool_registry.invoke("system.notify", {"title": title, "body": body})

        @function_tool
        async def capture_screenshot() -> dict[str, Any]:
            """Capture the current screen through the desktop bridge."""
            return await tool_registry.invoke("system.screenshot", {})

        return [
            search_knowledge,
            add_todo,
            list_todos,
            notify_user,
            capture_screenshot,
        ]
