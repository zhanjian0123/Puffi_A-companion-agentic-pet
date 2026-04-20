from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from rag.knowledge_base import knowledge_base


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


@dataclass(slots=True)
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)
    todos: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.register_defaults()

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.tools.values()
        ]

    async def invoke(self, tool_name: str, params: dict[str, Any]) -> Any:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": "Tool not found"}
        return await tool.handler(params)

    def register_defaults(self) -> None:
        self.register(
            Tool(
                name="system.screenshot",
                description="Capture current screen",
                input_schema={"type": "object", "properties": {}},
                handler=self._handle_screenshot,
            )
        )
        self.register(
            Tool(
                name="system.notify",
                description="Send system notification",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Notification title"},
                        "body": {"type": "string", "description": "Notification body"},
                    },
                },
                handler=self._handle_notify,
            )
        )
        self.register(
            Tool(
                name="kb.search",
                description="Search knowledge base",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
                handler=self._handle_search,
            )
        )
        self.register(
            Tool(
                name="todo.add",
                description="Add a new todo item",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Todo text"},
                    },
                    "required": ["text"],
                },
                handler=self._handle_todo_add,
            )
        )
        self.register(
            Tool(
                name="todo.list",
                description="List all todos",
                input_schema={"type": "object", "properties": {}},
                handler=self._handle_todo_list,
            )
        )

    async def _handle_screenshot(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "data": "screenshot_data"}

    async def _handle_notify(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "title": params.get("title"), "body": params.get("body")}

    async def _handle_search(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"results": await knowledge_base.search(params.get("query", ""))}

    async def _handle_todo_add(self, params: dict[str, Any]) -> dict[str, Any]:
        text = params.get("text", "")
        self.todos.append(text)
        return {"success": True, "text": text}

    async def _handle_todo_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"todos": list(self.todos)}


tool_registry = ToolRegistry()
