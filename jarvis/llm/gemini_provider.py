"""Google Gemini provider.

google-genai SDK 를 사용한다 (구 google-generativeai 가 아닌 신 SDK).
Gemini 는 tool_call_id 개념이 없어서 함수 이름으로 호출↔결과를 매칭한다.
우리 generic Message 의 tool_call_id 를 id→name 맵으로 변환해 처리.
"""

from __future__ import annotations

import uuid
from typing import Any

from google import genai
from google.genai import types

from .base import LLM, ChatResult, Message, ToolCall, ToolSpec


class GeminiLLM(LLM):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def chat(
        self,
        messages: list[Message],
        *,
        system: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResult:
        contents = _to_gemini_contents(messages)
        gem_tools = _to_gemini_tools(tools) if tools else None

        config_kwargs: dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
        }
        if gem_tools:
            config_kwargs["tools"] = gem_tools

        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            parts = getattr(candidates[0].content, "parts", None) or []
            for part in parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    args = dict(fc.args) if getattr(fc, "args", None) else {}
                    # Gemini 는 호출 id 를 안 줘서 자체 생성. tool 결과 변환 때
                    # id→name 맵으로 다시 매칭된다.
                    calls.append(
                        ToolCall(id=str(uuid.uuid4()), name=fc.name, arguments=args)
                    )

        return ChatResult(text="".join(text_parts), tool_calls=calls, raw=resp)


def _to_gemini_tools(tools: list[ToolSpec]) -> list[types.Tool]:
    decls = [
        types.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]
    return [types.Tool(function_declarations=decls)]


def _to_gemini_contents(messages: list[Message]) -> list[types.Content]:
    """generic Message → Gemini Content 변환.

    Gemini 룰:
      - assistant 메시지 → role="model"
      - tool 결과 → role="user" + function_response part
      - function_response 는 함수 이름이 필요해서 직전 assistant 의 tool_calls 에서
        id→name 매핑을 만들어 둠
    """
    out: list[types.Content] = []
    id_to_name: dict[str, str] = {}
    for m in messages:
        if m.role == "user":
            out.append(
                types.Content(role="user", parts=[types.Part(text=m.content or "")])
            )
        elif m.role == "assistant":
            parts: list[types.Part] = []
            if m.content:
                parts.append(types.Part(text=m.content))
            for tc in m.tool_calls:
                id_to_name[tc.id] = tc.name
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            name=tc.name, args=tc.arguments
                        )
                    )
                )
            if parts:
                out.append(types.Content(role="model", parts=parts))
        elif m.role == "tool":
            name = id_to_name.get(m.tool_call_id or "", "unknown_function")
            out.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=name,
                                response={"result": m.content},
                            )
                        )
                    ],
                )
            )
    return out
