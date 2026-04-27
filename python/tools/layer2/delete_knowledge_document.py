from __future__ import annotations

from agents import function_tool

from config import settings
from knowledge import get_knowledge_service


@function_tool
async def delete_knowledge_document(path: str) -> str:
    """按相对路径删除本地知识库文档，并同步清理索引。

    只有当用户明确要求删除知识库资料，并提供具体相对路径时才调用。
    path: 知识库文档目录内的相对路径，例如 agent-notes/example.md。
    """
    if not settings.knowledge_enabled:
        return "知识库未启用，无法删除。"

    result = await get_knowledge_service().delete_document(path)
    if not result.deleted:
        return result.message

    return (
        f"已删除知识库资料：{result.path}，并清理索引 "
        f"chunks={result.chunks_deleted} relations={result.relations_deleted} "
        f"summaries={result.summaries_deleted} "
        f"orphan_entities={result.orphan_entities_deleted}。"
    )
