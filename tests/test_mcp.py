"""Unit tests for MCP tool handlers — mocked Qdrant, no live services."""

from unittest.mock import MagicMock, patch

import pytest

# Patch heavy imports before loading server module
with patch("agent.llm.get_llm_client"), patch("qdrant_client.QdrantClient"):
    from mcp_server.server import call_tool, list_tools


@pytest.fixture
def mock_qdrant():
    return MagicMock()


@pytest.mark.asyncio
async def test_list_tools_returns_four():
    tools = await list_tools()
    names = {t.name for t in tools}
    assert names == {"search_papers", "ask_question", "get_paper", "summarise_topic"}


@pytest.mark.asyncio
async def test_list_tools_have_required_fields():
    tools = await list_tools()
    for tool in tools:
        assert tool.name
        assert tool.description
        assert "required" in tool.inputSchema


@pytest.mark.asyncio
async def test_search_papers(mock_qdrant):
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.execute_tool", return_value="[2312.00001] Test Paper\nExcerpt...") as mock_exec,
    ):
        result = await call_tool("search_papers", {"query": "attention mechanism"})
        mock_exec.assert_called_once_with("search_papers", {"query": "attention mechanism"}, mock_qdrant)
        assert len(result) == 1
        assert "2312.00001" in result[0].text


@pytest.mark.asyncio
async def test_search_papers_with_filters(mock_qdrant):
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.execute_tool", return_value="No papers found.") as mock_exec,
    ):
        args = {"query": "diffusion models", "category": "cs.LG", "date_from": "2025-01-01"}
        await call_tool("search_papers", args)
        mock_exec.assert_called_once_with("search_papers", args, mock_qdrant)


@pytest.mark.asyncio
async def test_get_paper(mock_qdrant):
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.execute_tool", return_value="Title: Test\nAuthors: Alice") as mock_exec,
    ):
        result = await call_tool("get_paper", {"paper_id": "2312.00001"})
        mock_exec.assert_called_once_with("get_paper", {"paper_id": "2312.00001"}, mock_qdrant)
        assert "Title" in result[0].text


@pytest.mark.asyncio
async def test_summarise_topic(mock_qdrant):
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.execute_tool", return_value="Found 3 papers on 'RL':...") as mock_exec,
    ):
        result = await call_tool("summarise_topic", {"topic": "RL", "max_papers": 3})
        mock_exec.assert_called_once_with("summarise_topic", {"topic": "RL", "max_papers": 3}, mock_qdrant)
        assert "RL" in result[0].text


@pytest.mark.asyncio
async def test_ask_question(mock_qdrant):
    fake_result = {
        "answer": "Transformers use self-attention.",
        "sources": ["2312.00001", "2312.00002"],
        "iterations": 1,
        "latency_ms": 100,
        "error": None,
    }
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.get_llm_client", return_value=MagicMock()),
        patch("mcp_server.server.loop.run", return_value=fake_result),
    ):
        result = await call_tool("ask_question", {"query": "How do transformers work?"})
        assert "self-attention" in result[0].text
        assert "2312.00001" in result[0].text


@pytest.mark.asyncio
async def test_ask_question_error(mock_qdrant):
    fake_result = {
        "answer": "",
        "sources": [],
        "iterations": 1,
        "latency_ms": 50,
        "error": "An error occurred while processing your query.",
    }
    with (
        patch("mcp_server.server._get_qdrant", return_value=mock_qdrant),
        patch("mcp_server.server.get_llm_client", return_value=MagicMock()),
        patch("mcp_server.server.loop.run", return_value=fake_result),
    ):
        result = await call_tool("ask_question", {"query": "bad query"})
        assert "Error" in result[0].text


@pytest.mark.asyncio
async def test_unknown_tool(mock_qdrant):
    with patch("mcp_server.server._get_qdrant", return_value=mock_qdrant):
        result = await call_tool("nonexistent_tool", {})
        assert "Unknown tool" in result[0].text
