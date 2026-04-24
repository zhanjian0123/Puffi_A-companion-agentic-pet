from __future__ import annotations

from pathlib import Path
import re

from memory.models import MemoryCandidate, MemoryCommandResult
from memory.store import MarkdownMemoryStore


class MemoryService:
    def __init__(
        self,
        *,
        memory_dir: str,
        core_char_limit: int,
        mode_char_limit: int,
        skill_index_char_limit: int,
        skill_file_char_limit: int,
        max_skills_per_request: int,
        core_file_char_limit: int,
        mode_file_char_limit: int,
        skill_file_max_chars: int,
        skill_index_file_max_chars: int,
        auto_capture: bool = True,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._auto_capture = auto_capture
        self._core_char_limit = core_char_limit
        self._mode_char_limit = mode_char_limit
        self._skill_index_char_limit = skill_index_char_limit
        self._skill_file_char_limit = skill_file_char_limit
        self._max_skills_per_request = max_skills_per_request
        self._store = MarkdownMemoryStore(
            memory_dir,
            core_file_char_limit=core_file_char_limit,
            mode_file_char_limit=mode_file_char_limit,
            skill_file_char_limit=skill_file_max_chars,
            skill_index_file_char_limit=skill_index_file_max_chars,
        )

    async def apply_explicit_commands(
        self,
        *,
        message: str,
        mode: str,
    ) -> list[MemoryCommandResult]:
        if not self._enabled:
            return []

        if self._is_forget_message(message):
            return await self._forget_from_message(message=message, mode=mode)

        if self._is_remember_message(message):
            result = await self._remember_from_message(
                message=message,
                mode=mode,
                explicit=True,
            )
            return [result] if result is not None else []

        if self._auto_capture and self._should_auto_capture(message):
            result = await self._remember_from_message(
                message=message,
                mode=mode,
                explicit=False,
            )
            if result is not None:
                result.user_visible = False
            return [result] if result is not None else []

        return []

    async def build_context(self, *, message: str, mode: str) -> str:
        if not self._enabled:
            return ""

        core_memory = await self._store.read_core(self._core_char_limit)
        mode_memory = await self._store.read_mode(mode, self._mode_char_limit)
        skill_context = await self._store.build_skill_context(
            message=message,
            index_char_limit=self._skill_index_char_limit,
            skill_file_char_limit=self._skill_file_char_limit,
            max_skills=self._max_skills_per_request,
        )

        sections: list[str] = []
        if core_memory:
            sections.append(f"长期核心记忆（Markdown，已按长度限制截断）：\n{core_memory}")

        if mode_memory:
            sections.append(f"当前模式记忆（{mode}，Markdown，已按长度限制截断）：\n{mode_memory}")

        if skill_context:
            sections.append(f"可复用技能（Markdown，按需匹配并限制数量）：\n{skill_context}")

        return "\n\n".join(sections)

    def should_short_circuit_response(
        self,
        *,
        message: str,
        command_results: list[MemoryCommandResult],
    ) -> bool:
        if not command_results:
            return False

        text = message.strip()
        if any(mark in text for mark in ("？", "?")):
            return False

        if self._is_forget_message(text) or self._is_remember_message(text):
            return True

        return False

    def format_acknowledgement(self, command_results: list[MemoryCommandResult]) -> str:
        if not command_results:
            return ""

        return "\n".join(
            result.message
            for result in command_results
            if result.message and result.user_visible
        ).strip()

    def format_runtime_notes(self, command_results: list[MemoryCommandResult]) -> list[str]:
        notes: list[str] = []
        for result in command_results:
            if result.internal_summary:
                notes.append(f"{result.action}: {result.internal_summary}")
            elif result.message:
                notes.append(result.message)

        return notes

    async def _remember_from_message(
        self,
        *,
        message: str,
        mode: str,
        explicit: bool,
    ) -> MemoryCommandResult | None:
        candidate = self._extract_candidate(message=message, mode=mode, explicit=explicit)
        if candidate is None:
            return None

        path, action = await self._store.upsert_memory(candidate)
        target_name = "当前模式记忆" if candidate.scope == "mode" else "核心记忆"

        if action == "ignored":
            result = MemoryCommandResult(
                action=action,
                message=self._user_acknowledgement(candidate, action),
                internal_summary=candidate.summary,
                target=self._relative_target(path),
            )
            self._log_memory_result(result, candidate)
            return result

        verb = "更新" if action == "updated" else "记录"
        result = MemoryCommandResult(
            action=action,
            message=self._user_acknowledgement(candidate, action),
            internal_summary=candidate.summary,
            target=self._relative_target(path),
        )
        self._log_memory_result(result, candidate, target_name=target_name, verb=verb)
        return result

    async def _forget_from_message(self, *, message: str, mode: str) -> list[MemoryCommandResult]:
        query = self._clean_forget_content(message)
        if not query:
            return [
                MemoryCommandResult(
                    action="forget",
                    message="我需要知道你想忘记哪条记忆。",
                )
            ]

        scope = self._detect_scope(message) if self._mentions_specific_scope(message) else None
        changed_paths = await self._store.forget_matching(scope=scope, mode=mode, query=query)

        if not changed_paths:
            return [
                MemoryCommandResult(
                    action="forget",
                    message="我查了一下，还没找到对应的记忆。",
                )
            ]

        result = MemoryCommandResult(
            action="forget",
            message="已经忘掉相关记忆啦。",
            internal_summary=f"deleted {len(changed_paths)} matching memory item(s)",
            target=", ".join(self._relative_target(path) for path in changed_paths),
        )
        print(
            f"[Memory] forget matches={len(changed_paths)} target={result.target}",
            flush=True,
        )
        return [
            result
        ]

    def _extract_candidate(
        self,
        *,
        message: str,
        mode: str,
        explicit: bool,
    ) -> MemoryCandidate | None:
        raw_input = self._clean_memory_content(message, explicit=explicit)
        normalized = re.sub(r"\s+", "", raw_input)
        if not normalized:
            return None

        scope = self._detect_scope(message)
        kind = self._detect_kind(normalized)
        candidate = self._build_candidate(
            scope=scope,
            mode=mode,
            kind=kind,
            raw_input=raw_input,
            normalized=normalized,
            explicit=explicit,
        )
        if candidate is not None:
            return candidate

        if explicit:
            return MemoryCandidate(
                scope=scope,
                mode=mode,
                kind="preference",
                category="general",
                section="Stable Preferences" if scope == "core" else "Preferences",
                label="长期偏好",
                summary=f"长期偏好：{self._normalize_sentence(raw_input)}",
                raw_input=raw_input,
            )

        return None

    def _build_candidate(
        self,
        *,
        scope: str,
        mode: str,
        kind: str,
        raw_input: str,
        normalized: str,
        explicit: bool,
    ) -> MemoryCandidate | None:
        category = self._infer_category(kind=kind, raw_input=raw_input, normalized=normalized)
        section = self._section_for(kind=kind, scope=scope)
        label = self._label_for(kind=kind, category=category)

        if kind == "preference":
            items = self._extract_preference_items(raw_input=raw_input, normalized=normalized, category=category)
            summary = self._build_preference_summary(
                raw_input=raw_input,
                normalized=normalized,
                category=category,
                label=label,
                items=items,
            )
            if not summary:
                return None

            return MemoryCandidate(
                scope=scope,
                mode=mode,
                kind=kind,
                category=category,
                section=section,
                label=label,
                summary=summary,
                raw_input=raw_input,
                items=tuple(items),
            )

        if kind == "habit":
            detail = self._extract_habit_detail(raw_input)
            if not detail:
                return None
            return MemoryCandidate(
                scope=scope,
                mode=mode,
                kind=kind,
                category=category,
                section=section,
                label=label,
                summary=f"{label}：{detail}",
                raw_input=raw_input,
            )

        if kind == "goal":
            detail = self._extract_goal_detail(raw_input)
            if not detail:
                return None
            return MemoryCandidate(
                scope=scope,
                mode=mode,
                kind=kind,
                category=category,
                section=section,
                label=label,
                summary=f"{label}：{detail}",
                raw_input=raw_input,
            )

        if kind == "profile":
            detail = self._extract_profile_detail(raw_input)
            if not detail:
                return None
            return MemoryCandidate(
                scope=scope,
                mode=mode,
                kind=kind,
                category=category,
                section=section,
                label=label,
                summary=f"{label}：{detail}",
                raw_input=raw_input,
            )

        detail = self._extract_rule_detail(raw_input)
        if not detail:
            return None
        return MemoryCandidate(
            scope=scope,
            mode=mode,
            kind="rule",
            category=category,
            section=section,
            label=label,
            summary=f"{label}：{detail}",
            raw_input=raw_input,
        )

    def _detect_kind(self, normalized: str) -> str:
        if any(token in normalized for token in ("喜欢", "爱", "偏好", "不喜欢", "讨厌", "想吃", "想听", "想玩")):
            return "preference"

        if any(token in normalized for token in ("目标", "计划", "准备", "想要", "希望做到", "打算")):
            return "goal"

        if any(token in normalized for token in ("我是", "来自", "职业", "工作是", "身份")):
            return "profile"

        if any(token in normalized for token in ("习惯", "平常", "通常", "一般", "经常")):
            return "habit"

        return "rule"

    def _infer_category(self, *, kind: str, raw_input: str, normalized: str) -> str:
        lowered = normalized.lower()

        if "codex" in lowered or any(token in normalized for token in ("写代码", "编码", "代码", "开发")):
            if any(token in normalized for token in ("方案", "先", "再")):
                return "coding_workflow"
            if kind == "habit":
                return "coding_workflow"

        if self._extract_food_name(normalized):
            return "food"

        if self._extract_music_name(normalized):
            return "music"

        if self._extract_game_name(normalized):
            return "game"

        if any(token in normalized for token in ("回答", "解释", "语气", "简洁", "详细", "直接", "精简")):
            return "communication_style"

        if any(token in normalized for token in ("学习", "背单词", "复习", "刷题", "考试")):
            return "learning"

        if any(token in normalized for token in ("上班", "工作", "效率", "专注", "提醒")):
            return "work_style"

        return "general"

    def _section_for(self, *, kind: str, scope: str) -> str:
        if kind == "preference":
            return "Stable Preferences" if scope == "core" else "Preferences"
        if kind == "habit":
            return "Habits" if scope == "core" else "Current State"
        if kind == "goal":
            return "Stable Preferences" if scope == "core" else "Goals"
        if kind == "profile":
            return "Stable Preferences" if scope == "core" else "Current State"
        return "Collaboration Rules" if scope == "core" else "Preferences"

    def _label_for(self, *, kind: str, category: str) -> str:
        if kind == "preference":
            label_map = {
                "food": "美食偏好",
                "music": "音乐偏好",
                "game": "游戏偏好",
                "coding_workflow": "编码协作偏好",
                "communication_style": "交流偏好",
                "learning": "学习偏好",
                "work_style": "工作偏好",
            }
            return label_map.get(category, "长期偏好")

        if kind == "habit":
            label_map = {
                "coding_workflow": "编码习惯",
                "learning": "学习习惯",
                "work_style": "工作习惯",
            }
            return label_map.get(category, "使用习惯")

        if kind == "goal":
            return "长期目标"

        if kind == "profile":
            return "个人信息"

        return "协作规则"

    def _extract_preference_items(self, *, raw_input: str, normalized: str, category: str) -> list[str]:
        if category == "food":
            known = self._extract_known_items(
                normalized,
                ("冰激凌", "冰淇淋", "拉面", "牛肉面", "火锅", "寿司", "烧烤", "辣椒", "草莓", "川菜", "湘菜", "麻辣烫"),
            )
            extracted = known or self._extract_list_after_patterns(
                raw_input,
                patterns=("喜欢吃", "爱吃", "想吃", "喜欢喝", "爱喝", "想喝", "吃", "喝"),
            )
            return self._clean_extracted_items(extracted)

        if category == "music":
            known = self._extract_known_items(
                normalized,
                ("流行音乐", "民谣", "摇滚", "爵士", "古典", "电子音乐", "说唱"),
            )
            extracted = known or self._extract_list_after_patterns(
                raw_input,
                patterns=("喜欢听", "爱听", "想听", "听", "喜欢"),
            )
            return self._clean_extracted_items(extracted)

        if category == "game":
            game = self._extract_game_name(normalized)
            extracted = [game] if game else self._extract_list_after_patterns(
                raw_input,
                patterns=("喜欢玩", "爱玩", "想玩", "玩"),
            )
            return self._clean_extracted_items(extracted)

        if category in {"learning", "work_style", "general"}:
            extracted = self._extract_list_after_patterns(
                raw_input,
                patterns=("喜欢", "偏好", "希望", "想要"),
            )
            return self._clean_extracted_items(extracted)

        return []

    def _build_preference_summary(
        self,
        *,
        raw_input: str,
        normalized: str,
        category: str,
        label: str,
        items: list[str],
    ) -> str:
        if category == "coding_workflow":
            detail = self._extract_coding_workflow_detail(raw_input, normalized)
            return f"{label}：{detail}" if detail else ""

        if label == "美食偏好" and items:
            return f"{label}：喜欢吃{'、'.join(items)}。"

        if label == "游戏偏好" and items:
            return f"{label}：喜欢玩{'、'.join(items)}。"

        if items:
            return f"{label}：喜欢{'、'.join(items)}。"

        detail = self._extract_preference_detail(raw_input)
        return f"{label}：{detail}" if detail else ""

    def _extract_preference_detail(self, message: str) -> str:
        message = self._clean_memory_content(message, explicit=False)
        if "听流行音乐" in message or "流行音乐" in message:
            return "喜欢流行音乐。"

        detail = message
        prefixes = (
            "我喜欢",
            "我不喜欢",
            "我希望",
            "我的偏好是",
            "我的偏好",
            "记住我喜欢",
            "记住我希望",
        )
        for prefix in prefixes:
            if detail.startswith(prefix):
                detail = detail[len(prefix):].strip(" ，,。")
                break

        if not detail:
            return ""

        if detail.startswith("听"):
            return f"喜欢{detail[1:]}。"

        if detail.startswith("吃"):
            return f"喜欢吃{detail[1:].rstrip('。')}。"

        if "偏好" in detail:
            return self._normalize_sentence(detail)

        return f"喜欢{detail.rstrip('。')}。"

    def _extract_goal_detail(self, message: str) -> str:
        detail = self._clean_memory_content(message, explicit=False)
        prefixes = (
            "我的目标是",
            "我的计划是",
            "我打算",
            "我准备",
            "我想要",
            "我想",
        )
        for prefix in prefixes:
            if detail.startswith(prefix):
                detail = detail[len(prefix):].strip(" ，,。")
                break

        return self._normalize_sentence(detail)

    def _extract_profile_detail(self, message: str) -> str:
        detail = self._clean_memory_content(message, explicit=False)
        prefixes = ("我是", "我来自", "我的职业是", "我做", "我的身份是")
        for prefix in prefixes:
            if detail.startswith(prefix):
                detail = detail[len(prefix):].strip(" ，,。")
                break

        return self._normalize_sentence(detail)

    def _extract_habit_detail(self, message: str) -> str:
        detail = self._clean_memory_content(message, explicit=False)
        prefixes = (
            "我平常",
            "我一般",
            "我通常",
            "我习惯",
            "我经常",
        )
        for prefix in prefixes:
            if detail.startswith(prefix):
                detail = detail[len(prefix):].strip(" ，,。")
                break

        normalized = self._normalize_sentence(detail)
        return normalized

    def _extract_rule_detail(self, message: str) -> str:
        normalized = self._normalize_sentence(self._clean_memory_content(message, explicit=False))
        if not normalized.endswith("。"):
            normalized += "。"
        return normalized

    def _extract_coding_workflow_detail(self, message: str, normalized: str) -> str:
        lowered = normalized.lower()
        if "codex" in lowered and any(token in normalized for token in ("方案", "编码", "写代码", "代码")):
            if "先" in normalized and "再" in normalized:
                return "使用 Codex 写代码时，偏好先给方案，再进行编码。"
            return "使用 Codex 写代码时，偏好先沟通方案，再进行编码。"

        detail = self._normalize_sentence(message)
        return detail

    def _extract_list_after_patterns(self, text: str, *, patterns: tuple[str, ...]) -> list[str]:
        cleaned = self._clean_memory_content(text, explicit=False)
        for pattern in patterns:
            if pattern not in cleaned:
                continue
            fragment = cleaned.split(pattern, 1)[1].strip(" ：:，,。")
            if not fragment:
                continue
            return [
                item.strip()
                for item in re.split(r"[、,，和及跟/]+", fragment)
                if item.strip()
            ]

        return []

    def _extract_known_items(self, normalized: str, known_values: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        for value in known_values:
            alias = "冰激凌" if value == "冰淇淋" else value
            if value in normalized and alias not in found:
                found.append(alias)

        return found

    def _clean_extracted_items(self, items: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            normalized = item.strip(" ，,。！？；:：")
            normalized = re.sub(r"^(我|也|还|更|最|平常|通常|一般)", "", normalized).strip()
            normalized = re.sub(r"(呢|呀|哦|啊)$", "", normalized).strip()
            if not normalized:
                continue
            if normalized not in cleaned:
                cleaned.append(normalized)

        return cleaned

    def _normalize_sentence(self, text: str) -> str:
        normalized = text.strip().strip("，,。")
        normalized = normalized.replace("codex", "Codex").replace("CODEx", "Codex")
        normalized = re.sub(r"\s+", " ", normalized)
        if not normalized:
            return ""
        if not normalized.endswith("。"):
            normalized += "。"
        return normalized

    def _extract_food_name(self, normalized: str) -> str:
        for food in (
            "冰激凌",
            "冰淇淋",
            "拉面",
            "牛肉面",
            "火锅",
            "寿司",
            "烧烤",
            "辣椒",
            "草莓",
            "川菜",
            "湘菜",
            "麻辣烫",
        ):
            if food in normalized:
                return "冰激凌" if food == "冰淇淋" else food

        match = re.search(r"(?:喜欢|爱|想)?吃([^\s，。！？；、]+)", normalized)
        if match:
            return match.group(1)

        return ""

    def _extract_music_name(self, normalized: str) -> str:
        for genre in ("流行音乐", "民谣", "摇滚", "爵士", "古典", "电子音乐", "说唱"):
            if genre in normalized:
                return genre

        return ""

    def _extract_game_name(self, normalized: str) -> str:
        game_aliases = {
            "英雄联盟": ("英雄联盟", "lol", "leagueoflegends"),
            "王者荣耀": ("王者荣耀",),
            "原神": ("原神",),
            "塞尔达": ("塞尔达",),
        }
        lowered = normalized.lower()
        for game, aliases in game_aliases.items():
            if any(alias in lowered for alias in aliases):
                return game

        return ""

    def _user_acknowledgement(self, candidate: MemoryCandidate, action: str) -> str:
        if action == "ignored":
            return self._duplicate_acknowledgement(candidate)

        if candidate.label == "美食偏好":
            food = self._extract_food_name(candidate.summary)
            if candidate.scope == "mode":
                return f"记住啦，在这个模式下我会记得你喜欢吃{food}。"
            return f"记住啦，以后聊到吃的我会记得你喜欢{food}。"

        if candidate.label == "音乐偏好":
            music = self._extract_music_name(candidate.summary) or "这些音乐"
            if candidate.scope == "mode":
                return f"记住啦，在这个模式下我会记得你喜欢{music}。"
            return f"记住啦，以后聊音乐我会记得你喜欢{music}。"

        if candidate.label == "游戏偏好":
            game = self._extract_game_name(candidate.summary) or "这个游戏"
            if candidate.scope == "mode":
                return f"记住啦，在这个模式下我会记得你喜欢玩{game}。"
            return f"记住啦，以后聊游戏我会记得你喜欢玩{game}。"

        if candidate.label == "编码协作偏好":
            if candidate.scope == "mode":
                return "记住啦，这个模式下聊代码时我会先给你方案，再进入编码。"
            return "记住啦，以后聊代码时我会先给你方案，再进入编码。"

        if candidate.label in {"交流偏好", "学习偏好", "工作偏好"}:
            detail = candidate.summary.split("：", 1)[1] if "：" in candidate.summary else candidate.summary
            if candidate.scope == "mode":
                return f"记住啦，这个模式下我会按这个偏好来：{detail}"
            return f"记住啦，我会按这个偏好来：{detail}"

        if candidate.kind == "habit":
            if candidate.scope == "mode":
                return "记住啦，这个模式下我会参考你的这个习惯。"
            return "记住啦，我会把这个作为你的习惯来理解。"

        if candidate.kind == "goal":
            if candidate.scope == "mode":
                return "记住啦，这个模式下我会记得你的这个目标。"
            return "记住啦，我会把这个作为你的长期目标。"

        if candidate.kind == "profile":
            return "记住啦，我会记得这条关于你的信息。"

        if candidate.scope == "mode":
            return "记住啦，这个模式下我会按你的偏好来。"

        return "记住啦，我会把这个作为你的长期偏好。"

    def _duplicate_acknowledgement(self, candidate: MemoryCandidate) -> str:
        if candidate.label == "美食偏好":
            food = self._extract_food_name(candidate.summary)
            if candidate.scope == "mode":
                return f"这个模式下我已经记着啦，你喜欢吃{food}。"
            return f"我已经记着啦，你喜欢{food}。"

        if candidate.label == "音乐偏好":
            music = self._extract_music_name(candidate.summary) or "这些音乐"
            if candidate.scope == "mode":
                return f"这个模式下我已经记着啦，你喜欢{music}。"
            return f"我已经记着啦，你喜欢{music}。"

        if candidate.label == "游戏偏好":
            game = self._extract_game_name(candidate.summary) or "这个游戏"
            if candidate.scope == "mode":
                return f"这个模式下我已经记着啦，你喜欢玩{game}。"
            return f"我已经记着啦，你喜欢玩{game}。"

        if candidate.label == "编码协作偏好":
            if candidate.scope == "mode":
                return "这个模式下我已经记着啦，写代码时先给方案再编码。"
            return "我已经记着啦，写代码时先给方案再编码。"

        if candidate.label in {"交流偏好", "学习偏好", "工作偏好"}:
            if candidate.scope == "mode":
                return "这个模式下我已经记着这条偏好啦。"
            return "我已经记着这条偏好啦。"

        if candidate.kind == "habit":
            if candidate.scope == "mode":
                return "这个模式下我已经记着你的这个习惯啦。"
            return "我已经记着你的这个习惯啦。"

        if candidate.kind == "goal":
            if candidate.scope == "mode":
                return "这个模式下我已经记着你的这个目标啦。"
            return "我已经记着你的这个目标啦。"

        if candidate.kind == "profile":
            return "我已经记着这条关于你的信息啦。"

        return "我已经记着这条偏好啦。"

    def _log_memory_result(
        self,
        result: MemoryCommandResult,
        candidate: MemoryCandidate,
        *,
        target_name: str | None = None,
        verb: str | None = None,
    ) -> None:
        target = target_name or ("mode" if candidate.scope == "mode" else "core")
        operation = verb or result.action
        print(
            (
                f"[Memory] {operation} action={result.action} scope={candidate.scope} "
                f"target={target} section={candidate.section} summary={candidate.summary} "
                f"path={result.target}"
            ),
            flush=True,
        )

    def _is_remember_message(self, message: str) -> bool:
        return any(keyword in message for keyword in ("记住", "帮我记", "请记", "以后要记得"))

    def _is_forget_message(self, message: str) -> bool:
        return any(keyword in message for keyword in ("忘记", "忘掉", "不要记住", "别记住"))

    def _detect_scope(self, message: str) -> str:
        if self._mentions_mode_scope(message):
            return "mode"

        return "core"

    def _mentions_specific_scope(self, message: str) -> bool:
        return self._mentions_mode_scope(message) or any(
            keyword in message for keyword in ("核心记忆", "长期记忆", "所有模式")
        )

    def _mentions_mode_scope(self, message: str) -> bool:
        return any(keyword in message for keyword in ("当前模式", "这个模式", "本模式", "模式下"))

    def _clean_remember_content(self, message: str) -> str:
        content = message.strip()
        patterns = [
            r"^(请|麻烦|帮我|你要|你需要)?记住[:：,，\s]*",
            r"^以后要记得[:：,，\s]*",
            r"^(请|麻烦|帮我)?把[:：,，\s]*",
            r"记住[:：,，\s]*$",
        ]
        for pattern in patterns:
            content = re.sub(pattern, "", content).strip()

        content = content.removesuffix("这件事").strip()
        return content or message.strip()

    def _clean_memory_content(self, message: str, *, explicit: bool) -> str:
        content = self._clean_remember_content(message) if explicit else message.strip()

        while True:
            updated = re.sub(
                r"^(在)?(当前模式|这个模式|本模式|所有模式|核心记忆|长期记忆)下?[:：,，\s]*",
                "",
                content,
            ).strip()
            updated = re.sub(
                r"^(关于)?(当前模式|这个模式|本模式|核心记忆|长期记忆)[:：,，\s]*",
                "",
                updated,
            ).strip()
            if updated == content:
                break
            content = updated

        return content.strip("，,。 ")

    def _clean_forget_content(self, message: str) -> str:
        content = message.strip()
        patterns = [
            r"^(请|麻烦|帮我|你要)?(忘记|忘掉|不要记住|别记住)[:：,，\s]*",
            r"^(请|麻烦|帮我)?把[:：,，\s]*",
        ]
        for pattern in patterns:
            content = re.sub(pattern, "", content).strip()

        return content.removesuffix("这件事").strip()

    def _relative_target(self, path: Path) -> str:
        return str(path)

    def _should_auto_capture(self, message: str) -> bool:
        text = message.strip()
        if len(text) < 5 or len(text) > 220:
            return False

        if any(mark in text for mark in ("？", "?", "吗", "么")):
            return False

        if any(keyword in text for keyword in ("记住", "忘记", "删除", "清空", "todo", "待办", "skill", "技能")):
            return False

        signal_patterns = (
            r"^我平常",
            r"^我一般",
            r"^我通常",
            r"^我习惯",
            r"^我喜欢",
            r"^我不喜欢",
            r"^我希望",
            r"^我的偏好",
            r"^我的习惯",
            r"^我.*喜欢",
            r"^我.*习惯",
            r"^我.*希望",
        )
        return any(re.search(pattern, text) for pattern in signal_patterns)
