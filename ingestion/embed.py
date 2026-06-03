"""Embed chunks and upsert to Qdrant with dense + sparse vectors."""

import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

COLLECTION = os.getenv("QDRANT_COLLECTION", "arxivmind")
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DENSE_DIM = 384
BATCH_SIZE = 64

_dense_model: SentenceTransformer | None = None


def _get_dense_model() -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(DENSE_MODEL)
    return _dense_model


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION in existing:
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        },
    )


def upsert_chunks(client: QdrantClient, chunks: list[dict]) -> int:
    """Embed and upsert chunks. Returns count upserted."""
    if not chunks:
        return 0

    model = _get_dense_model()
    points = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        dense_vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        for chunk, dense_vec in zip(batch, dense_vecs):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={"dense": dense_vec.tolist()},
                    payload=chunk,
                )
            )

    client.upsert(collection_name=COLLECTION, points=points)
    return len(points)
