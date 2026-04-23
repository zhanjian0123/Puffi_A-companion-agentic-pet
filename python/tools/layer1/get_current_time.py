from __future__ import annotations

from datetime import datetime

from agents import function_tool


@function_tool
def get_current_time() -> str:
    """获取当前本地时间，适合回答现在几点、当前时间安排之类的问题。"""
    return datetime.now().strftime("%H:%M:%S")
