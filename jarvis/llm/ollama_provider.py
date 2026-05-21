from __future__ import annotations

import json
import uuid
from typing import Any

import ollama

from .base import LLM, ChatResult, Message, ToolCall, ToolSpec


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.1") -> None:
        self.client = ollama.Client(host=host)
        self.model = model

    def chat(
        self,
        messages: list[Message],
        *,
        system: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResult:
        oll_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        oll_messages.extend(_to_ollama_messages(messages))

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": oll_messages,
            "options": {"num_predict": max_tokens},
        }
        if tools:
            kwargs["tools"] = _to_ollama_tools(tools)

        resp = self.client.chat(**kwargs)
        msg = resp.get("message", {}) if isinstance(resp, dict) else resp.message
        content = _get(msg, "content", "") or ""
        tool_calls_raw = _get(msg, "tool_calls", None) or []

        calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            fn = _get(tc, "function", {}) or {}
            name = _get(fn, "name", "")
            args = _get(fn, "arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            # Ollama doesn't always return a stable tool_call id — synthesize one.
            calls.append(ToolCall(id=str(uuid.uuid4()), name=name, arguments=args))

        return ChatResult(text=content, tool_calls=calls, raw=resp)


def _get(obj: Any, key: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_ollama_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _to_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in m.tool_calls
                ]
            out.append(entry)
        elif m.role == "tool":
            out.append({"role": "tool", "content": m.content})
    return out
