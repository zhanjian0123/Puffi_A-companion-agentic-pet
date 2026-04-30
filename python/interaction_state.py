from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from config import settings


@dataclass(slots=True)
class InteractionState:
    last_user_chat_at: datetime | None = None


class InteractionStateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        root = Path(settings.tool_data_dir).expanduser().resolve()
        self._path = Path(path).expanduser().resolve() if path is not None else root / "interaction_state.json"

    async def load(self) -> InteractionState:
        return await asyncio.to_thread(self._load_sync)

    async def update_last_user_chat_at(self, value: datetime) -> None:
        await asyncio.to_thread(self._update_last_user_chat_at_sync, value)

    def _load_sync(self) -> InteractionState:
        if not self._path.exists():
            return InteractionState()

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return InteractionState()

        if not isinstance(payload, dict):
            return InteractionState()

        return InteractionState(last_user_chat_at=self._parse_datetime(payload.get("last_user_chat_at")))

    def _update_last_user_chat_at_sync(self, value: datetime) -> None:
        state = self._load_sync()
        last_user_chat_at = value
        ignored_older_value: datetime | None = None
        if state.last_user_chat_at is not None and state.last_user_chat_at > value:
            last_user_chat_at = state.last_user_chat_at
            ignored_older_value = value

        payload = {
            "last_user_chat_at": last_user_chat_at.isoformat(timespec="seconds"),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if ignored_older_value is not None:
            payload["ignored_older_user_chat_at"] = ignored_older_value.isoformat(timespec="seconds")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None

        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.astimezone()

        return parsed.astimezone()
