from __future__ import annotations

from datetime import datetime

from agents import function_tool


@function_tool
def get_current_date() -> str:
    """获取当前本地日期和星期，适合回答今天几号、周几等问题。"""
    return datetime.now().strftime("%Y-%m-%d %A")
