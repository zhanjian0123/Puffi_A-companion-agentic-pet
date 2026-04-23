from __future__ import annotations

from datetime import datetime

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def complete_todo(todo_id: str) -> str:
    """把指定待办标记为完成。todo_id 应来自 list_todos 返回的 id。"""
    clean_id = todo_id.strip()
    if not clean_id:
        return "请提供要完成的待办 id。"

    items = tool_storage.load_todos()
    for item in items:
        if item.id == clean_id:
            if item.completed:
                return f"待办已经是完成状态：{item.title} (id: {item.id})"

            item.completed = True
            item.completed_at = datetime.now().isoformat(timespec="seconds")
            tool_storage.save_todos(items)
            return f"已完成待办：{item.title} (id: {item.id})"

    return f"没有找到 id 为 {clean_id} 的待办。"
