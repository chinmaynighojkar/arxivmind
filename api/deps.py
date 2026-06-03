"""Shared FastAPI dependencies — Qdrant client and LLM client."""

import os

from qdrant_client import QdrantClient

from agent.llm import LLMClient, get_llm_client

_qdrant: QdrantClient | None = None
_llm: LLMClient | None = None


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        api_key = os.getenv("QDRANT_API_KEY") or None
        _qdrant = QdrantClient(url=url, api_key=api_key)
    return _qdrant


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = get_llm_client()
    return _llm
