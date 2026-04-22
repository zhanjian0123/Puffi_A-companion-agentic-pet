from __future__ import annotations

from pathlib import Path
from typing import Any

from schemas import HistoryMessage

try:
    from agents.memory.session_settings import SessionSettings
    from agents.memory.sqlite_session import SQLiteSession
except ImportError:  # pragma: no cover - optional dependency
    SessionSettings = None
    SQLiteSession = None


class AgentSessionStore:
    def __init__(
        self,
        session_id: str,
        db_path: str | Path,
        context_limit: int | None = None,
    ) -> None:
        self._session = None

        if SQLiteSession is None:
            return

        resolved_path = Path(db_path).expanduser()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        session_settings = None
        if SessionSettings is not None and context_limit is not None:
            session_settings = SessionSettings(limit=context_limit)

        self._session = SQLiteSession(
            session_id=session_id,
            db_path=resolved_path,
            session_settings=session_settings,
        )

    @property
    def session(self) -> SQLiteSession | None:
        return self._session

    async def get_recent_messages(self, limit: int) -> list[HistoryMessage]:
        if self._session is None:
            return []

        raw_items = await self._session.get_items(limit=max(limit * 4, limit))
        messages: list[HistoryMessage] = []

        for item in raw_items:
            message = self._normalize_message(item)
            if message is not None:
                messages.append(message)

        return messages[-limit:]

    def _normalize_message(self, item: Any) -> HistoryMessage | None:
        if not isinstance(item, dict):
            return None

        role = item.get("role")
        if role not in {"user", "assistant"}:
            return None

        content = self._extract_text(item.get("content"))
        if not content:
            return None

        return HistoryMessage(role=role, content=content)

    def _extract_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, list):
            parts = [self._extract_text(item) for item in value]
            return "\n".join(part for part in parts if part).strip()

        if isinstance(value, dict):
            if "text" in value:
                text = self._extract_text(value["text"])
                if text:
                    return text

            if "content" in value:
                text = self._extract_text(value["content"])
                if text:
                    return text

            if "value" in value:
                text = self._extract_text(value["value"])
                if text:
                    return text

        return ""
