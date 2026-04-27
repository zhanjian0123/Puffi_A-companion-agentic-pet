from __future__ import annotations

from datetime import datetime

from agents import function_tool

from tools.storage import ReminderItem, tool_storage


@function_tool
def add_reminder(title: str, remind_at: str) -> str:
    """添加提醒事项。remind_at 必须是明确时间，格式 YYYY-MM-DD HH:mm 或 YYYY-MM-DDTHH:mm:ss。"""
    clean_title = " ".join(title.split()).strip()
    clean_remind_at = " ".join(remind_at.split()).strip()
    if not clean_title:
        return "提醒内容不能为空，请提供明确的事项。"
    if not clean_remind_at:
        return "提醒时间不能为空，请提供明确时间。"

    items = tool_storage.load_reminders()
    item = ReminderItem(
        id=tool_storage.new_reminder_id(),
        title=clean_title,
        remind_at=clean_remind_at,
        completed=False,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    items.append(item)
    items.sort(key=lambda reminder: (reminder.completed, reminder.remind_at, reminder.created_at))
    tool_storage.save_reminders(items)
    return f"已添加提醒：{item.title}，时间：{item.remind_at} (id: {item.id})"
