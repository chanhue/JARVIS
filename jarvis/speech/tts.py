from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile

import edge_tts

from ..config import TTSConfig


class Speaker:
    """Text-to-speech via edge-tts with pyttsx3 (or `say`) fallback.

    Picks the voice based on the language code passed in. Falls back to the
    configured `default_lang` voice if there's no exact match.
    """

    def __init__(self, cfg: TTSConfig) -> None:
        self.cfg = cfg
        self._pyttsx3_engine = None

    def say(self, text: str, language: str | None = None) -> None:
        text = text.strip()
        if not text:
            return
        voice = self._pick_voice(language)
        try:
            asyncio.run(self._say_edge(text, voice))
            return
        except Exception as e:  # noqa: BLE001
            if not self.cfg.offline_fallback:
                raise
            print(f"[TTS] edge-tts 실패, 폴백 사용: {e}", file=sys.stderr)
            self._say_offline(text)

    def _pick_voice(self, language: str | None) -> str:
        voices = self.cfg.voices
        if language and language in voices:
            return voices[language]
        if self.cfg.default_lang in voices:
            return voices[self.cfg.default_lang]
        # 마지막 안전망: 사전에서 아무거나
        return next(iter(voices.values()))

    async def _say_edge(self, text: str, voice: str) -> None:
        communicate = edge_tts.Communicate(
            text,
            voice=voice,
            rate=self.cfg.rate,
            volume=self.cfg.volume,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        try:
            await communicate.save(tmp_path)
            self._play_audio_file(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _play_audio_file(self, path: str) -> None:
        # macOS native player — present on every Mac, no extra deps.
        subprocess.run(["afplay", path], check=False)

    def _say_offline(self, text: str) -> None:
        # First try pyttsx3 (cross-platform), else fall back to macOS `say`.
        try:
            import pyttsx3

            if self._pyttsx3_engine is None:
                self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()
        except Exception:  # noqa: BLE001
            subprocess.run(["say", text], check=False)
