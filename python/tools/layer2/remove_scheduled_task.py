from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def remove_scheduled_task(task_id: str) -> str:
    """删除指定自动任务。task_id 应来自 list_scheduled_tasks 返回的 id。"""
    clean_id = task_id.strip()
    if not clean_id:
        return "请提供要删除的自动任务 id。"

    item = tool_storage.remove_scheduled_task(clean_id)
    if item is None:
        return f"没有找到 id 为 {clean_id} 的自动任务。"

    schedule_time = item.schedule.get("time", "未知时间")
    timezone = item.schedule.get("timezone", "未知时区")
    return f"已删除自动任务：{item.title}，每天 {schedule_time} ({timezone}) (id: {item.id})"
