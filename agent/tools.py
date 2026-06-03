"""Tool definitions and executors for the agentic loop."""

import json
import os

from qdrant_client import QdrantClient

from retrieval.rerank import rerank
from retrieval.search import hybrid_search

COLLECTION = os.getenv("QDRANT_COLLECTION", "arxivmind")

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": (
                "Search Arxiv ML papers by semantic query. "
                "Use this to find relevant research on a topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "category": {
                        "type": "string",
                        "description": "Arxiv category filter e.g. cs.LG, cs.AI, stat.ML",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "ISO date string e.g. 2025-01-01 to filter recent papers",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper",
            "description": "Get the full abstract and metadata for a specific paper by its Arxiv ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string", "description": "Arxiv paper ID e.g. 2312.12456"},
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarise_topic",
            "description": (
                "Retrieve and summarise multiple papers on a topic. "
                "Use when asked to overview or compare a research area."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The research topic to summarise"},
                    "max_papers": {
                        "type": "integer",
                        "description": "Max number of papers to include (default 5)",
                    },
                },
                "required": ["topic"],
            },
        },
    },
]


def execute_tool(name: str, arguments: str | dict, qdrant: QdrantClient) -> str:
    """Execute a tool call and return the result as a string."""
    if isinstance(arguments, dict):
        args = arguments
    else:
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Error: invalid arguments JSON for tool {name}"

    if name == "search_papers":
        return _search_papers(args, qdrant)
    if name == "get_paper":
        return _get_paper(args, qdrant)
    if name == "summarise_topic":
        return _summarise_topic(args, qdrant)
    return f"Error: unknown tool {name}"


def _search_papers(args: dict, qdrant: QdrantClient) -> str:
    filters = {}
    if "category" in args:
        filters["category"] = args["category"]
    if "date_from" in args:
        filters["date_from"] = args["date_from"]

    candidates = hybrid_search(qdrant, args["query"], top_k=20, filters=filters or None)
    results = rerank(args["query"], candidates, top_n=5)

    if not results:
        return "No papers found for this query."

    lines = []
    for r in results:
        lines.append(
            f"- [{r['paper_id']}] {r['title']} ({r['date'][:10]})\n"
            f"  Section: {r.get('section', 'N/A')}\n"
            f"  Excerpt: {r['text'][:300]}..."
        )
    return "\n\n".join(lines)


def _get_paper(args: dict, qdrant: QdrantClient) -> str:
    results = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter={"must": [{"key": "paper_id", "match": {"value": args["paper_id"]}}]},
        limit=1,
        with_payload=True,
    )
    points = results[0]
    if not points:
        return f"Paper {args['paper_id']} not found in the index."

    p = points[0].payload
    return (
        f"Title: {p['title']}\n"
        f"Authors: {', '.join(p.get('authors', []))}\n"
        f"Date: {p.get('date', 'N/A')[:10]}\n"
        f"Category: {p.get('category', 'N/A')}\n"
        f"Abstract: {p.get('abstract', 'N/A')}"
    )


def _summarise_topic(args: dict, qdrant: QdrantClient) -> str:
    max_papers = min(args.get("max_papers", 5), 10)
    candidates = hybrid_search(qdrant, args["topic"], top_k=20)
    results = rerank(args["topic"], candidates, top_n=max_papers)

    if not results:
        return "No papers found on this topic."

    seen_ids = set()
    unique = []
    for r in results:
        if r["paper_id"] not in seen_ids:
            seen_ids.add(r["paper_id"])
            unique.append(r)

    lines = [f"Found {len(unique)} papers on '{args['topic']}':\n"]
    for r in unique:
        lines.append(f"[{r['paper_id']}] {r['title']} ({r['date'][:10]})\n{r['text'][:400]}...")
    return "\n\n".join(lines)
