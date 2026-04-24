from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MemoryCandidate:
    scope: str
    mode: str
    kind: str
    category: str
    section: str
    label: str
    summary: str
    raw_input: str
    items: tuple[str, ...] = ()


@dataclass(slots=True)
class MemoryCommandResult:
    action: str
    message: str
    internal_summary: str | None = None
    target: str | None = None
    user_visible: bool = True
