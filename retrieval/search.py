"""Hybrid retrieval: dense vector search via Qdrant query_points API."""

import os

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range
from sentence_transformers import SentenceTransformer

COLLECTION = os.getenv("QDRANT_COLLECTION", "arxivmind")
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 20

_dense_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(DENSE_MODEL)
    return _dense_model


def hybrid_search(
    client: QdrantClient,
    query: str,
    top_k: int = TOP_K,
    filters: dict | None = None,
) -> list[dict]:
    """Dense vector search over Qdrant. Returns top_k results with scores."""
    model = _get_model()
    query_vec = model.encode(query, normalize_embeddings=True).tolist()

    qdrant_filter = _build_filter(filters) if filters else None

    results = client.query_points(
        collection_name=COLLECTION,
        query=query_vec,
        using="dense",
        limit=top_k,
        query_filter=qdrant_filter,
        with_payload=True,
    )

    return [{**r.payload, "_score": r.score, "_id": str(r.id)} for r in results.points]


def _build_filter(filters: dict) -> Filter | None:
    conditions = []
    if "category" in filters:
        conditions.append(
            FieldCondition(key="category", match=MatchValue(value=filters["category"]))
        )
    if "date_from" in filters:
        conditions.append(FieldCondition(key="date", range=Range(gte=filters["date_from"])))
    if not conditions:
        return None
    return Filter(must=conditions)
