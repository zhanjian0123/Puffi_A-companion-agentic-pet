from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(slots=True)
class ReminderItem:
    id: str
    title: str
    remind_at: str
    completed: bool
    created_at: str
    completed_at: str | None = None
    notified_at: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReminderItem":
        return cls(
            id=str(value.get("id", "")),
            title=str(value.get("title", "")),
            remind_at=str(value.get("remind_at", "")),
            completed=bool(value.get("completed", False)),
            created_at=str(value.get("created_at", "")),
            completed_at=value.get("completed_at"),
            notified_at=value.get("notified_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "remind_at": self.remind_at,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "notified_at": self.notified_at,
        }


class ToolStorage:
    def __init__(self) -> None:
        self._root = _resolve_tools_root()
        self._root.mkdir(parents=True, exist_ok=True)

    def todos_path(self) -> Path:
        return self._resolve_controlled_file("todos.json")

    def reminders_path(self) -> Path:
        return self._resolve_controlled_file("reminders.json")

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

    def load_reminders(self) -> list[ReminderItem]:
        path = self.reminders_path()
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        items = [ReminderItem.from_dict(item) for item in payload if isinstance(item, dict)]
        return [item for item in items if item.id and item.title and item.remind_at]

    def save_reminders(self, items: list[ReminderItem]) -> None:
        path = self.reminders_path()
        payload = [item.to_dict() for item in items]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def new_reminder_id(self) -> str:
        return f"reminder-{uuid4().hex[:12]}"

    def due_reminders(self, now: datetime | None = None) -> list[ReminderItem]:
        current = now or datetime.now()
        due: list[ReminderItem] = []
        for item in self.load_reminders():
            if item.completed or item.notified_at:
                continue
            remind_at = self._parse_remind_at(item.remind_at)
            if remind_at is not None and remind_at <= current:
                due.append(item)

        due.sort(key=lambda reminder: (reminder.remind_at, reminder.created_at))
        return due

    def mark_reminder_notified(self, reminder_id: str, notified_at: datetime | None = None) -> ReminderItem | None:
        clean_id = reminder_id.strip()
        if not clean_id:
            return None

        timestamp = (notified_at or datetime.now()).isoformat(timespec="seconds")
        items = self.load_reminders()
        matched: ReminderItem | None = None
        for item in items:
            if item.id == clean_id:
                item.notified_at = timestamp
                matched = item
                break

        if matched is None:
            return None

        self.save_reminders(items)
        return matched

    def _parse_remind_at(self, value: str) -> datetime | None:
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _resolve_controlled_file(self, filename: str) -> Path:
        path = (self._root / filename).resolve()

        if self._root not in path.parents and path != self._root:
            raise ValueError("Tool storage path escaped the allowed directory.")

        path.parent.mkdir(parents=True, exist_ok=True)
        return path


tool_storage = ToolStorage()
