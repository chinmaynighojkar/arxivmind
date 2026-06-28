"""Monthly refresh: delete papers older than RETENTION_MONTHS, ingest recent ones."""

import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from ingestion.chunk import chunk_sections
from ingestion.embed import ensure_collection, upsert_chunks
from ingestion.fetch import fetch_papers

logger = structlog.get_logger()

_COLLECTION = os.getenv("QDRANT_COLLECTION", "arxivmind")
_RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", "4"))


def _scroll_all(qdrant, fields: list[str]) -> list[dict]:
    records = []
    offset = None
    while True:
        results, next_offset = qdrant.scroll(
            collection_name=_COLLECTION,
            limit=256,
            offset=offset,
            with_payload=fields,
            with_vectors=False,
        )
        records.extend(r.payload for r in results)
        if next_offset is None:
            break
        offset = next_offset
    return records


def delete_old_papers(qdrant) -> int:
    cutoff = (
        datetime.date.today() - datetime.timedelta(days=_RETENTION_MONTHS * 30)
    ).isoformat()
    payloads = _scroll_all(qdrant, ["paper_id", "date"])
    old_ids = {
        p["paper_id"]
        for p in payloads
        if p.get("date", "")[:10] < cutoff and p.get("paper_id")
    }
    if not old_ids:
        logger.info("no_old_papers", cutoff=cutoff)
        return 0
    qdrant.delete(
        collection_name=_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="paper_id", match=MatchAny(any=list(old_ids)))]
        ),
    )
    logger.info("deleted_old_papers", count=len(old_ids), cutoff=cutoff)
    return len(old_ids)


def ingest_recent_papers(qdrant) -> int:
    existing_ids = {
        p["paper_id"] for p in _scroll_all(qdrant, ["paper_id"]) if p.get("paper_id")
    }
    recent = fetch_papers(max_results=200)
    new_papers = [
        p
        for p in recent
        if p["paper_id"] not in existing_ids
        and p["paper_id"].split("v")[0] not in existing_ids
    ]
    logger.info("papers_to_ingest", new=len(new_papers), skipped=len(recent) - len(new_papers))
    ensure_collection(qdrant)
    ingested = 0
    for paper in new_papers:
        sections = [{"section": "abstract", "text": paper["abstract"], "page_start": 0}]
        chunks = chunk_sections(paper, sections)
        upsert_chunks(qdrant, chunks)
        ingested += 1
        logger.info("ingested", paper_id=paper["paper_id"], title=paper["title"][:60])
    return ingested


def main() -> None:
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    logger.info("refresh_start", retention_months=_RETENTION_MONTHS)
    deleted = delete_old_papers(qdrant)
    ingested = ingest_recent_papers(qdrant)
    logger.info("refresh_complete", deleted=deleted, ingested=ingested)


if __name__ == "__main__":
    main()
