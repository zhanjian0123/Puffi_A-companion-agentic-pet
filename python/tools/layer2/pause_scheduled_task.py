from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def pause_scheduled_task(task_id: str) -> str:
    """停用指定自动任务但保留记录。task_id 应来自 list_scheduled_tasks 返回的 id。"""
    clean_id = task_id.strip()
    if not clean_id:
        return "请提供要停用的自动任务 id。"

    item = tool_storage.pause_scheduled_task(clean_id)
    if item is None:
        return f"没有找到 id 为 {clean_id} 的自动任务。"

    schedule_time = item.schedule.get("time", "未知时间")
    timezone = item.schedule.get("timezone", "未知时区")
    return f"已停用自动任务：{item.title}，每天 {schedule_time} ({timezone}) (id: {item.id})"
