from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import json
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


@dataclass(slots=True)
class ScheduledTaskItem:
    id: str
    title: str
    enabled: bool
    schedule: dict[str, Any]
    action: dict[str, Any]
    next_run_at: str
    created_at: str
    last_run_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScheduledTaskItem":
        schedule = value.get("schedule")
        action = value.get("action")
        return cls(
            id=str(value.get("id", "")),
            title=str(value.get("title", "")),
            enabled=bool(value.get("enabled", True)),
            schedule=schedule if isinstance(schedule, dict) else {},
            action=action if isinstance(action, dict) else {},
            next_run_at=str(value.get("next_run_at", "")),
            created_at=str(value.get("created_at", "")),
            last_run_at=value.get("last_run_at"),
            last_status=value.get("last_status"),
            last_error=value.get("last_error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "enabled": self.enabled,
            "schedule": self.schedule,
            "action": self.action,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "last_status": self.last_status,
            "last_error": self.last_error,
        }


class ToolStorage:
    def __init__(self) -> None:
        self._root = _resolve_tools_root()
        self._root.mkdir(parents=True, exist_ok=True)

    def todos_path(self) -> Path:
        return self._resolve_controlled_file("todos.json")

    def reminders_path(self) -> Path:
        return self._resolve_controlled_file("reminders.json")

    def scheduled_tasks_path(self) -> Path:
        return self._resolve_controlled_file("scheduled_tasks.json")

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

    def load_scheduled_tasks(self) -> list[ScheduledTaskItem]:
        path = self.scheduled_tasks_path()
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        items = [ScheduledTaskItem.from_dict(item) for item in payload if isinstance(item, dict)]
        return [item for item in items if item.id and item.title and item.next_run_at]

    def save_scheduled_tasks(self, items: list[ScheduledTaskItem]) -> None:
        path = self.scheduled_tasks_path()
        payload = [item.to_dict() for item in items]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def new_scheduled_task_id(self) -> str:
        return f"task-{uuid4().hex[:12]}"

    def create_daily_scheduled_task(
        self,
        title: str,
        time_of_day: str,
        prompt: str,
        timezone: str = "Asia/Shanghai",
    ) -> ScheduledTaskItem:
        schedule_time = self._parse_time_of_day(time_of_day)
        zone = self._resolve_timezone(timezone)
        now = datetime.now(zone)
        item = ScheduledTaskItem(
            id=self.new_scheduled_task_id(),
            title=title,
            enabled=True,
            schedule={
                "type": "daily",
                "time": schedule_time.strftime("%H:%M"),
                "timezone": zone.key,
            },
            action={
                "type": "agent_prompt",
                "prompt": prompt,
            },
            next_run_at=self._next_daily_run_at(schedule_time, zone, now).isoformat(timespec="seconds"),
            created_at=now.isoformat(timespec="seconds"),
        )

        items = self.load_scheduled_tasks()
        items.append(item)
        items.sort(key=lambda task: (not task.enabled, task.next_run_at, task.created_at))
        self.save_scheduled_tasks(items)
        return item

    def due_scheduled_tasks(self, now: datetime | None = None) -> list[ScheduledTaskItem]:
        current = now or datetime.now().astimezone()
        due: list[ScheduledTaskItem] = []
        for item in self.load_scheduled_tasks():
            if not item.enabled:
                continue
            next_run_at = self._parse_datetime(item.next_run_at)
            if next_run_at is not None and next_run_at.tzinfo is None:
                next_run_at = next_run_at.astimezone()
            if next_run_at is not None and next_run_at <= current:
                due.append(item)

        due.sort(key=lambda task: (task.next_run_at, task.created_at))
        return due

    def mark_scheduled_task_completed(
        self,
        task_id: str,
        success: bool,
        error: str | None = None,
        completed_at: datetime | None = None,
    ) -> ScheduledTaskItem | None:
        clean_id = task_id.strip()
        if not clean_id:
            return None

        now = completed_at or datetime.now().astimezone()
        items = self.load_scheduled_tasks()
        matched: ScheduledTaskItem | None = None
        for item in items:
            if item.id != clean_id:
                continue

            item.last_run_at = now.isoformat(timespec="seconds")
            item.last_status = "success" if success else "error"
            item.last_error = error
            item.next_run_at = self._calculate_next_run_at(item, now)
            matched = item
            break

        if matched is None:
            return None

        items.sort(key=lambda task: (not task.enabled, task.next_run_at, task.created_at))
        self.save_scheduled_tasks(items)
        return matched

    def remove_scheduled_task(self, task_id: str) -> ScheduledTaskItem | None:
        clean_id = task_id.strip()
        if not clean_id:
            return None

        items = self.load_scheduled_tasks()
        removed_item: ScheduledTaskItem | None = None
        remaining_items: list[ScheduledTaskItem] = []
        for item in items:
            if item.id == clean_id:
                removed_item = item
            else:
                remaining_items.append(item)

        if removed_item is None:
            return None

        self.save_scheduled_tasks(remaining_items)
        return removed_item

    def pause_scheduled_task(self, task_id: str) -> ScheduledTaskItem | None:
        clean_id = task_id.strip()
        if not clean_id:
            return None

        items = self.load_scheduled_tasks()
        matched: ScheduledTaskItem | None = None
        for item in items:
            if item.id == clean_id:
                item.enabled = False
                matched = item
                break

        if matched is None:
            return None

        items.sort(key=lambda task: (not task.enabled, task.next_run_at, task.created_at))
        self.save_scheduled_tasks(items)
        return matched

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
        parsed = self._parse_datetime(value)
        if parsed is not None and parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _parse_datetime(self, value: str) -> datetime | None:
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
            return parsed.astimezone()
        return parsed

    def _parse_time_of_day(self, value: str) -> time:
        normalized = value.strip()
        try:
            return datetime.strptime(normalized, "%H:%M").time()
        except ValueError as error:
            raise ValueError("time 必须使用 HH:mm 格式，例如 09:00。") from error

    def _resolve_timezone(self, value: str) -> ZoneInfo:
        normalized = value.strip() or "Asia/Shanghai"
        try:
            return ZoneInfo(normalized)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"不支持的时区：{normalized}") from error

    def _next_daily_run_at(self, time_of_day: time, zone: ZoneInfo, now: datetime) -> datetime:
        current = now.astimezone(zone)
        candidate = datetime.combine(current.date(), time_of_day, tzinfo=zone)
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate

    def _calculate_next_run_at(self, item: ScheduledTaskItem, now: datetime) -> str:
        if item.schedule.get("type") != "daily":
            return item.next_run_at

        time_value = str(item.schedule.get("time", "")).strip()
        timezone_value = str(item.schedule.get("timezone", "Asia/Shanghai")).strip()
        schedule_time = self._parse_time_of_day(time_value)
        zone = self._resolve_timezone(timezone_value)
        return self._next_daily_run_at(schedule_time, zone, now).isoformat(timespec="seconds")

    def _resolve_controlled_file(self, filename: str) -> Path:
        path = (self._root / filename).resolve()

        if self._root not in path.parents and path != self._root:
            raise ValueError("Tool storage path escaped the allowed directory.")

        path.parent.mkdir(parents=True, exist_ok=True)
        return path


tool_storage = ToolStorage()
