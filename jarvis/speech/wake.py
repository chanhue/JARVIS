"""웨이크워드 감지기.

마이크에서 N초짜리 청크를 계속 떠서 whisper-tiny 로 빠르게 인식, 텍스트에
"jarvis" 또는 "자비스"(혹은 설정된 키워드)가 들어있으면 콜백 호출.

장점: 외부 키 불필요. 단점: 항상 CPU 약간 먹음. 더 효율적인 wake가 필요하면
Picovoice Porcupine 으로 갈아끼우는 게 좋다.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from ..config import WakeConfig


class WakeWordListener:
    def __init__(self, cfg: WakeConfig, on_wake: Callable[[str], None]) -> None:
        """on_wake 는 매칭된 키워드(예: "자비스" 또는 "jarvis")를 인자로 받는다.
        키워드 별로 응답 언어를 고를 수 있도록 시그니처를 확장."""
        self.cfg = cfg
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._model: Optional[WhisperModel] = None
        self._keywords_lower = [k.lower() for k in cfg.keywords]

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def pause(self) -> None:
        """active listening 중에는 웨이크 감지 끄기."""
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(self.cfg.model, device="cpu", compute_type="int8")
        return self._model

    def _run(self) -> None:
        sr = self.cfg.samplerate
        chunk_samples = int(sr * self.cfg.chunk_seconds)
        block_size = int(sr * 0.1)  # 100ms blocks for the callback
        q: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            q.put(indata.copy())

        model = self._ensure_model()

        with sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            callback=callback,
        ):
            buffer = np.zeros((0, 1), dtype=np.float32)
            while not self._stop.is_set():
                try:
                    chunk = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                buffer = np.concatenate([buffer, chunk], axis=0)
                # 청크 크기 만큼 모이면 인식 시도
                if len(buffer) >= chunk_samples:
                    audio = buffer[:chunk_samples].flatten().astype(np.float32)
                    # 슬라이딩: 절반 겹치게 다음으로 넘김
                    buffer = buffer[chunk_samples // 2 :]

                    if self._paused.is_set():
                        continue

                    rms = float(np.sqrt(np.mean(audio**2)))
                    if rms < self.cfg.silence_threshold:
                        continue

                    matched = self._matched_keyword(model, audio)
                    if matched:
                        try:
                            self.on_wake(matched)
                        except Exception as e:  # noqa: BLE001
                            print(f"[wake] on_wake 콜백 에러: {e}")
                        # 연속 트리거 방지 (방금 깨어났으니 잠깐 쉼)
                        time.sleep(0.5)

    def _matched_keyword(self, model: WhisperModel, audio: np.ndarray) -> Optional[str]:
        try:
            segments, _ = model.transcribe(
                audio,
                language=None,
                vad_filter=False,
                beam_size=1,
                no_speech_threshold=0.5,
            )
            text = "".join(seg.text for seg in segments).lower()
        except Exception:  # noqa: BLE001
            return None
        for kw in self._keywords_lower:
            if kw in text:
                return kw
        return None
