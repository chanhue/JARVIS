"""로컬 캘린더 저장소.

이벤트를 ~/.jarvis/events.json 에 단순 JSON 배열로 저장한다.
나중에 Google Calendar 등 외부와 동기화할 수 있도록 `external_id` 필드를
미리 비워두지만, 1단계에서는 사용하지 않는다.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .state import STATE_DIR

EVENTS_FILE = STATE_DIR / "events.json"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    start: datetime
    end: datetime
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    # 외부 시스템과 동기화될 때 채워짐 (예: Google Calendar event id)
    external_id: Optional[str] = None


class EventStore:
    def __init__(self, path: Path = EVENTS_FILE) -> None:
        self.path = path

    # ---------- IO ----------

    def load(self) -> list[Event]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        events = [Event(**item) for item in data]
        events.sort(key=lambda e: e.start)
        return events

    def _atomic_write(self, events: list[Event]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [json.loads(e.model_dump_json()) for e in events]
        # 같은 디렉토리에 temp 파일 → rename 으로 원자적 교체
        fd, tmp = tempfile.mkstemp(prefix=".events.", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    # ---------- 조작 ----------

    def add(self, event: Event) -> Event:
        events = self.load()
        events.append(event)
        events.sort(key=lambda e: e.start)
        self._atomic_write(events)
        return event

    def delete(self, event_id: str) -> bool:
        events = self.load()
        new = [e for e in events if e.id != event_id]
        if len(new) == len(events):
            return False
        self._atomic_write(new)
        return True

    def list_in_range(self, start: datetime, end: datetime) -> list[Event]:
        """start <= event.start < end 인 이벤트들."""
        events = self.load()
        return [e for e in events if start <= _aware(e.start) < end]

    def search(self, query: str) -> list[Event]:
        """제목/설명에 query 가 포함된 이벤트."""
        q = query.lower().strip()
        if not q:
            return []
        events = self.load()
        return [
            e for e in events if q in e.title.lower() or q in (e.description or "").lower()
        ]


def _aware(dt: datetime) -> datetime:
    """naive 면 로컬 타임존으로 붙여서 비교 가능하게."""
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt
