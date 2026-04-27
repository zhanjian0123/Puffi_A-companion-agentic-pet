from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import re

from agents import function_tool

from config import settings
from knowledge import get_knowledge_service


MAX_TITLE_CHARS = 80
MAX_CONTENT_CHARS = 20000
MAX_TAGS = 8


@function_tool
async def write_knowledge_note(title: str, content: str, tags: list[str] | None = None) -> str:
    """将用户明确要求沉淀的资料写入本地知识库，并立即导入索引。

    只有当用户明确说“加入知识库 / 存到知识库 / 保存成资料 / 下次检索这个内容”等意图时才调用。
    title: 资料标题，必须简洁明确。
    content: 要写入知识库的正文，应该是整理后的 Markdown 内容，不要保存无意义寒暄。
    tags: 可选标签，帮助后续检索。
    """
    return await write_knowledge_note_impl(title=title, content=content, tags=tags)


async def write_knowledge_note_impl(title: str, content: str, tags: list[str] | None = None) -> str:
    if not settings.knowledge_enabled:
        return "知识库未启用，无法写入。"

    clean_title = _clean_title(title)
    clean_content = content.strip()
    clean_tags = _clean_tags(tags or [])

    if not clean_title:
        return "知识库写入失败：标题不能为空。"
    if not clean_content:
        return "知识库写入失败：内容不能为空。"
    if len(clean_content) > MAX_CONTENT_CHARS:
        return f"知识库写入失败：内容超过 {MAX_CONTENT_CHARS} 字符，请先压缩总结后再保存。"

    document_dir = Path(settings.knowledge_document_dir).expanduser().resolve()
    note_dir = (document_dir / "agent-notes").resolve()
    note_dir.mkdir(parents=True, exist_ok=True)

    try:
        note_dir.relative_to(document_dir)
    except ValueError:
        return "知识库写入失败：目标目录不在知识库文档目录内。"

    digest = hashlib.sha256(f"{clean_title}\n{clean_content}".encode("utf-8")).hexdigest()[:8]
    filename = f"{_slugify(clean_title)}-{digest}.md"
    note_path = note_dir / filename
    markdown = _format_note(title=clean_title, content=clean_content, tags=clean_tags)
    note_path.write_text(markdown, encoding="utf-8")

    print(
        f"[Knowledge] tool_write path={note_path} chars={len(markdown)} tags={clean_tags}",
        flush=True,
    )

    result = await get_knowledge_service().import_documents(str(note_path))
    relative_path = note_path.relative_to(document_dir)
    return (
        f"知识库资料已保存：{relative_path} "
        f"(imported={result.imported}, skipped={result.skipped}, failed={result.failed})"
    )


def _clean_title(title: str) -> str:
    return " ".join(title.split()).strip()[:MAX_TITLE_CHARS]


def _clean_tags(tags: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = " ".join(str(tag).split()).strip()
        if not value or value.lower() in seen:
            continue
        clean.append(value[:30])
        seen.add(value.lower())
        if len(clean) >= MAX_TAGS:
            break
    return clean


def _slugify(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", title).strip(".-")
    return slug[:60] or "knowledge-note"


def _format_note(*, title: str, content: str, tags: list[str]) -> str:
    created_at = datetime.now().isoformat(timespec="seconds")
    tag_line = ", ".join(tags)
    frontmatter = [
        "---",
        f"title: {title}",
        "source: ai-pet-tool",
        f"created_at: {created_at}",
    ]
    if tag_line:
        frontmatter.append(f"tags: {tag_line}")
    frontmatter.append("---")
    return "\n".join(frontmatter) + f"\n\n# {title}\n\n{content}\n"
