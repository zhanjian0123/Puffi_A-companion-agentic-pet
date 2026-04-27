from __future__ import annotations

from agents import function_tool

from config import settings
from knowledge import get_knowledge_service


@function_tool
async def list_knowledge_documents(limit: int = 50) -> str:
    """列出本地知识库中已经索引的文档清单。"""
    if not settings.knowledge_enabled:
        return "知识库未启用。"

    safe_limit = min(max(int(limit), 1), 200)
    documents = await get_knowledge_service().list_documents()
    if not documents:
        return "知识库当前没有已索引文档。"

    shown = documents[:safe_limit]
    header = f"知识库当前共有 {len(documents)} 个文档"
    if len(documents) > len(shown):
        header += f"，展示前 {len(shown)} 个"
    header += "："

    lines = [header]
    for index, document in enumerate(shown, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. {document.path}",
                    f"   标题：{document.title}",
                    f"   chunks：{document.chunk_count}",
                    f"   大小：{_format_size(document.size)}",
                    f"   索引时间：{document.indexed_at or '未知'}",
                ]
            )
        )

    return "\n\n".join(lines)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
