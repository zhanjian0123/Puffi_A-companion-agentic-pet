from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import settings


def _resolve_tools_root() -> Path:
    return Path(settings.tool_data_dir).expanduser().resolve()


@dataclass(slots=True)
class TodoItem:
    id: str
    title: str
    completed: bool
    created_at: str
    completed_at: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TodoItem":
        return cls(
            id=str(value.get("id", "")),
            title=str(value.get("title", "")),
            completed=bool(value.get("completed", False)),
            created_at=str(value.get("created_at", "")),
            completed_at=value.get("completed_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class ToolStorage:
    def __init__(self) -> None:
        self._root = _resolve_tools_root()
        self._root.mkdir(parents=True, exist_ok=True)

    def todos_path(self) -> Path:
        return self._resolve_controlled_file("todos.json")

    def load_todos(self) -> list[TodoItem]:
        path = self.todos_path()
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        items = [TodoItem.from_dict(item) for item in payload if isinstance(item, dict)]
        return [item for item in items if item.id and item.title]

    def save_todos(self, items: list[TodoItem]) -> None:
        path = self.todos_path()
        payload = [item.to_dict() for item in items]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def new_todo_id(self) -> str:
        return f"todo-{uuid4().hex[:12]}"

    def _resolve_controlled_file(self, filename: str) -> Path:
        path = (self._root / filename).resolve()

        if self._root not in path.parents and path != self._root:
            raise ValueError("Tool storage path escaped the allowed directory.")

        path.parent.mkdir(parents=True, exist_ok=True)
        return path


tool_storage = ToolStorage()
