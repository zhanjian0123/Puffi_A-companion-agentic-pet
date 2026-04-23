from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def remove_todo(todo_id: str) -> str:
    """删除指定待办。todo_id 应来自 list_todos 返回的 id。"""
    clean_id = todo_id.strip()
    if not clean_id:
        return "请提供要删除的待办 id。"

    items = tool_storage.load_todos()
    remaining_items = [item for item in items if item.id != clean_id]

    if len(remaining_items) == len(items):
        return f"没有找到 id 为 {clean_id} 的待办。"

    removed_item = next(item for item in items if item.id == clean_id)
    tool_storage.save_todos(remaining_items)
    return f"已删除待办：{removed_item.title} (id: {removed_item.id})"
