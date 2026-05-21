from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from .base import LLM, ChatResult, Message, ToolCall, ToolSpec


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-opus-4-7") -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def chat(
        self,
        messages: list[Message],
        *,
        system: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResult:
        anthro_messages = _to_anthropic_messages(messages)
        anthro_tools = _to_anthropic_tools(tools or [])

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": anthro_messages,
        }
        if anthro_tools:
            kwargs["tools"] = anthro_tools

        resp = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                args = block.input if isinstance(block.input, dict) else {}
                calls.append(ToolCall(id=block.id, name=block.name, arguments=args))

        return ChatResult(text="".join(text_parts), tool_calls=calls, raw=resp)


def _to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


def _to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate our generic messages to Anthropic's content-block format.

    Anthropic doesn't have a 'tool' role — tool results are user messages
    containing a tool_result content block. Assistant messages that issued
    tool_use blocks must reproduce them so the API can pair results.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            out.append({"role": "assistant", "content": blocks or m.content})
        elif m.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": m.content,
                        }
                    ],
                }
            )
    return out
