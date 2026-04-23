from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re

from memory.models import MemoryCandidate


CORE_TEMPLATE = """# Core Memory

## Stable Preferences

## Habits

## Collaboration Rules
"""

MODE_TEMPLATE = """# {mode_title} Mode Memory

## Goals

## Preferences

## Current State
"""

SKILL_INDEX_TEMPLATE = """# Skill Index

"""

SKILL_TEMPLATE = """---
name: {name}
description: {description}
version: "1.0.0"
tags:
{tags_yaml}
---

# Skill: {title}

## When To Use
{when_to_use}

## Triggers
{triggers}

## Instructions
{instructions}

## Examples
- Add examples for your common use-cases here.
"""


@dataclass(slots=True)
class MarkdownDocument:
    title: str
    section_order: list[str]
    sections: dict[str, list[str]]


class MarkdownMemoryStore:
    def __init__(
        self,
        memory_dir: str | Path,
        *,
        core_file_char_limit: int,
        mode_file_char_limit: int,
        skill_file_char_limit: int,
        skill_index_file_char_limit: int,
    ) -> None:
        self._memory_dir = Path(memory_dir).expanduser()
        self._modes_dir = self._memory_dir / "modes"
        self._skills_dir = self._memory_dir / "skills"
        self._core_file_char_limit = max(core_file_char_limit, 500)
        self._mode_file_char_limit = max(mode_file_char_limit, 500)
        self._skill_file_char_limit = max(skill_file_char_limit, 1200)
        self._skill_index_file_char_limit = max(skill_index_file_char_limit, 1000)
        self._initialize()

    async def read_core(self, char_limit: int) -> str:
        return await asyncio.to_thread(
            self._read_memory_context,
            self._core_path,
            CORE_TEMPLATE,
            char_limit,
        )

    async def read_mode(self, mode: str, char_limit: int) -> str:
        mode_path = self._mode_path(mode)
        await asyncio.to_thread(self._ensure_file, mode_path, self._mode_template(mode))
        return await asyncio.to_thread(
            self._read_memory_context,
            mode_path,
            self._mode_template(mode),
            char_limit,
        )

    async def upsert_memory(self, candidate: MemoryCandidate) -> tuple[Path, str]:
        return await asyncio.to_thread(self._upsert_memory_sync, candidate)

    async def forget_matching(self, *, scope: str | None, mode: str, query: str) -> list[Path]:
        paths: list[Path] = []
        if scope in {None, "core"}:
            paths.append(self._core_path)

        if scope in {None, "mode"}:
            mode_path = self._mode_path(mode)
            self._ensure_file(mode_path, self._mode_template(mode))
            paths.append(mode_path)

        changed: list[Path] = []
        for path in paths:
            changed_one = await asyncio.to_thread(self._remove_matching_lines, path, query)
            if changed_one:
                changed.append(path)

        return changed

    async def build_skill_context(
        self,
        *,
        message: str,
        index_char_limit: int,
        skill_file_char_limit: int,
        max_skills: int,
    ) -> str:
        if max_skills <= 0:
            return ""

        index_text = await asyncio.to_thread(
            self._read_limited,
            self._skill_index_path,
            index_char_limit,
        )
        matched = await asyncio.to_thread(
            self._match_skills,
            message,
            max_skills,
            skill_file_char_limit,
        )
        if not matched:
            return ""

        sections: list[str] = []
        if "- " in index_text:
            sections.append(f"Skill Index:\n{index_text}")

        for skill_name, skill_text in matched:
            sections.append(f"Matched Skill ({skill_name}):\n{skill_text}")

        return "\n\n".join(section for section in sections if section.strip())

    async def create_or_update_skill(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        triggers: str,
        tags: list[str] | None = None,
    ) -> Path:
        return await asyncio.to_thread(
            self.create_or_update_skill_sync,
            name,
            description,
            instructions,
            triggers,
            tags,
        )

    def create_or_update_skill_sync(
        self,
        name: str,
        description: str,
        instructions: str,
        triggers: str,
        tags: list[str] | None = None,
    ) -> Path:
        safe_name = self._safe_name(name)
        path = self._skill_path(safe_name)
        description_line = self._one_line(description, fallback=f"{safe_name} workflow skill")
        trigger_lines = self._as_bullets(triggers, fallback="- manual trigger")
        instruction_lines = self._as_bullets(instructions, fallback="- follow provided workflow")
        tags_yaml = self._tags_yaml(tags)

        body = SKILL_TEMPLATE.format(
            name=safe_name,
            description=description_line,
            tags_yaml=tags_yaml,
            title=self._title(safe_name),
            when_to_use=f"- {description_line}",
            triggers=trigger_lines,
            instructions=instruction_lines,
        )
        body = self._trim_to_limit(body, self._skill_file_char_limit)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        self._upsert_skill_index(name=safe_name, description=description_line, triggers=triggers)
        return path

    @property
    def _core_path(self) -> Path:
        return self._memory_dir / "core.md"

    @property
    def _skill_index_path(self) -> Path:
        return self._skills_dir / "index.md"

    def _mode_path(self, mode: str) -> Path:
        return self._modes_dir / f"{self._safe_name(mode)}.md"

    def _skill_path(self, skill_name: str) -> Path:
        return self._skills_dir / self._safe_name(skill_name) / "SKILL.md"

    def _initialize(self) -> None:
        self._modes_dir.mkdir(parents=True, exist_ok=True)
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self._core_path, CORE_TEMPLATE)
        self._ensure_file(self._mode_path("chat"), self._mode_template("chat"))
        self._ensure_file(self._skill_index_path, SKILL_INDEX_TEMPLATE)

    def _mode_template(self, mode: str) -> str:
        return MODE_TEMPLATE.format(mode_title=self._title(mode))

    def _ensure_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def _read_memory_context(self, path: Path, template: str, char_limit: int) -> str:
        if char_limit <= 0:
            return ""

        document = self._load_document(path, template)
        visible_sections = [
            section
            for section in document.section_order
            if any(line.strip() for line in document.sections.get(section, []))
        ]
        if not visible_sections:
            return ""

        lines = [document.title]
        for section in visible_sections:
            lines.append("")
            lines.append(f"## {section}")
            lines.extend(document.sections.get(section, []))

        return self._trim_to_limit("\n".join(lines).strip() + "\n", char_limit).strip()

    def _upsert_memory_sync(self, candidate: MemoryCandidate) -> tuple[Path, str]:
        path, template, file_limit = self._memory_target(candidate)
        document = self._load_document(path, template)

        action = self._upsert_stable_summary(document, candidate)
        rendered = self._render_document(document)
        rendered = self._trim_to_limit(rendered, file_limit)
        path.write_text(rendered, encoding="utf-8")

        if action == "ignored":
            return path, "ignored"

        return path, action

    def _memory_target(self, candidate: MemoryCandidate) -> tuple[Path, str, int]:
        if candidate.scope == "mode":
            return (
                self._mode_path(candidate.mode),
                self._mode_template(candidate.mode),
                self._mode_file_char_limit,
            )

        return self._core_path, CORE_TEMPLATE, self._core_file_char_limit

    def _load_document(self, path: Path, template: str) -> MarkdownDocument:
        self._ensure_file(path, template)
        text = path.read_text(encoding="utf-8")
        template_lines = template.strip().splitlines()
        title = template_lines[0].strip()
        section_order = [line[3:].strip() for line in template_lines if line.startswith("## ")]
        sections = {section: [] for section in section_order}

        current_section: str | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped
                continue
            if stripped.startswith("## "):
                section_name = stripped[3:].strip()
                if section_name in {"Notes", "Raw Inbox"}:
                    current_section = None
                    continue
                if section_name not in sections:
                    section_order.append(section_name)
                    sections[section_name] = []
                current_section = section_name
                continue
            if current_section is not None:
                sections[current_section].append(line.rstrip())

        return MarkdownDocument(title=title, section_order=section_order, sections=sections)

    def _render_document(self, document: MarkdownDocument) -> str:
        lines = [document.title]
        for section in document.section_order:
            lines.append("")
            lines.append(f"## {section}")
            content = [line for line in document.sections.get(section, []) if line.strip()]
            if content:
                lines.extend(content)

        return "\n".join(lines).rstrip() + "\n"

    def _upsert_stable_summary(self, document: MarkdownDocument, candidate: MemoryCandidate) -> str:
        section_lines = [line for line in document.sections.get(candidate.section, []) if line.strip()]
        exact_bullet = f"- {candidate.summary}"
        label_prefix = f"- {candidate.label}："

        for existing in section_lines:
            if existing.strip() == exact_bullet:
                document.sections[candidate.section] = section_lines
                return "ignored"

        if self._is_mergeable_preference(candidate):
            return self._merge_preference_summary(document, candidate, section_lines, label_prefix)

        replaced = False
        updated_lines: list[str] = []
        for existing in section_lines:
            if existing.startswith(label_prefix):
                updated_lines.append(exact_bullet)
                replaced = True
            else:
                updated_lines.append(existing)

        if not replaced:
            updated_lines.append(exact_bullet)

        document.sections[candidate.section] = updated_lines
        return "updated" if replaced else "created"

    def _is_mergeable_preference(self, candidate: MemoryCandidate) -> bool:
        return candidate.label in {"音乐偏好", "美食偏好", "游戏偏好"}

    def _merge_preference_summary(
        self,
        document: MarkdownDocument,
        candidate: MemoryCandidate,
        section_lines: list[str],
        label_prefix: str,
    ) -> str:
        candidate_items = self._extract_preference_items(candidate.summary)
        if not candidate_items:
            return "ignored"

        merged = False
        changed = False
        updated_lines: list[str] = []
        for existing in section_lines:
            if self._is_bad_generic_preference(existing):
                changed = True
                continue

            if not existing.startswith(label_prefix):
                updated_lines.append(existing)
                continue

            existing_items = self._extract_preference_items(existing)
            all_items = [*existing_items]
            for item in candidate_items:
                if item not in all_items:
                    all_items.append(item)
                    changed = True

            updated_lines.append(f"- {self._format_preference_summary(candidate.label, all_items)}")
            merged = True

        if not merged:
            updated_lines.append(f"- {self._format_preference_summary(candidate.label, candidate_items)}")
            changed = True

        document.sections[candidate.section] = updated_lines
        if not changed:
            return "ignored"

        return "updated" if merged else "created"

    def _extract_preference_items(self, summary: str) -> list[str]:
        if "：" not in summary:
            return []

        _, value = summary.split("：", 1)
        cleaned = value.strip().strip("。")
        for prefix in ("喜欢玩", "喜欢吃", "喜欢", "偏好"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break

        return [
            item.strip()
            for item in re.split(r"[、,，和]+", cleaned)
            if item.strip()
        ]

    def _format_preference_summary(self, label: str, items: list[str]) -> str:
        joined = "、".join(items)
        if label == "美食偏好":
            return f"{label}：喜欢吃{joined}。"

        if label == "游戏偏好":
            return f"{label}：喜欢玩{joined}。"

        return f"{label}：喜欢{joined}。"

    def _is_bad_generic_preference(self, line: str) -> bool:
        return line.startswith("- 长期偏好：") and any(
            marker in line
            for marker in ("我还喜欢", "我喜欢", "喜欢听", "喜欢吃", "喜欢玩")
        )

    def _remove_matching_lines(self, path: Path, query: str) -> bool:
        if not path.exists():
            return False

        normalized_query = query.strip().lower()
        if not normalized_query:
            return False

        changed = False
        kept_lines: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if normalized_query in line.lower() and line.lstrip().startswith("- "):
                changed = True
                continue
            kept_lines.append(line)

        if changed:
            path.write_text("\n".join(kept_lines).rstrip() + "\n", encoding="utf-8")

        return changed

    def _read_limited(self, path: Path, char_limit: int) -> str:
        if char_limit <= 0 or not path.exists():
            return ""

        text = path.read_text(encoding="utf-8").strip()
        if len(text) <= char_limit:
            return text

        return text[:char_limit].rstrip() + "\n[truncated]"

    def _match_skills(
        self,
        message: str,
        max_skills: int,
        skill_file_char_limit: int,
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[int, str, Path]] = []
        for path in self._skills_dir.glob("*/SKILL.md"):
            content = path.read_text(encoding="utf-8")
            skill_name = path.parent.name
            score = self._score(message, content) + self._score(message, skill_name.replace("-", " "))
            if score >= 2:
                candidates.append((score, skill_name, path))

        candidates.sort(key=lambda item: item[0], reverse=True)
        matched: list[tuple[str, str]] = []
        for _, skill_name, path in candidates[:max_skills]:
            matched.append((skill_name, self._read_limited(path, skill_file_char_limit)))

        return matched

    def _upsert_skill_index(self, *, name: str, description: str, triggers: str) -> None:
        self._ensure_file(self._skill_index_path, SKILL_INDEX_TEMPLATE)
        lines = self._skill_index_path.read_text(encoding="utf-8").splitlines()
        prefix = f"- {name}:"
        kept = [line for line in lines if not line.startswith(prefix)]
        trigger_text = self._one_line(triggers, fallback="manual trigger")
        kept.append(f"- {name}: {description} | triggers: {trigger_text}")
        updated = "\n".join(kept).rstrip() + "\n"
        updated = self._trim_to_limit(updated, self._skill_index_file_char_limit)
        self._skill_index_path.write_text(updated, encoding="utf-8")

    def _tags_yaml(self, tags: list[str] | None) -> str:
        normalized = [self._safe_name(tag) for tag in (tags or []) if tag.strip()]
        if not normalized:
            normalized = ["desktop-pet", "workflow"]

        return "\n".join(f"  - {tag}" for tag in normalized)

    def _as_bullets(self, value: str, fallback: str) -> str:
        text = value.strip()
        if not text:
            return fallback

        if "\n" in text:
            parts = [part.strip() for part in text.splitlines() if part.strip()]
            if all(part.startswith("- ") for part in parts):
                return "\n".join(parts)
            return "\n".join(f"- {part.lstrip('- ').strip()}" for part in parts)

        if text.startswith("- "):
            return text

        return f"- {text}"

    def _trim_to_limit(self, value: str, char_limit: int) -> str:
        if len(value) <= char_limit:
            return value.rstrip() + "\n"

        marker = "\n[truncated]\n"
        payload_limit = max(char_limit - len(marker), 0)
        return value[:payload_limit].rstrip() + marker

    def _score(self, a: str, b: str) -> int:
        tokens_a = self._tokens(a)
        tokens_b = self._tokens(b)
        if not tokens_a or not tokens_b:
            return 0

        return len(tokens_a & tokens_b)

    def _tokens(self, text: str) -> set[str]:
        lowered = text.lower()
        words = set(re.findall(r"[a-z0-9_]+", lowered))
        cjk_chars = {char for char in lowered if "\u4e00" <= char <= "\u9fff"}
        return words | cjk_chars

    def _safe_name(self, value: str) -> str:
        lowered = value.strip().lower()
        safe = re.sub(r"[^a-z0-9_-]+", "-", lowered).strip("-")
        return safe or "default"

    def _title(self, value: str) -> str:
        return " ".join(part.capitalize() for part in self._safe_name(value).split("-"))

    def _one_line(self, value: str, fallback: str) -> str:
        text = re.sub(r"\s+", " ", value.strip())
        return text if text else fallback
