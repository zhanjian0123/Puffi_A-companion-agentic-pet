from __future__ import annotations

from agents import function_tool

from tools.storage import tool_storage


@function_tool
def add_scheduled_task(title: str, time: str, prompt: str, timezone: str = "Asia/Shanghai") -> str:
    """添加每天重复执行的自动任务。time 必须是 HH:mm，例如 09:00；prompt 是到点后要交给助手执行的完整指令。"""
    clean_title = " ".join(title.split()).strip()
    clean_time = " ".join(time.split()).strip()
    clean_prompt = prompt.strip()
    clean_timezone = " ".join(timezone.split()).strip() or "Asia/Shanghai"

    if not clean_title:
        return "任务标题不能为空，请提供明确的任务名称。"
    if not clean_time:
        return "任务时间不能为空，请使用 HH:mm 格式，例如 09:00。"
    if not clean_prompt:
        return "任务执行指令不能为空，请说明到点后要做什么。"

    try:
        item = tool_storage.create_daily_scheduled_task(
            title=clean_title,
            time_of_day=clean_time,
            prompt=clean_prompt,
            timezone=clean_timezone,
        )
    except ValueError as error:
        return str(error)

    return (
        f"已添加每日自动任务：{item.title}，时间：{item.schedule['time']} "
        f"({item.schedule['timezone']})，下次执行：{item.next_run_at} (id: {item.id})"
    )
