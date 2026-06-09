"""POST /query — main RAG query endpoint."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent import loop
from api.auth import require_scope
from api.deps import get_llm, get_qdrant
from api.middleware import limiter

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
@limiter.limit("20/minute")
async def query(
    request: Request,
    req: QueryRequest,
    _client: dict = Depends(require_scope("read:query")),
    qdrant=Depends(get_qdrant),
    llm=Depends(get_llm),
):
    filters = {k: v for k, v in {"category": req.category, "date_from": req.date_from}.items() if v is not None}
    result = await asyncio.to_thread(loop.run, req.query, qdrant=qdrant, llm=llm, filters=filters or None)
    if result["error"]:
        raise HTTPException(status_code=500, detail="Query failed. Please try again.")
    return QueryResponse(**result)
