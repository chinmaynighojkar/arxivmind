"""Demo: run 3 live queries against the ArxivMind API."""

import httpx

BASE = "http://localhost:8000"

token = httpx.post(
    BASE + "/token", data={"username": "arxivmind-client", "password": "change-me"}
).json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

queries = [
    "What are the latest approaches to reducing hallucination in LLMs?",
    "Summarise recent work on efficient transformer architectures",
    "What is LoRA and how is it used for fine-tuning?",
]

for q in queries:
    resp = httpx.post(BASE + "/query", json={"query": q}, headers=headers, timeout=120).json()
    print(f"\nQ: {q}")
    print(f"A: {resp['answer'][:400]}...")
    print(f"Sources: {resp['sources']}")
    print(f"Iterations: {resp['iterations']} | Latency: {resp['latency_ms']}ms")
    print("-" * 70)
