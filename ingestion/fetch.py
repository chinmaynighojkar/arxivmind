"""Fetch papers from Arxiv API and download PDFs to local cache."""

import time
from pathlib import Path

import arxiv

CATEGORIES = ["cs.LG", "cs.AI", "stat.ML", "cs.CL"]
PDF_DIR = Path(__file__).parent.parent / "data" / "pdfs"

_client = arxiv.Client(page_size=100, delay_seconds=5, num_retries=5)


def fetch_papers(
    categories: list[str] = CATEGORIES,
    max_results: int = 500,
    months_back: int = 12,
) -> list[dict]:
    """Fetch paper metadata from Arxiv. Returns list of paper dicts."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    papers = []
    per_category = min(max_results // len(categories), 100)  # stay within one page

    for category in categories:
        print(f"  Fetching {per_category} papers from {category}...")
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=per_category,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        retries = 0
        while retries < 5:
            try:
                batch = []
                for result in _client.results(search):
                    batch.append(
                        {
                            "paper_id": result.entry_id.split("/")[-1],
                            "title": result.title,
                            "authors": [a.name for a in result.authors[:5]],
                            "abstract": result.summary,
                            "date": result.published.isoformat(),
                            "category": category,
                            "pdf_url": result.pdf_url,
                        }
                    )
                papers.extend(batch)
                print(f"  Got {len(batch)} papers from {category}")
                break
            except Exception:
                retries += 1
                wait = 15 * retries
                print(f"  Rate limited on {category}, waiting {wait}s (attempt {retries}/5)...")
                time.sleep(wait)

        time.sleep(10)  # respectful delay between categories

    return papers


def download_pdf(paper: dict) -> Path | None:
    """Download PDF for a paper. Returns local path or None on failure."""
    pdf_path = PDF_DIR / f"{paper['paper_id']}.pdf"
    if pdf_path.exists():
        return pdf_path

    try:
        paper_id = paper["paper_id"]
        search = arxiv.Search(id_list=[paper_id])
        result = next(_client.results(search))
        result.download_pdf(dirpath=str(PDF_DIR), filename=f"{paper_id}.pdf")
        return pdf_path
    except Exception as e:
        print(f"[fetch] Failed to download {paper['paper_id']}: {e}")
        return None
