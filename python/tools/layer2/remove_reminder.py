from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def remove_reminder(reminder_id: str) -> str:
    """删除指定提醒。reminder_id 应来自 list_reminders 返回的 id。"""
    clean_id = reminder_id.strip()
    if not clean_id:
        return "请提供要删除的提醒 id。"

    items = tool_storage.load_reminders()
    remaining_items = [item for item in items if item.id != clean_id]

    if len(remaining_items) == len(items):
        return f"没有找到 id 为 {clean_id} 的提醒。"

    removed_item = next(item for item in items if item.id == clean_id)
    tool_storage.save_reminders(remaining_items)
    return f"已删除提醒：{removed_item.title}，时间：{removed_item.remind_at} (id: {removed_item.id})"
