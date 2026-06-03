"""
RAG Evaluation — semantic similarity + retrieval quality metrics.
Uses sentence-transformers (already installed, zero extra cost).

Metrics:
  answer_similarity   — cosine sim between generated answer and reference
  retrieval_coverage  — % of queries that returned >=1 source
  citation_rate       — % of answers that cite a paper ID
  answer_completeness — % of answers that are non-empty and substantial (>50 words)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx
import numpy as np
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.table import Table
from rich.progress import track
import os

console = Console()

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
SAMPLE_SIZE = 10
API_BASE = "http://localhost:8000"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_token() -> str:
    resp = httpx.post(
        f"{API_BASE}/token",
        data={
            "username": os.getenv("OAUTH_CLIENT_ID", "arxivmind-client"),
            "password": os.getenv("OAUTH_CLIENT_SECRET", "change-me"),
        },
    )
    return resp.json()["access_token"]


def query_rag(question: str, token: str) -> tuple[str, list[str], int, int]:
    resp = httpx.post(
        f"{API_BASE}/query",
        json={"query": question},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    data = resp.json()
    return (
        data.get("answer", ""),
        data.get("sources", []),
        data.get("iterations", 0),
        data.get("latency_ms", 0),
    )


def has_citation(text: str) -> bool:
    return bool(re.search(r"\b\d{4}\.\d{4,5}", text))


def main():
    console.print("[bold blue]ArxivMind — RAG Evaluation[/bold blue]\n")

    golden = json.loads(GOLDEN_SET_PATH.read_text())[:SAMPLE_SIZE]
    console.print(f"Evaluating on {len(golden)} questions...\n")

    console.print("[yellow]Loading embedding model...[/yellow]")
    model = SentenceTransformer(EMBED_MODEL)

    token = get_token()

    results = []
    for item in track(golden, description="Running queries..."):
        answer, sources, iterations, latency_ms = query_rag(item["question"], token)
        results.append({
            "question": item["question"],
            "reference": item["reference"],
            "answer": answer,
            "sources": sources,
            "iterations": iterations,
            "latency_ms": latency_ms,
        })

    console.print("\n[yellow]Computing metrics...[/yellow]")

    answers = [r["answer"] for r in results]
    references = [r["reference"] for r in results]

    answer_vecs = model.encode(answers, normalize_embeddings=True)
    reference_vecs = model.encode(references, normalize_embeddings=True)
    similarities = (answer_vecs * reference_vecs).sum(axis=1)

    retrieval_coverage = sum(1 for r in results if len(r["sources"]) > 0) / len(results)
    citation_rate = sum(1 for r in results if has_citation(r["answer"])) / len(results)
    answer_completeness = sum(
        1 for r in results if len(r["answer"].split()) >= 50
    ) / len(results)
    avg_similarity = float(np.mean(similarities))
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)
    avg_sources = sum(len(r["sources"]) for r in results) / len(results)

    # Save scores first so data is never lost even if display crashes
    scores = {
        "sample_size": len(golden),
        "model": "qwen2.5:7b (local)",
        "corpus_size": 400,
        "metrics": {
            "answer_similarity": round(avg_similarity, 3),
            "retrieval_coverage": round(retrieval_coverage, 3),
            "citation_rate": round(citation_rate, 3),
            "answer_completeness": round(answer_completeness, 3),
        },
        "avg_latency_seconds": round(avg_latency / 1000, 1),
        "avg_sources_per_query": round(avg_sources, 1),
    }
    out_path = Path(__file__).parent / "eval_scores.json"
    out_path.write_text(json.dumps(scores, indent=2))

    # ── Results table ──────────────────────────────────────────────────────
    table = Table(title="RAG Evaluation Results", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan", width=28)
    table.add_column("Score", style="bold green", width=10)
    table.add_column("Description")

    def score_color(v: float) -> str:
        if v >= 0.7: return f"[green]{v:.3f}[/green]"
        if v >= 0.5: return f"[yellow]{v:.3f}[/yellow]"
        return f"[red]{v:.3f}[/red]"

    table.add_row("Answer Similarity", score_color(avg_similarity),
                  "Cosine sim vs reference answer (sentence-transformers)")
    table.add_row("Retrieval Coverage", score_color(retrieval_coverage),
                  "% queries that returned >=1 source paper")
    table.add_row("Citation Rate", score_color(citation_rate),
                  "% answers that cite a paper ID")
    table.add_row("Answer Completeness", score_color(answer_completeness),
                  "% answers >=50 words (non-trivial response)")

    console.print(table)

    # ── Per-question breakdown ─────────────────────────────────────────────
    console.print("\n[bold]Per-question breakdown:[/bold]")
    detail = Table(show_header=True, header_style="dim")
    detail.add_column("#", width=3)
    detail.add_column("Question", width=45)
    detail.add_column("Sim", width=6)
    detail.add_column("Srcs", width=5)
    detail.add_column("Cited", width=5)
    detail.add_column("Words", width=6)

    for i, (r, sim) in enumerate(zip(results, similarities)):
        words = len(r["answer"].split())
        detail.add_row(
            str(i + 1),
            r["question"][:43] + ".." if len(r["question"]) > 45 else r["question"],
            f"{sim:.2f}",
            str(len(r["sources"])),
            "✓" if has_citation(r["answer"]) else "✗",
            "Y" if has_citation(r["answer"]) else "N",
            str(words),
        )
    console.print(detail)

    # ── Summary stats ──────────────────────────────────────────────────────
    console.print(f"\nAvg latency: {avg_latency/1000:.1f}s | "
                  f"Avg sources per query: {avg_sources:.1f} | "
                  f"Sample: {len(golden)} questions")

    console.print(f"\nScores saved to {out_path}")


if __name__ == "__main__":
    main()
