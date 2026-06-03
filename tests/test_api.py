"""Basic API tests — auth, health, and query endpoint contract."""

import os
os.environ.setdefault("LLM_BACKEND", "ollama")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_token_invalid_credentials():
    resp = client.post("/token", data={"username": "wrong", "password": "wrong"})
    assert resp.status_code == 401


def test_token_valid():
    resp = client.post(
        "/token",
        data={"username": "test-client", "password": "test-secret"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_query_requires_auth():
    resp = client.post("/query", json={"query": "What is attention?"})
    assert resp.status_code == 401


def test_query_with_valid_token():
    token_resp = client.post(
        "/token",
        data={"username": "test-client", "password": "test-secret"},
    )
    token = token_resp.json()["access_token"]

    mock_result = {
        "answer": "Attention is a mechanism...",
        "sources": ["2017.03762"],
        "iterations": 2,
        "latency_ms": 300,
        "error": None,
    }

    with patch("api.routes.query.loop.run", return_value=mock_result), \
         patch("api.routes.query.get_qdrant", return_value=MagicMock()), \
         patch("api.routes.query.get_llm", return_value=MagicMock()):
        resp = client.post(
            "/query",
            json={"query": "What is attention?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
