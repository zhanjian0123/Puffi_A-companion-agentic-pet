from __future__ import annotations

from datetime import datetime

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def complete_reminder(reminder_id: str) -> str:
    """把指定提醒标记为完成。reminder_id 应来自 list_reminders 返回的 id。"""
    clean_id = reminder_id.strip()
    if not clean_id:
        return "请提供要完成的提醒 id。"

    items = tool_storage.load_reminders()
    for item in items:
        if item.id == clean_id:
            if item.completed:
                return f"提醒已经是完成状态：{item.title} (id: {item.id})"

            item.completed = True
            item.completed_at = datetime.now().isoformat(timespec="seconds")
            tool_storage.save_reminders(items)
            return f"已完成提醒：{item.title} (id: {item.id})"

    return f"没有找到 id 为 {clean_id} 的提醒。"
