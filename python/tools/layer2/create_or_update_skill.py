from __future__ import annotations

from agents import function_tool

from config import settings
from memory.store import MarkdownMemoryStore


@function_tool
def create_or_update_skill(
    name: str,
    description: str,
    instructions: str,
    triggers: str = "",
    tags: list[str] | None = None,
) -> str:
    """将可复用流程保存为跨生态兼容的 Skill 文件（skills/<name>/SKILL.md）。

    只有当用户明确说“保存为 skill / 沉淀成技能 / 下次类似任务照这个来”等意图时才调用。
    name: Skill 标识（建议英文短名，如 report-writing）。
    description: 何时使用这个 skill。
    instructions: 可复用步骤、偏好、注意事项。
    triggers: 关键词，供后续匹配加载。
    tags: 可选标签列表。
    """
    store = MarkdownMemoryStore(
        settings.memory_dir,
        core_file_char_limit=settings.memory_core_file_max_chars,
        mode_file_char_limit=settings.memory_mode_file_max_chars,
        skill_file_char_limit=settings.skill_file_max_chars,
        skill_index_file_char_limit=settings.skill_index_file_max_chars,
    )
    path = store.create_or_update_skill_sync(
        name=name,
        description=description,
        instructions=instructions,
        triggers=triggers,
        tags=tags,
    )
    return f"Skill saved: {path}"
