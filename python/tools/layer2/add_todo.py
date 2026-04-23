from __future__ import annotations

from datetime import datetime

from agents import function_tool

from tools.storage import TodoItem, tool_storage


@function_tool
def add_todo(title: str) -> str:
    """添加一条新的待办事项。title 必须是简洁明确的待办内容。"""
    clean_title = " ".join(title.split()).strip()
    if not clean_title:
        return "待办内容不能为空，请提供明确的事项。"

    items = tool_storage.load_todos()
    item = TodoItem(
        id=tool_storage.new_todo_id(),
        title=clean_title,
        completed=False,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    items.append(item)
    tool_storage.save_todos(items)
    return f"已添加待办：{item.title} (id: {item.id})"
