"""ArxivMind MCP Tool Server — stdio transport."""

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from qdrant_client import QdrantClient

from agent import loop
from agent.llm import get_llm_client
from agent.tools import execute_tool

logger = structlog.get_logger()

app = Server("arxivmind")

_qdrant: QdrantClient | None = None


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )
    return _qdrant


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_papers",
            description="Semantic search over ingested Arxiv ML papers. Returns top matching paper excerpts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {
                        "type": "string",
                        "description": "Arxiv category e.g. cs.LG, cs.AI",
                    },
                    "date_from": {"type": "string", "description": "ISO date e.g. 2025-01-01"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="ask_question",
            description="Ask a research question. Runs full RAG loop: retrieves papers then synthesises answer with citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Research question"},
                    "category": {"type": "string", "description": "Arxiv category filter"},
                    "date_from": {"type": "string", "description": "ISO date filter"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_paper",
            description="Get title, authors, date, category and abstract for a specific paper by Arxiv ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string", "description": "Arxiv ID e.g. 2312.12456"},
                },
                "required": ["paper_id"],
            },
        ),
        Tool(
            name="summarise_topic",
            description="Retrieve and summarise multiple papers on a research topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Research topic"},
                    "max_papers": {
                        "type": "integer",
                        "description": "Max papers to include (default 5)",
                    },
                },
                "required": ["topic"],
            },
        ),
    ]


_MAX_QUERY_LEN = 1000
_MAX_CATEGORY_LEN = 20


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    for field in ("query", "topic"):
        if len(arguments.get(field, "")) > _MAX_QUERY_LEN:
            return [
                TextContent(
                    type="text",
                    text=f"Error: '{field}' exceeds maximum length of {_MAX_QUERY_LEN} characters.",
                )
            ]
    if len(arguments.get("category", "")) > _MAX_CATEGORY_LEN:
        return [
            TextContent(
                type="text",
                text=f"Error: 'category' exceeds maximum length of {_MAX_CATEGORY_LEN} characters.",
            )
        ]

    qdrant = _get_qdrant()

    if name == "search_papers":
        result = await asyncio.to_thread(execute_tool, "search_papers", arguments, qdrant)
        return [TextContent(type="text", text=result)]

    if name == "ask_question":
        query = arguments.get("query", "")
        filters = {k: v for k, v in arguments.items() if k != "query" and v is not None}
        llm = get_llm_client()
        result = await asyncio.to_thread(loop.run, query, qdrant, llm, filters or None)
        text = result["answer"]
        if result["sources"]:
            text += f"\n\nSources: {', '.join(result['sources'])}"
        if result["error"]:
            text = f"Error: {result['error']}"
        return [TextContent(type="text", text=text)]

    if name == "get_paper":
        result = await asyncio.to_thread(execute_tool, "get_paper", arguments, qdrant)
        return [TextContent(type="text", text=result)]

    if name == "summarise_topic":
        result = await asyncio.to_thread(execute_tool, "summarise_topic", arguments, qdrant)
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
