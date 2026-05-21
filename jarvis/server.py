"""Jarvis FastAPI 서버.

- 정적 UI (jarvis/web/) 호스팅
- 셋업 안 되어 있으면 모달 띄우라고 알려주는 GET /api/state
- POST /api/setup 으로 state.json 저장
- WebSocket /ws 로 실시간 상태/자막 푸시
- 백그라운드 스레드에서 웨이크워드 → STT → LLM → TTS 루프 돌림
"""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Settings, load_settings, reload_user
from .core import Jarvis
from .speech import Speaker, SpeechRecognizer, WakeWordListener
from .state import STATE_FILE, UserState, load_state, save_state


WEB_DIR = Path(__file__).parent / "web"


class SetupPayload(BaseModel):
    user_name: str
    provider: str
    api_key: str = ""
    model: str | None = None
    ollama_host: str | None = None


class Hub:
    """WebSocket 브로드캐스터 + 워커 루프 진입.

    UI 가 보는 상태:
      - state: standby / listening / thinking / speaking / error
      - transcript: {role: 'user'|'assistant', text, lang?}
      - log: 디버그 메시지
    """

    def __init__(self) -> None:
        self.settings: Settings = load_settings()
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake_event = threading.Event()
        self._jarvis: Jarvis | None = None
        self._stt: SpeechRecognizer | None = None
        self._tts: Speaker | None = None
        self._wake_listener: WakeWordListener | None = None

    # ---------- WS bookkeeping ----------

    async def register(self, ws: WebSocket) -> None:
        self.clients.add(ws)
        await ws.send_json({"type": "state", "value": self._current_state})
        await ws.send_json(
            {
                "type": "user",
                "name": self.settings.user.user_name,
                "provider": self.settings.user.provider,
            }
        )

    def unregister(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def push(self, message: dict[str, Any]) -> None:
        """워커 스레드에서 비동기 브로드캐스트 호출."""
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    # ---------- lifecycle ----------

    _current_state: str = "needs-setup"

    def set_state(self, value: str) -> None:
        self._current_state = value
        self.push({"type": "state", "value": value})

    def _build_jarvis(self) -> bool:
        """state 를 다시 읽어 Jarvis 인스턴스를 만들고 self._jarvis 에 저장.

        성공하면 True. 셋업 미완이면 False (state=needs-setup).
        """
        self.settings = reload_user(self.settings)
        if not self.settings.user.is_complete():
            self.set_state("needs-setup")
            return False
        try:
            self._jarvis = Jarvis(self.settings)
        except RuntimeError as e:
            self.push({"type": "log", "text": f"초기화 실패: {e}"})
            self.set_state("error")
            return False
        # UI 의 칩 갱신
        self.push(
            {
                "type": "user",
                "name": self.settings.user.user_name,
                "provider": self.settings.user.provider,
            }
        )
        return True

    def start_worker_if_ready(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        if not self._build_jarvis():
            return

        self._stt = SpeechRecognizer(self.settings.stt, language="auto")
        self._tts = Speaker(self.settings.tts)
        self._wake_listener = WakeWordListener(self.settings.wake, on_wake=self._on_wake)

        self._stop.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._wake_listener.start()
        self.set_state("standby")

    def reload(self) -> None:
        """provider/키/모델 변경 후 호출. 워커 중이면 Jarvis 만 핫스왑."""
        if self._worker and self._worker.is_alive():
            if self._build_jarvis():
                self.push({"type": "log", "text": "설정이 갱신되었습니다."})
        else:
            self.start_worker_if_ready()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake_event.set()
        if self._wake_listener:
            self._wake_listener.stop()

    # ---------- worker ----------

    def _on_wake(self) -> None:
        self._wake_event.set()

    def _worker_loop(self) -> None:
        assert self._stt and self._tts and self._jarvis and self._wake_listener
        # 환영 인사 (영문 분위기)
        name = self.settings.user.user_name or ""
        greeting = f"At your service, {name}." if name else "At your service."
        self.set_state("speaking")
        self.push({"type": "transcript", "role": "assistant", "text": greeting, "lang": "en"})
        self._tts.say(greeting, language="en")
        self.set_state("standby")

        while not self._stop.is_set():
            # 웨이크워드 대기
            self._wake_event.wait()
            self._wake_event.clear()
            if self._stop.is_set():
                break

            # 웨이크워드 감지 중에는 일시정지 (마이크 점유 충돌 방지)
            self._wake_listener.pause()
            try:
                self.set_state("listening")
                heard = self._stt.listen_once()
                if not heard:
                    self.push({"type": "log", "text": "들은 게 없어요."})
                    self.set_state("standby")
                    continue
                user_text, lang = heard
                self.push(
                    {"type": "transcript", "role": "user", "text": user_text, "lang": lang}
                )

                self.set_state("thinking")
                reply = self._jarvis.respond(user_text)

                self.set_state("speaking")
                self.push(
                    {
                        "type": "transcript",
                        "role": "assistant",
                        "text": reply,
                        "lang": lang,
                    }
                )
                self._tts.say(reply, language=lang)
            except Exception as e:  # noqa: BLE001
                self.push({"type": "log", "text": f"에러: {e}"})
            finally:
                self.set_state("standby")
                self._wake_listener.resume()


hub = Hub()


@asynccontextmanager
async def lifespan(_: FastAPI):
    hub.loop = asyncio.get_running_loop()
    # 셋업이 이미 끝나있으면 즉시 워커 시작
    hub.start_worker_if_ready()
    try:
        yield
    finally:
        hub.shutdown()


app = FastAPI(lifespan=lifespan)


# ---------- HTTP ----------

@app.get("/api/state")
def api_state() -> JSONResponse:
    state = load_state()
    return JSONResponse(
        {
            "setup_complete": state.is_complete(),
            "user_name": state.user_name,
            "provider": state.provider,
            "have_keys": {
                "anthropic": bool(state.anthropic_api_key),
                "openai": bool(state.openai_api_key),
                "ollama": True,  # 키 불필요
                "gemini": bool(state.gemini_api_key),
            },
            "models": {
                "anthropic": state.anthropic_model,
                "openai": state.openai_model,
                "ollama": state.ollama_model,
                "gemini": state.gemini_model,
            },
            "ollama_host": state.ollama_host,
            "runtime_state": hub._current_state,
            "state_file": str(STATE_FILE),
        }
    )


@app.post("/api/setup")
def api_setup(payload: SetupPayload) -> JSONResponse:
    """초기 셋업 + 사후 설정 변경 모두 처리.

    api_key 가 비어있으면 해당 provider 의 기존 키를 그대로 둔다 (UX: 키를 다시
    안 쳐도 이름/모델만 바꿀 수 있도록).
    """
    if payload.provider not in {"anthropic", "openai", "ollama", "gemini"}:
        return JSONResponse({"ok": False, "error": "알 수 없는 provider"}, status_code=400)
    if not payload.user_name.strip():
        return JSONResponse({"ok": False, "error": "이름이 비어있어요"}, status_code=400)

    state = load_state()
    state = state.model_copy(
        update={"user_name": payload.user_name.strip(), "provider": payload.provider}
    )
    api_key = payload.api_key.strip() if payload.api_key else ""

    if payload.provider == "anthropic":
        if not api_key and not state.anthropic_api_key:
            return JSONResponse({"ok": False, "error": "API 키가 필요해요"}, status_code=400)
        update: dict = {}
        if api_key:
            update["anthropic_api_key"] = api_key
        if payload.model:
            update["anthropic_model"] = payload.model
        state = state.model_copy(update=update)

    elif payload.provider == "openai":
        if not api_key and not state.openai_api_key:
            return JSONResponse({"ok": False, "error": "API 키가 필요해요"}, status_code=400)
        update = {}
        if api_key:
            update["openai_api_key"] = api_key
        if payload.model:
            update["openai_model"] = payload.model
        state = state.model_copy(update=update)

    elif payload.provider == "ollama":
        update = {}
        if payload.ollama_host:
            update["ollama_host"] = payload.ollama_host
        if payload.model:
            update["ollama_model"] = payload.model
        state = state.model_copy(update=update)

    elif payload.provider == "gemini":
        if not api_key and not state.gemini_api_key:
            return JSONResponse({"ok": False, "error": "API 키가 필요해요"}, status_code=400)
        update = {}
        if api_key:
            update["gemini_api_key"] = api_key
        if payload.model:
            update["gemini_model"] = payload.model
        state = state.model_copy(update=update)

    save_state(state)
    hub.reload()
    return JSONResponse({"ok": True})


# ---------- WS ----------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    await hub.register(ws)
    try:
        while True:
            # 클라가 보내는 메시지(현재는 ping 정도)
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(ws)


# ---------- 정적 파일 ----------

# /static/* 는 그대로, 루트는 index.html
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def root_index() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))
