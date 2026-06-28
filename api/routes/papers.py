"""Routes for paper search, single-paper ingestion, and topic summarisation."""

import asyncio
import os
import re

import arxiv
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agent.tools import execute_tool
from api.auth import require_scope
from api.deps import get_qdrant
from api.middleware import limiter
from ingestion.chunk import chunk_sections
from ingestion.embed import ensure_collection, upsert_chunks
from ingestion.fetch import download_pdf, fetch_papers
from ingestion.parse import parse_pdf
from retrieval.rerank import rerank
from retrieval.search import hybrid_search

router = APIRouter()

_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_arxiv_client = arxiv.Client(page_size=1, delay_seconds=3, num_retries=3)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    category: str | None = None
    date_from: str | None = None


class PaperResult(BaseModel):
    paper_id: str
    title: str
    date: str
    section: str
    excerpt: str


class SearchResponse(BaseModel):
    results: list[PaperResult]


class IngestRequest(BaseModel):
    paper_id: str = Field(min_length=1, max_length=30)


class IngestResponse(BaseModel):
    paper_id: str
    title: str
    chunks_upserted: int


class SummariseRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    max_papers: int = Field(default=5, ge=1, le=10)


class SummariseResponse(BaseModel):
    topic: str
    summary: str


@router.post("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    req: SearchRequest,
    _client: dict = Depends(require_scope("read:query")),
    qdrant=Depends(get_qdrant),
):
    filters = {}
    if req.category:
        filters["category"] = req.category
    if req.date_from:
        filters["date_from"] = req.date_from

    candidates = await asyncio.to_thread(
        hybrid_search, qdrant, req.query, top_k=20, filters=filters or None
    )
    results = await asyncio.to_thread(rerank, req.query, candidates, top_n=5)

    return SearchResponse(
        results=[
            PaperResult(
                paper_id=r["paper_id"],
                title=r["title"],
                date=r["date"][:10],
                section=r.get("section", "N/A"),
                excerpt=r["text"][:400],
            )
            for r in results
        ]
    )


def _ingest_paper_sync(paper_id: str, qdrant) -> dict:
    """Fetch, parse, chunk, embed, and upsert a single paper by arxiv ID."""
    if not _ARXIV_ID_RE.match(paper_id):
        raise ValueError(f"Invalid arxiv ID format: '{paper_id}'. Expected e.g. 2312.12456")

    search = arxiv.Search(id_list=[paper_id])
    results = list(_arxiv_client.results(search))
    if not results:
        raise ValueError(f"Paper '{paper_id}' not found on arxiv")

    r = results[0]
    paper = {
        "paper_id": paper_id,
        "title": r.title,
        "authors": [a.name for a in r.authors[:5]],
        "abstract": r.summary,
        "date": r.published.isoformat(),
        "category": str(r.primary_category),
        "pdf_url": r.pdf_url,
    }

    ensure_collection(qdrant)

    _MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
    pdf_path = download_pdf(paper)
    if pdf_path and pdf_path.stat().st_size > _MAX_PDF_BYTES:
        pdf_path.unlink(missing_ok=True)
        pdf_path = None
    sections = parse_pdf(pdf_path) if pdf_path else []
    if not sections:
        sections = [{"section": "abstract", "text": paper["abstract"], "page_start": 0}]

    chunks = chunk_sections(paper, sections)
    n = upsert_chunks(qdrant, chunks)
    return {"title": paper["title"], "chunks_upserted": n}


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit("5/minute")
async def ingest(
    request: Request,
    req: IngestRequest,
    _client: dict = Depends(require_scope("write:ingest")),
    qdrant=Depends(get_qdrant),
):
    paper_id = req.paper_id.strip()
    try:
        result = await asyncio.to_thread(_ingest_paper_sync, paper_id, qdrant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ingestion failed. Check server logs.") from e

    return IngestResponse(
        paper_id=paper_id,
        title=result["title"],
        chunks_upserted=result["chunks_upserted"],
    )


class PaperMeta(BaseModel):
    paper_id: str
    title: str
    authors: list[str]
    date: str
    category: str
    abstract: str


class PapersResponse(BaseModel):
    papers: list[PaperMeta]
    total: int


_MAX_PAPERS_LISTING = int(os.getenv("MAX_PAPERS_LISTING", "1000"))


def _list_papers_sync(qdrant) -> list[dict]:
    """Scroll chunks and return one record per unique paper_id, capped at MAX_PAPERS_LISTING."""
    seen: dict[str, dict] = {}
    offset = None

    while len(seen) < _MAX_PAPERS_LISTING:
        results, next_offset = qdrant.scroll(
            collection_name=os.getenv("QDRANT_COLLECTION", "arxivmind"),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in results:
            p = point.payload
            pid = p.get("paper_id", "")
            if pid and pid not in seen:
                seen[pid] = {
                    "paper_id": pid,
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "date": p.get("date", "")[:10],
                    "category": p.get("category", ""),
                    "abstract": p.get("abstract", "")[:400],
                }
            if len(seen) >= _MAX_PAPERS_LISTING:
                break
        if next_offset is None:
            break
        offset = next_offset

    return sorted(seen.values(), key=lambda x: x["date"], reverse=True)


@router.get("/papers", response_model=PapersResponse)
@limiter.limit("30/minute")
async def list_papers(
    request: Request,
    _client: dict = Depends(require_scope("read:query")),
    qdrant=Depends(get_qdrant),
):
    papers = await asyncio.to_thread(_list_papers_sync, qdrant)
    return PapersResponse(papers=papers, total=len(papers))


class RefreshResponse(BaseModel):
    ingested: int
    skipped: int


def _get_existing_paper_ids(qdrant) -> set[str]:
    seen: set[str] = set()
    offset = None
    collection = os.getenv("QDRANT_COLLECTION", "arxivmind")
    while True:
        results, next_offset = qdrant.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=["paper_id"],
            with_vectors=False,
        )
        for point in results:
            pid = point.payload.get("paper_id", "")
            if pid:
                seen.add(pid)
        if next_offset is None:
            break
        offset = next_offset
    return seen


def _refresh_papers_sync(qdrant) -> dict:
    existing_ids = _get_existing_paper_ids(qdrant)
    recent = fetch_papers(max_results=200)
    new_papers = [
        p
        for p in recent
        if p["paper_id"] not in existing_ids and p["paper_id"].split("v")[0] not in existing_ids
    ]
    skipped = len(recent) - len(new_papers)
    ensure_collection(qdrant)
    ingested = 0
    for paper in new_papers:
        sections = [{"section": "abstract", "text": paper["abstract"], "page_start": 0}]
        chunks = chunk_sections(paper, sections)
        upsert_chunks(qdrant, chunks)
        ingested += 1
    return {"ingested": ingested, "skipped": skipped}


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("2/hour")
async def refresh_papers(
    request: Request,
    _client: dict = Depends(require_scope("write:ingest")),
    qdrant=Depends(get_qdrant),
):
    try:
        result = await asyncio.to_thread(_refresh_papers_sync, qdrant)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Refresh failed. Check server logs.") from e
    return RefreshResponse(**result)


@router.post("/summarise", response_model=SummariseResponse)
@limiter.limit("10/minute")
async def summarise(
    request: Request,
    req: SummariseRequest,
    _client: dict = Depends(require_scope("read:query")),
    qdrant=Depends(get_qdrant),
):
    args = {"topic": req.topic, "max_papers": req.max_papers}
    summary = await asyncio.to_thread(execute_tool, "summarise_topic", args, qdrant)
    return SummariseResponse(topic=req.topic, summary=summary)
