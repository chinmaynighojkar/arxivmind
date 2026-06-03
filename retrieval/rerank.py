"""Cross-encoder re-ranking: top-20 candidates → top-5."""

from sentence_transformers import CrossEncoder

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_N = 5

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def rerank(query: str, candidates: list[dict], top_n: int = TOP_N) -> list[dict]:
    """Re-rank candidates using cross-encoder. Returns top_n results."""
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    reranker = _get_reranker()
    pairs = [[query, c["text"]] for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(candidates, scores, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )
    return [doc for doc, _ in ranked[:top_n]]
