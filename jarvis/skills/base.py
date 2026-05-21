from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..llm.base import ToolSpec


class Skill(ABC):
    """One action Jarvis can perform.

    Subclasses set `name`, `description`, and `parameters` (JSON Schema for
    the arguments object). The LLM picks them up as tool definitions.
    """

    name: str
    description: str
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """Execute the skill and return a short string for the LLM."""

    def to_tool_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"이미 등록된 스킬: {skill.name}")
        self._skills[skill.name] = skill

    def names(self) -> list[str]:
        return list(self._skills)

    def tool_specs(self) -> list[ToolSpec]:
        return [s.to_tool_spec() for s in self._skills.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        skill = self._skills.get(name)
        if skill is None:
            return f"[error] 알 수 없는 스킬: {name}"
        try:
            return skill.run(**arguments)
        except TypeError as e:
            return f"[error] {name} 인자 오류: {e}"
        except Exception as e:  # noqa: BLE001
            return f"[error] {name} 실행 실패: {e}"
