"""사용자 셋업 상태 저장소.

~/.jarvis/state.json 에 사용자 이름, 선택한 provider, provider별 API 키를 저장.
.env 파일을 대체한다 — UI 셋업 모달이 여기에 쓴다.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["anthropic", "openai", "ollama", "gemini"]

STATE_DIR = Path.home() / ".jarvis"
STATE_FILE = STATE_DIR / "state.json"


class UserState(BaseModel):
    user_name: str = ""
    provider: Provider = "anthropic"

    # provider별 키 — 둘 다 저장해두면 provider 전환 시 재입력 불필요
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    def is_complete(self) -> bool:
        """현재 선택된 provider 기준으로 셋업이 끝났는지."""
        if not self.user_name.strip():
            return False
        if self.provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.provider == "openai":
            return bool(self.openai_api_key)
        if self.provider == "ollama":
            return bool(self.ollama_host)
        if self.provider == "gemini":
            return bool(self.gemini_api_key)
        return False

    def active_key_present(self) -> bool:
        return self.is_complete()


def load_state() -> UserState:
    if not STATE_FILE.exists():
        return UserState()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserState()
    return UserState(**data)


def save_state(state: UserState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    # API 키 들어있으니 사용자 본인만 읽도록.
    try:
        os.chmod(STATE_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def update_state(**fields) -> UserState:
    state = load_state()
    merged = state.model_copy(update=fields)
    save_state(merged)
    return merged
