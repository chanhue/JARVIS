from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .state import UserState, load_state

Provider = Literal["anthropic", "openai", "ollama", "gemini"]


class STTConfig(BaseModel):
    model: str = "small"
    device: str = "auto"
    compute_type: str = "int8"
    max_record_seconds: int = 15
    silence_threshold: float = 0.012
    silence_duration: float = 1.0
    samplerate: int = 16000


class TTSConfig(BaseModel):
    voices: dict[str, str] = Field(
        default_factory=lambda: {
            "en": "en-GB-RyanNeural",
            "ko": "ko-KR-InJoonNeural",
        }
    )
    default_lang: str = "en"
    rate: str = "+0%"
    volume: str = "+0%"
    offline_fallback: bool = True


class LLMConfig(BaseModel):
    max_tokens: int = 1024
    history_turns: int = 8


class WakeConfig(BaseModel):
    # 발화에서 들리면 깨어나는 키워드 (대소문자 무시, 부분 매칭)
    keywords: list[str] = Field(default_factory=lambda: ["jarvis", "자비스"])
    # 청크 길이 (초). 너무 짧으면 단어 잘리고, 너무 길면 반응이 느려짐
    chunk_seconds: float = 2.0
    # 웨이크 감지에 쓸 모델 (작을수록 빠름)
    model: str = "tiny"
    samplerate: int = 16000
    # 무음 청크는 인식 안 함
    silence_threshold: float = 0.008
    # 깨어났을 때 짧게 응답할 문구. 언어별로 매핑. 빈 문자열이면 응답 안 함.
    ack: dict[str, str] = Field(
        default_factory=lambda: {"ko": "네?", "en": "Yes?"}
    )


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True


class Settings(BaseModel):
    system_prompt: str = "너는 한국어/영어로 답하는 친절한 비서다."
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    wake: WakeConfig = Field(default_factory=WakeConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    user: UserState = Field(default_factory=UserState)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(config_path: str | Path = "config.yaml") -> Settings:
    data = _load_yaml(Path(config_path))
    user = load_state()
    return Settings(**data, user=user)


def reload_user(settings: Settings) -> Settings:
    """state.json 이 갱신된 후 settings 의 user 부분만 다시 읽어와 반환."""
    return settings.model_copy(update={"user": load_state()})
