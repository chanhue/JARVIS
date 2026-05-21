from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "tool"]


@dataclass
class ToolSpec:
    """Provider-independent description of a tool the LLM can call."""

    name: str
    description: str
    # JSON Schema for arguments
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """One turn in the conversation.

    For tool results, set role='tool', tool_call_id to the call's id, and put
    the stringified result in `content`.
    """

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ChatResult:
    text: str
    tool_calls: list[ToolCall]
    raw: Any = None  # provider-specific response, for debugging


class LLM(ABC):
    """Common interface every provider implements."""

    name: str

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        *,
        system: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResult: ...
