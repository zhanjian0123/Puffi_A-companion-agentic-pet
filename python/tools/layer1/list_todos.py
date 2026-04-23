from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def list_todos() -> str:
    """查看当前待办列表，返回每条待办的状态、标题和编号。"""
    items = tool_storage.load_todos()
    if not items:
        return "当前还没有待办事项。"

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        status = "已完成" if item.completed else "未完成"
        lines.append(f"{index}. [{status}] {item.title} (id: {item.id})")

    return "\n".join(lines)
