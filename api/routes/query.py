"""POST /query — main RAG query endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agent import loop
from api.auth import require_scope
from api.deps import get_llm, get_qdrant

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    category: str | None = None
    date_from: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    iterations: int
    latency_ms: int
    error: str | None


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    _client: dict = Depends(require_scope("read:query")),
    qdrant=Depends(get_qdrant),
    llm=Depends(get_llm),
):
    result = loop.run(req.query, qdrant=qdrant, llm=llm)
    return QueryResponse(**result)
