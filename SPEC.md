# ArxivMind MCP Tool Server — Spec

## Objective

Expose ArxivMind's RAG capabilities as MCP tools so Claude Code can query the
paper index directly. Target: local development use + portfolio demonstration.

## Commands

```bash
# Install MCP SDK
pip install mcp

# Run the server (Claude Code wires this via .mcp.json)
python mcp/server.py

# Test manually
echo '{}' | python mcp/server.py
```

## Project Structure

```
arxivmind/
└── mcp_server/
    ├── __init__.py
    └── server.py        # Single-file MCP server, stdio transport
```

No new config files. Uses existing env vars: `QDRANT_URL`, `QDRANT_API_KEY`,
`QDRANT_COLLECTION`, `LLM_BACKEND`, `GROQ_API_KEY` / `OLLAMA_HOST`.

## Tools Exposed

| MCP Tool | Wraps | Has LLM? |
|---|---|---|
| `search_papers` | `agent/tools._search_papers()` | No |
| `get_paper` | `agent/tools._get_paper()` | No |
| `summarise_topic` | `agent/tools._summarise_topic()` | No |
| `ask_question` | `agent/loop.run()` | Yes |

## Code Style

- Match existing style: type hints, structlog, no docstrings on obvious functions
- No new abstractions — thin wrapper only
- Use `asyncio.to_thread` for blocking Qdrant/LLM calls (same pattern as `api/routes/query.py`)

## Testing Strategy

- One test file: `tests/test_mcp.py`
- Test each tool handler function directly (not via MCP protocol)
- Mock Qdrant client (same approach as `tests/test_retrieval.py`)
- No integration tests (requires live Qdrant)

## Boundaries

- **Always:** validate inputs before passing to tools (paper_id format, query length)
- **Never:** expose auth, modify existing modules, add a new HTTP server
- **Ask first:** adding new tools beyond the four listed above

## Claude Code Integration

After building, add to `C:\Users\chinm\.claude\settings.json`:

```json
"mcpServers": {
  "arxivmind": {
    "command": "python",
    "args": ["C:/Projects/arxivmind/mcp/server.py"],
    "env": {
      "QDRANT_URL": "http://localhost:6333",
      "LLM_BACKEND": "groq"
    }
  }
}
```
