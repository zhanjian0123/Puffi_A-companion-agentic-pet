from __future__ import annotations

from inspect import isawaitable
from time import perf_counter
from typing import Any

from agents import Tool

from tools.layer1.get_current_date import get_current_date
from tools.layer1.get_current_time import get_current_time
from tools.layer1.knowledge_search import knowledge_search
from tools.layer1.list_todos import list_todos
from tools.layer2.add_todo import add_todo
from tools.layer2.complete_todo import complete_todo
from tools.layer2.create_or_update_skill import create_or_update_skill
from tools.layer2.remove_todo import remove_todo
from tools.layer2.write_knowledge_note import write_knowledge_note


SAFE_READ_ONLY_TOOLS: list[Tool] = [
    get_current_time,
    get_current_date,
    list_todos,
    knowledge_search,
]

CONTROLLED_WRITE_TOOLS: list[Tool] = [
    add_todo,
    complete_todo,
    remove_todo,
    create_or_update_skill,
    write_knowledge_note,
]


def _shorten(value: object, limit: int = 500) -> str:
    text = str(value)
    if len(text) <= limit:
        return text

    return f"{text[:limit]}...<truncated>"


def _with_tool_logs(tool: Tool) -> Tool:
    if getattr(tool, "_ai_pet_tool_logging_wrapped", False):
        return tool

    original_invoke = tool.on_invoke_tool
    tool_name = getattr(tool, "name", type(tool).__name__)

    async def logged_invoke(ctx: Any, input: str) -> Any:
        started_at = perf_counter()
        print(f"[Tool] start {tool_name} args={_shorten(input)}", flush=True)

        try:
            result = original_invoke(ctx, input)
            if isawaitable(result):
                result = await result
        except Exception as error:
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[Tool] error {tool_name} elapsed={elapsed_ms:.1f}ms error={_shorten(error)}",
                flush=True,
            )
            raise

        elapsed_ms = (perf_counter() - started_at) * 1000
        print(
            f"[Tool] success {tool_name} elapsed={elapsed_ms:.1f}ms result={_shorten(result)}",
            flush=True,
        )
        return result

    tool.on_invoke_tool = logged_invoke
    setattr(tool, "_ai_pet_tool_logging_wrapped", True)
    return tool


def build_agent_tools() -> list[Tool]:
    tools = [
        *SAFE_READ_ONLY_TOOLS,
        *CONTROLLED_WRITE_TOOLS,
    ]
    return [_with_tool_logs(tool) for tool in tools]
