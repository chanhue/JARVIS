from __future__ import annotations

from datetime import datetime

from .config import Settings
from .llm import LLM, Message, create_llm
from .skills import SkillRegistry, default_registry

# 안전장치: tool_call이 무한히 이어지는 걸 막기 위해 한 턴당 최대 호출 수.
MAX_TOOL_HOPS = 6

_KO_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


class Jarvis:
    """Jarvis 메인 오케스트레이터.

    한 번의 user input → (LLM 응답 + tool 호출 반복) → 최종 텍스트 응답.
    대화 히스토리는 메모리에 유지하되, settings.llm.history_turns 만큼만 잘라둔다.
    """

    def __init__(
        self,
        settings: Settings,
        llm: LLM | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.llm = llm or create_llm(settings.user)
        self.registry = registry or default_registry()
        self.history: list[Message] = []

    def respond(self, user_text: str) -> str:
        self.history.append(Message(role="user", content=user_text))

        for _ in range(MAX_TOOL_HOPS):
            result = self.llm.chat(
                messages=self.history,
                system=self._system_with_time(),
                tools=self.registry.tool_specs(),
                max_tokens=self.settings.llm.max_tokens,
            )

            self.history.append(
                Message(
                    role="assistant",
                    content=result.text,
                    tool_calls=result.tool_calls,
                )
            )

            if not result.tool_calls:
                self._trim_history()
                return result.text

            for call in result.tool_calls:
                output = self.registry.dispatch(call.name, call.arguments)
                self.history.append(
                    Message(role="tool", content=output, tool_call_id=call.id)
                )

        self._trim_history()
        return "(도구 호출이 너무 길어져 중단했어요.)"

    def _system_with_time(self) -> str:
        """매 LLM 호출마다 현재 시각을 시스템 프롬프트에 끼워넣는다.

        '내일', '다음 주' 같은 상대 표현을 안정적으로 해석하려면 LLM 이 절대
        시각을 알아야 한다. 호출 비용 무시할 만하니 매 턴 새로 만들어 넣는다.
        """
        now = datetime.now().astimezone()
        iso = now.isoformat(timespec="seconds")
        tz_name = now.tzname() or ""
        weekday = _KO_WEEKDAYS[now.weekday()]
        return (
            self.settings.system_prompt
            + f"\n\n[현재 시각: {iso} ({weekday}요일, {tz_name})]"
        )

    def _trim_history(self) -> None:
        """user/assistant 쌍 기준 N턴만 남기되, 매달린 tool_use/tool_result는 깨지 않도록 보존."""
        max_msgs = self.settings.llm.history_turns * 2 * 2  # 여유롭게 (tool 메시지 포함)
        if len(self.history) <= max_msgs:
            return
        # 잘라낼 때 user 경계에서 자른다.
        drop = len(self.history) - max_msgs
        # drop 위치 이후 첫 user 메시지를 새 시작점으로.
        i = drop
        while i < len(self.history) and self.history[i].role != "user":
            i += 1
        self.history = self.history[i:]
