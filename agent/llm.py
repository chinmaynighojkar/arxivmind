"""LLM client abstraction. Switch backends with LLM_BACKEND env var."""

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx
from openai import OpenAI

LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class LLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> dict:
        """
        Send messages and optional tools. Returns:
        {"content": str, "tool_calls": list | None, "usage": dict}
        """


class OllamaClient(LLMClient):
    def chat(self, messages, tools=None, max_tokens=1024) -> dict:
        payload: dict[str, Any] = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools

        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message", {})
        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls"),
            "usage": data.get("usage", {}),
        }


class GroqClient(LLMClient):
    def __init__(self):
        self._client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

    def chat(self, messages, tools=None, max_tokens=1024) -> dict:
        kwargs: dict[str, Any] = {
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        return {
            "content": choice.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (choice.tool_calls or [])
            ]
            or None,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
        }


def get_llm_client() -> LLMClient:
    if LLM_BACKEND == "groq":
        return GroqClient()
    return OllamaClient()
