from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def list_reminders(include_completed: bool = False) -> str:
    """查看提醒列表，返回每条提醒的状态、时间、标题和编号。"""
    items = tool_storage.load_reminders()
    if not include_completed:
        items = [item for item in items if not item.completed]

    if not items:
        return "当前没有提醒事项。" if include_completed else "当前没有未完成的提醒事项。"

    items.sort(key=lambda reminder: (reminder.completed, reminder.remind_at, reminder.created_at))
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        status = "已完成" if item.completed else "未完成"
        lines.append(f"{index}. [{status}] {item.remind_at} - {item.title} (id: {item.id})")

    return "\n".join(lines)
