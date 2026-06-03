"""Unit tests for chunker and re-ranker."""

from ingestion.chunk import _chunk_text, chunk_sections
from retrieval.rerank import rerank


def test_chunk_text_basic():
    text = " ".join([f"word{i}" for i in range(500)])
    chunks = _chunk_text(text, max_tokens=100, overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) <= 100 + 5  # small tolerance


def test_chunk_text_short():
    # Strings under 30 chars are filtered as noise — expect empty result
    chunks = _chunk_text("short text here", max_tokens=100, overlap=10)
    assert len(chunks) == 0

    # A longer short text should produce exactly one chunk
    chunks = _chunk_text("this is a slightly longer piece of text for testing", max_tokens=100, overlap=10)
    assert len(chunks) == 1


def test_chunk_sections_metadata():
    paper = {
        "paper_id": "2312.00001",
        "title": "Test Paper",
        "authors": ["Alice"],
        "date": "2023-12-01",
        "category": "cs.LG",
        "abstract": "A test abstract.",
    }
    sections = [{"section": "introduction", "text": "This paper presents " * 50, "page_start": 0}]
    chunks = chunk_sections(paper, sections)
    assert len(chunks) >= 1
    assert all(c["paper_id"] == "2312.00001" for c in chunks)
    assert all(c["section"] == "introduction" for c in chunks)


def test_rerank_reduces_candidates():
    candidates = [
        {"text": f"This paper discusses topic {i}", "paper_id": f"2312.0000{i}"}
        for i in range(10)
    ]
    results = rerank("transformer attention mechanism", candidates, top_n=3)
    assert len(results) == 3


def test_rerank_empty():
    assert rerank("anything", [], top_n=5) == []


def test_rerank_fewer_than_top_n():
    candidates = [{"text": "short text", "paper_id": "2312.00001"}]
    results = rerank("query", candidates, top_n=5)
    assert len(results) == 1
