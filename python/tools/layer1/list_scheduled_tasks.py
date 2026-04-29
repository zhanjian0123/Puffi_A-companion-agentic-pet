from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def list_scheduled_tasks(include_disabled: bool = False) -> str:
    """查看自动任务列表，返回每条任务的状态、计划时间、下次执行时间和编号。"""
    items = tool_storage.load_scheduled_tasks()
    if not include_disabled:
        items = [item for item in items if item.enabled]

    if not items:
        return "当前没有自动任务。" if include_disabled else "当前没有启用中的自动任务。"

    items.sort(key=lambda task: (not task.enabled, task.next_run_at, task.created_at))
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        status = "启用" if item.enabled else "停用"
        schedule_time = item.schedule.get("time", "未知时间")
        timezone = item.schedule.get("timezone", "未知时区")
        last_status = item.last_status or "尚未执行"
        lines.append(
            f"{index}. [{status}] 每天 {schedule_time} ({timezone}) - {item.title}，"
            f"下次执行：{item.next_run_at}，上次状态：{last_status} (id: {item.id})"
        )

    return "\n".join(lines)
