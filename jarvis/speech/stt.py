from __future__ import annotations

import queue
import time
from typing import Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from ..config import STTConfig


class SpeechRecognizer:
    """Mic-driven STT using faster-whisper.

    Records from default input device, ends when silence persists for
    `silence_duration` seconds OR after `max_record_seconds`. Then runs
    faster-whisper on the buffer. Returns (text, detected_language).
    """

    def __init__(self, cfg: STTConfig, language: str = "auto") -> None:
        self.cfg = cfg
        # "auto" → None → Whisper가 발화별로 자동 감지
        self.language: Optional[str] = None if language == "auto" else language
        device = cfg.device
        if device == "auto":
            device = "cpu"
        self.model = WhisperModel(cfg.model, device=device, compute_type=cfg.compute_type)

    def listen_once(self) -> Optional[tuple[str, str]]:
        """Block until a single utterance is captured, then transcribe.

        Returns (text, language_code) — language_code is the ISO code Whisper
        detected (e.g. "ko", "en"). Returns None if nothing audible.
        """
        audio = self._record_until_silence()
        if audio is None or len(audio) < self.cfg.samplerate // 2:
            return None
        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=1,
        )
        text = "".join(seg.text for seg in segments).strip()
        if not text:
            return None
        lang = info.language or (self.language or "en")
        return text, lang

    def _record_until_silence(self) -> np.ndarray | None:
        sr = self.cfg.samplerate
        block_size = int(sr * 0.05)  # 50 ms blocks
        q: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            q.put(indata.copy())

        frames: list[np.ndarray] = []
        silence_seconds = 0.0
        speech_started = False
        deadline = time.monotonic() + self.cfg.max_record_seconds

        with sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            callback=callback,
        ):
            while time.monotonic() < deadline:
                try:
                    chunk = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                frames.append(chunk)
                rms = float(np.sqrt(np.mean(chunk**2)))
                if rms >= self.cfg.silence_threshold:
                    speech_started = True
                    silence_seconds = 0.0
                else:
                    silence_seconds += len(chunk) / sr
                    if speech_started and silence_seconds >= self.cfg.silence_duration:
                        break

        if not speech_started or not frames:
            return None
        audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
        return audio
