"""Section-aware chunker. Never mixes content from different sections."""

MAX_CHUNK_TOKENS = 400
OVERLAP_TOKENS = 50


def chunk_sections(paper: dict, sections: list[dict]) -> list[dict]:
    """
    Split sections into chunks. Each chunk carries full paper metadata.
    Chunks never cross section boundaries.
    """
    chunks = []
    for section in sections:
        section_chunks = _chunk_text(section["text"], MAX_CHUNK_TOKENS, OVERLAP_TOKENS)
        for i, chunk_text in enumerate(section_chunks):
            chunks.append(
                {
                    "paper_id": paper["paper_id"],
                    "title": paper["title"],
                    "authors": paper["authors"],
                    "date": paper["date"],
                    "category": paper["category"],
                    "abstract": paper["abstract"][:500],
                    "section": section["section"],
                    "chunk_index": i,
                    "text": chunk_text,
                }
            )
    return chunks


def _chunk_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by approximate token count (words ≈ tokens)."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap

    return [c for c in chunks if len(c.strip()) > 30]
