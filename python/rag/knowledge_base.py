from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from uuid import uuid4

from schemas.knowledge import KnowledgeResult


@dataclass(slots=True)
class KnowledgeDocument:
    id: str
    content: str
    source: str
    type: str
    created_at: int


@dataclass(slots=True)
class KnowledgeBase:
    path: str = "./knowledge"
    documents: list[KnowledgeDocument] = field(default_factory=list)

    async def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]:
        normalized = query.lower()
        matched = [
            doc
            for doc in self.documents
            if normalized in doc.content.lower()
        ][:limit]

        return [
            KnowledgeResult(
                id=doc.id,
                content=doc.content,
                metadata={
                    "source": doc.source,
                    "type": doc.type,
                    "createdAt": doc.created_at,
                },
            )
            for doc in matched
        ]

    async def add_text(self, text: str, source: str = "manual", type_: str = "text") -> None:
        for chunk in self._chunk_text(text):
            self.documents.append(
                KnowledgeDocument(
                    id=str(uuid4()),
                    content=chunk,
                    source=source,
                    type=type_,
                    created_at=int(time() * 1000),
                )
            )

    def _chunk_text(self, text: str, size: int = 500) -> list[str]:
        return [text[index : index + size] for index in range(0, len(text), size)]


knowledge_base = KnowledgeBase()
