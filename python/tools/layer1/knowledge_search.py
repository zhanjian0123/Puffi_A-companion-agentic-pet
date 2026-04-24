from __future__ import annotations

from agents import function_tool

from config import settings
from knowledge import get_knowledge_service


@function_tool
async def knowledge_search(query: str) -> str:
    """检索本地知识库，适合回答事实、定义、项目文档、资料、笔记中的内容。"""
    if not settings.knowledge_enabled:
        return "知识库未启用。"

    service = get_knowledge_service()
    results = await service.query(query, top_k=settings.knowledge_top_k)
    if not results:
        return "NO_KNOWLEDGE_RESULTS: 本地知识库没有可用于回答该问题的内容。请直接用通用模型知识自然回答，不要向用户提及这条内部检索结果。"

    lines = ["知识库检索结果："]
    for index, result in enumerate(results, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. 来源：{result.document}#{result.chunk_index}",
                    f"相关度：{result.score:.4f}",
                    result.content,
                ]
                + ([f"相关关系：{'；'.join(result.relations)}"] if result.relations else [])
            )
        )

    return "\n\n".join(lines)
