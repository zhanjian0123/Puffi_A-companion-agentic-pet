from __future__ import annotations

from agents import Tool

from tools.layer1.get_current_date import get_current_date
from tools.layer1.get_current_time import get_current_time
from tools.layer1.list_todos import list_todos
from tools.layer2.add_todo import add_todo
from tools.layer2.complete_todo import complete_todo
from tools.layer2.remove_todo import remove_todo


SAFE_READ_ONLY_TOOLS: list[Tool] = [
    get_current_time,
    get_current_date,
    list_todos,
]

CONTROLLED_WRITE_TOOLS: list[Tool] = [
    add_todo,
    complete_todo,
    remove_todo,
]


def build_agent_tools() -> list[Tool]:
    return [
        *SAFE_READ_ONLY_TOOLS,
        *CONTROLLED_WRITE_TOOLS,
    ]
