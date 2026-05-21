from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .base import LLM, ChatResult, Message, ToolCall, ToolSpec


class OpenAILLM(LLM):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat(
        self,
        messages: list[Message],
        *,
        system: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResult:
        oai_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        oai_messages.extend(_to_openai_messages(messages))

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)

        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        text = msg.content or ""

        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return ChatResult(text=text, tool_calls=calls, raw=resp)


def _to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
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


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in m.tool_calls
                ]
            out.append(entry)
        elif m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content,
                }
            )
    return out
