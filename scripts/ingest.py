"""One-shot ingestion: Arxiv → parse → chunk → embed → Qdrant."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import os

from qdrant_client import QdrantClient
from rich.console import Console
from rich.progress import track

from ingestion.chunk import chunk_sections
from ingestion.embed import ensure_collection, upsert_chunks
from ingestion.fetch import download_pdf, fetch_papers
from ingestion.parse import parse_pdf

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Ingest Arxiv papers into Qdrant")
    parser.add_argument("--limit", type=int, default=500, help="Max papers to fetch")
    parser.add_argument(
        "--skip-download", action="store_true", help="Skip PDF download, use abstracts only"
    )
    args = parser.parse_args()

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    ensure_collection(qdrant)
    console.print("[green]Qdrant collection ready[/green]")

    console.print(f"[blue]Fetching up to {args.limit} papers from Arxiv...[/blue]")
    papers = fetch_papers(max_results=args.limit)
    console.print(f"[green]Fetched {len(papers)} papers[/green]")

    total_chunks = 0
    for paper in track(papers, description="Processing papers..."):
        sections = []

        if not args.skip_download:
            pdf_path = download_pdf(paper)
            if pdf_path:
                sections = parse_pdf(pdf_path)

        if not sections:
            sections = [{"section": "abstract", "text": paper["abstract"], "page_start": 0}]

        chunks = chunk_sections(paper, sections)
        upserted = upsert_chunks(qdrant, chunks)
        total_chunks += upserted

    console.print(f"[green]Done. {total_chunks} chunks upserted to Qdrant.[/green]")


if __name__ == "__main__":
    main()
