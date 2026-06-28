# ArxivMind

A RAG system that lets you query a database of Arxiv ML research papers through a web UI, REST API, or directly from Claude Code via MCP. Built with FastAPI, Next.js, Qdrant, sentence-transformers, and an agentic retrieval loop.

## What it does

Ask questions about ML research and get grounded, cited answers pulled from real papers:

```
Q: What are the latest approaches to reducing hallucination in LLMs?

A: The latest approaches include Hallucination Rejection Sampling [2606.03628v1],
   which addresses snowballing errors in long-form generation, and grounding
   techniques that combine retrieval with constrained decoding [2606.03731v1]...

Sources: 2606.03628v1, 2606.03731v1, 2606.03022v1
```

## Architecture

```
Browser
  └── Next.js 15 frontend (localhost:3000)
        └── Server-side API proxy routes (/api/*)
              └── FastAPI (RS256 JWT auth, rate limiting, structured logging)
                    └── Agentic Loop
                          ├── Initial retrieval (always runs before LLM)
                          ├── Tool router (search, fetch, summarise)
                          └── LLM synthesis (Ollama local | Groq deployed)

Claude Code
  └── MCP Tool Server (stdio)
        ├── search_papers
        ├── ask_question  ←── full agentic loop
        ├── get_paper
        └── summarise_topic

Ingestion pipeline (one-shot or per-paper via UI):
  Arxiv API -> sentence-transformers -> Qdrant          (--skip-download, abstracts only)
  Arxiv API -> PyMuPDF -> Section-aware chunker -> sentence-transformers -> Qdrant  (full PDF)
```

The LLM backend is configured via `LLM_BACKEND`: set to `ollama` for local development, `groq` for production. The agent loop is identical for both.

## MCP Tool Server

ArxivMind exposes its RAG capabilities as MCP tools so Claude Code can query the paper index directly, with no HTTP calls or token management.

### Tools

| Tool | Description |
|---|---|
| `search_papers` | Semantic search over ingested papers. Returns top matching excerpts. |
| `ask_question` | Full agentic RAG loop: retrieves papers then synthesises a cited answer. |
| `get_paper` | Fetch title, authors, date, category, and abstract by Arxiv ID. |
| `summarise_topic` | Retrieve and summarise multiple papers on a research topic. |

### Setup

```bash
pip install mcp
```

A `.mcp.json` file is included at the project root. Claude Code picks it up automatically when you open the project:

```json
{
  "mcpServers": {
    "arxivmind": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "LLM_BACKEND": "groq"
      }
    }
  }
}
```

The four tools are available in any Claude Code session where Qdrant is running.

## Evaluation results

Evaluated with RAGAS on a hand-crafted golden set (10 questions, 400-paper corpus):

| Metric | Score |
|---|---|
| Answer Similarity | 0.619 |
| Retrieval Coverage | 1.000 |
| Citation Rate | 1.000 |
| Answer Completeness | 1.000 |

*Model: qwen2.5:7b local. Answer similarity uses cosine distance scored by all-MiniLM-L6-v2 — the same model used for indexing, so it is not independent. The golden set is small and hand-authored; treat these numbers as a functional smoke test rather than a rigorous benchmark. Eval script and golden set are in `eval/`.*

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 (App Router), Tailwind CSS |
| API | FastAPI + uvicorn |
| Auth | RS256 JWT, token endpoint (client credentials form) |
| Vector DB | Qdrant (Docker local, Qdrant Cloud deployed) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Re-ranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| LLM (local) | qwen2.5:7b via Ollama |
| LLM (deployed) | llama-3.1-8b via Groq |
| MCP server | mcp (stdio transport) |
| Evaluation | RAGAS |
| Logging | structlog (JSON) |
| Rate limiting | slowapi |

## Getting started

**Prerequisites:** Docker Desktop, Python 3.11+, Ollama, Node.js 18+

```bash
# Clone and install
git clone https://github.com/chinmaynighojkar/arxivmind
cd arxivmind
pip install -e .

# Configure env vars (do this before anything else)
cp .env.example .env   # fill in OAUTH_CLIENT_SECRET and QDRANT_URL

# Generate RS256 keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

# Pull the LLM model
ollama pull qwen2.5:7b

# Start Qdrant
docker compose up -d qdrant

# Ingest papers — abstracts only, fast (~2 min)
python scripts/ingest.py --limit 400 --skip-download
# Or full PDF pipeline, slower (~30 min for 100 papers)
# python scripts/ingest.py --limit 100

# Start the API
uvicorn api.main:app --reload
```

### Frontend (optional)

```bash
cd frontend
cp .env.local.example .env.local   # fill in ARXIVMIND_CLIENT_SECRET
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — five tabs: Ask, Search Papers, Ingest Paper, Summarise Topic, and Papers (full index listing with filter).

## Usage

```bash
# Get a token (username = client ID, password = OAUTH_CLIENT_SECRET from .env)
curl -X POST http://localhost:8000/token \
  -d "username=arxivmind-client&password=<your-OAUTH_CLIENT_SECRET>&scope=read:query"

# Query
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LoRA and how is it used for fine-tuning?"}'
```

## Endpoints

| Endpoint | Method | Scope | Description |
|---|---|---|---|
| `/token` | POST | — | Issue a signed JWT (pass client ID + secret as username/password) |
| `/query` | POST | `read:query` | RAG query with agentic retrieval |
| `/search` | POST | `read:query` | Semantic paper search, returns structured results |
| `/summarise` | POST | `read:query` | Summarise papers on a topic |
| `/papers` | GET | `read:query` | List all indexed papers (sorted by date) |
| `/ingest` | POST | `write:ingest` | Fetch, parse, and index a paper by Arxiv ID |
| `/refresh` | POST | `write:ingest` | Pull latest Arxiv ML papers, skip already-indexed ones |
| `/health` | GET | — | Liveness check |
| `/ready` | GET | — | Readiness check (Qdrant reachable) |
| `/metrics` | GET | — | Request count, latency, error rate |

## Project structure

```
arxivmind/
├── frontend/       # Next.js 15 UI (5 tabs, server-side API proxy)
├── ingestion/      # Arxiv fetch, PDF parse, chunk, embed
├── retrieval/      # Dense search, cross-encoder re-ranking
├── agent/          # LLM abstraction, tool definitions, agentic loop
├── api/            # FastAPI routes, auth, middleware
├── mcp_server/     # MCP stdio tool server (Claude Code integration)
├── eval/           # Golden set, RAGAS evaluation script, scores
└── scripts/        # Ingestion runner, demo queries
```

## Adversarial testing

Five attack categories tested (prompt injection, role confusion, data exfiltration, cost amplification, context poisoning) with documented mitigations. See [SECURITY.md](SECURITY.md).

## Security hardening

Rate limiting on all endpoints, timing-safe secret comparison (`hmac.compare_digest`), startup `RuntimeError` if RS256 keys or `OAUTH_CLIENT_SECRET` are missing, LLM-controlled inputs validated before reaching the database, and structured error responses that never leak internal details. See [SECURITY.md](SECURITY.md) for the full list.
