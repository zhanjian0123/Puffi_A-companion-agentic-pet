from fastapi import APIRouter

from rag.knowledge_base import knowledge_base
from schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    results = await knowledge_base.search(request.query, request.limit)
    return KnowledgeSearchResponse(results=results)
