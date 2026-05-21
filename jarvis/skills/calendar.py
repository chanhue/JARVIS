"""LLM tool calling 으로 호출되는 캘린더 스킬.

LLM 은 시스템 프롬프트의 "현재 시각" 힌트를 참고해 ISO 8601 문자열로 시간을
정해서 넘긴다. 타임존이 없으면 시스템 로컬 타임존으로 해석한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..calendar import Event, EventStore
from .base import Skill


def _parse_dt(value: str) -> datetime:
    """ISO 8601 파서. 타임존 없으면 로컬 타임존으로."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def _format(e: Event) -> str:
    s = e.start.astimezone()
    en = e.end.astimezone()
    same_day = s.date() == en.date()
    if same_day:
        when = f"{s.strftime('%Y-%m-%d %H:%M')}~{en.strftime('%H:%M')}"
    else:
        when = f"{s.strftime('%Y-%m-%d %H:%M')} ~ {en.strftime('%Y-%m-%d %H:%M')}"
    line = f"[{e.id[:6]}] {when}  {e.title}"
    if e.description:
        line += f"  — {e.description}"
    return line


class CreateEventSkill(Skill):
    name = "create_event"
    description = (
        "캘린더에 새 일정을 추가한다. 시작/종료 시각은 ISO 8601 문자열 "
        "(예: '2026-05-22T15:00:00+09:00' 또는 타임존 생략 시 로컬 기준 "
        "'2026-05-22T15:00:00'). 종료 시각이 명확하지 않으면 시작 후 1시간으로 잡는다."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "일정 제목"},
            "start": {"type": "string", "description": "시작 시각 (ISO 8601)"},
            "end": {
                "type": "string",
                "description": "종료 시각 (ISO 8601). 없으면 start + 1시간",
            },
            "description": {
                "type": "string",
                "description": "선택 사항. 추가 메모/설명",
            },
        },
        "required": ["title", "start"],
    }

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def run(
        self,
        title: str,
        start: str,
        end: Optional[str] = None,
        description: str = "",
    ) -> str:
        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end) if end else start_dt + timedelta(hours=1)
        if end_dt <= start_dt:
            return "[error] 종료 시각이 시작 시각보다 빠르거나 같습니다."
        event = Event(
            title=title.strip(),
            start=start_dt,
            end=end_dt,
            description=(description or "").strip(),
        )
        self.store.add(event)
        return f"일정 추가됨: {_format(event)}"


class ListEventsSkill(Skill):
    name = "list_events"
    description = (
        "특정 기간의 일정을 조회한다. from/to 는 ISO 8601 문자열. "
        "조회 결과가 없으면 그 점을 사용자에게 알려라."
    )
    parameters = {
        "type": "object",
        "properties": {
            "from": {
                "type": "string",
                "description": "시작 시각 (ISO 8601). 포함",
            },
            "to": {
                "type": "string",
                "description": "끝 시각 (ISO 8601). 미포함",
            },
        },
        "required": ["from", "to"],
    }

    def __init__(self, store: EventStore) -> None:
        self.store = store

    # 파이썬 예약어 'from' 이라 kwargs 로 받음
    def run(self, **kwargs) -> str:
        try:
            start = _parse_dt(kwargs["from"])
            end = _parse_dt(kwargs["to"])
        except KeyError as e:
            return f"[error] 필수 인자 누락: {e}"
        if end <= start:
            return "[error] to 가 from 보다 빠르거나 같습니다."
        events = self.store.list_in_range(start, end)
        if not events:
            return "해당 기간에 등록된 일정이 없습니다."
        lines = [_format(e) for e in events]
        return f"일정 {len(events)}건:\n" + "\n".join(lines)


class DeleteEventSkill(Skill):
    name = "delete_event"
    description = (
        "일정을 삭제한다. event_id 가 주어지면 해당 id 만 정확히 지운다. "
        "event_id 가 없으면 query (제목/설명 일부) 로 검색해 정확히 1건이면 삭제, "
        "여러 건이면 후보 목록을 돌려준다. (사용자에게 다시 물어봐서 골라야 함)"
    )
    parameters = {
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "삭제할 이벤트의 id (앞 6자도 허용)",
            },
            "query": {
                "type": "string",
                "description": "제목/설명에서 부분 매칭할 검색어",
            },
        },
    }

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def run(self, event_id: str = "", query: str = "") -> str:
        if event_id:
            for e in self.store.load():
                if e.id == event_id or e.id.startswith(event_id):
                    self.store.delete(e.id)
                    return f"삭제됨: {_format(e)}"
            return f"[error] id 일치하는 이벤트 없음: {event_id}"

        if not query.strip():
            return "[error] event_id 또는 query 중 하나는 필요합니다."

        matches = self.store.search(query)
        if not matches:
            return f"매칭되는 일정이 없습니다: {query!r}"
        if len(matches) > 1:
            lines = [_format(e) for e in matches]
            return (
                f"여러 일정이 매칭됐어요 ({len(matches)}건). 어떤 걸 지울지 확인 필요:\n"
                + "\n".join(lines)
            )
        target = matches[0]
        self.store.delete(target.id)
        return f"삭제됨: {_format(target)}"
