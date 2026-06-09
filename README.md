# ArxivMind

A production-grade RAG system that lets you query a database of Arxiv ML research papers through a natural language API. Built with FastAPI, Qdrant, and a local LLM via Ollama.

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
Client
  └── FastAPI (OAuth 2.0, rate limiting, structured logging)
        └── Agentic Loop
              ├── Initial retrieval (always runs before LLM)
              ├── Tool router (search, fetch, summarise)
              └── LLM synthesis (Ollama local | Groq deployed)

Ingestion pipeline (one-shot):
  Arxiv API -> PyMuPDF -> Section-aware chunker -> sentence-transformers -> Qdrant
```

The LLM backend is configured via `LLM_BACKEND`: set to `ollama` for local development, `groq` for production. The agent loop is identical for both.

## Evaluation results

Evaluated on 10 questions from a hand-crafted golden set:

| Metric | Score |
|---|---|
| Answer Similarity | 0.619 |
| Retrieval Coverage | 1.000 |
| Citation Rate | 1.000 |
| Answer Completeness | 1.000 |

*Answer similarity uses cosine distance between generated and reference answers (sentence-transformers/all-MiniLM-L6-v2). Model: qwen2.5:7b local. Corpus: 400 Arxiv papers.*

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + uvicorn |
| Auth | OAuth 2.0 client credentials, RS256 JWT |
| Vector DB | Qdrant (Docker local, Qdrant Cloud deployed) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Re-ranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| LLM (local) | qwen2.5:7b via Ollama |
| LLM (deployed) | llama-3.1-8b via Groq |
| Logging | structlog (JSON) |
| Rate limiting | slowapi |

## Getting started

**Prerequisites:** Docker Desktop, Python 3.11+, Ollama

```bash
# Clone and install
git clone https://github.com/chinmaynighojkar/arxivmind
cd arxivmind
pip install -r requirements.txt   # or: uv pip install -e .

# Pull the model
ollama pull qwen2.5:7b

# Start Qdrant
docker compose up -d qdrant

# Ingest papers (abstracts only, ~2 min)
python scripts/ingest.py --limit 400 --skip-download

# Start the API
uvicorn api.main:app --reload
```

## Usage

```bash
# Get a token
curl -X POST http://localhost:8000/token \
  -d "username=arxivmind-client&password=change-me"

# Query
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LoRA and how is it used for fine-tuning?"}'
```

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/token` | POST | OAuth 2.0 token (client credentials) |
| `/query` | POST | RAG query with agentic retrieval |
| `/health` | GET | Liveness check |
| `/ready` | GET | Readiness check (Qdrant + model) |
| `/metrics` | GET | Request count, latency, error rate |

## Project structure

```
arxivmind/
├── ingestion/      # Arxiv fetch, PDF parse, chunk, embed
├── retrieval/      # Dense search, cross-encoder re-ranking
├── agent/          # LLM abstraction, tool definitions, agentic loop
├── api/            # FastAPI routes, auth, middleware
├── eval/           # Golden set, evaluation script, scores
└── scripts/        # Ingestion runner, demo queries
```

## Adversarial testing

Five attack categories tested (prompt injection, role confusion, data exfiltration, cost amplification, context poisoning) with documented mitigations. See [SECURITY.md](SECURITY.md).

## Security & reliability hardening

A post-build review of the codebase identified and resolved several correctness and security issues across the API, agent layer, and ingestion pipeline.

**Concurrency:** the agentic loop (httpx calls to Ollama, sentence-transformer encoding, cross-encoder re-ranking) was running synchronously inside an async FastAPI handler, blocking the event loop for the full query duration (~30s worst case). Wrapped in `asyncio.to_thread` so concurrent requests are handled correctly.

**Rate limiting:** `slowapi` was wired up at the app level but the `@limiter.limit()` decorator was never applied to the `/query` route, leaving the endpoint unthrottled. Applied 20 req/min per IP.

**Auth hardening:** three issues addressed. The RS256-to-HS256 fallback when key files were missing was silent; a misconfigured production deploy would silently accept tokens signed with a known string. Changed to raise `RuntimeError` at startup. Client secret comparison used `!=`, which is vulnerable to timing attacks; switched to `hmac.compare_digest`. JWT verification errors returned the raw exception string to the caller; now logged server-side with a generic `"Invalid token"` response.

**API contract correctness:** `category` and `date_from` fields were accepted in `QueryRequest` but never propagated to the retrieval pipeline. Threaded them through `loop.run` and `execute_tool` so filters are actually applied.

**LLM output trust boundary:** the `get_paper` tool passed the LLM-generated `paper_id` argument directly into a Qdrant scroll query without validation. Added an Arxiv ID pattern check before it reaches the database. Also replaced the raw dict filter syntax with proper Qdrant `Filter`/`FieldCondition` model classes.

**Error handling:** agent loop exceptions were returned as HTTP 200 with `error: str(e)`, leaking internal details. Exceptions are now logged via structlog with `exc_info=True`; the API returns HTTP 500 with a generic message.

**Input validation:** `QueryRequest.query` had no length constraints, accepting empty strings or arbitrarily large payloads. Added `min_length=1` and `max_length=1000` via Pydantic `Field`.

**Logging consistency:** the ingestion pipeline (`fetch.py`) used `print()` while every other module used structlog. Replaced all print calls with structured log events.

**Metrics clarity:** the in-memory request counters in `middleware.py` reset on every process restart and are not persisted across deploys. Added a comment to make the scope explicit.
