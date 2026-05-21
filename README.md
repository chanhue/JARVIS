# Jarvis 🤖

아이언맨의 J.A.R.V.I.S.에서 영감을 받은 개인용 AI 음성 비서 + 데스크탑 컨트롤러.
**macOS** 환경에서 동작하며, 브라우저에서 영화 같은 HUD UI로 조작합니다.
여러 LLM(Anthropic Claude / OpenAI GPT / 로컬 Ollama)을 셋업 모달에서 바로 전환할 수 있습니다.

## ✨ 핵심 기능

- 🪟 **로컬 웹 앱 UI**: `python main.py` 하나로 서버 + 브라우저 자동 오픈, 아크 리액터 풍 HUD
- 🪪 **온보딩 셋업**: 첫 실행 시 UI에서 이름 / AI 종류 / API 키 입력 → `~/.jarvis/state.json` 저장 (`.env` 불필요)
- 🗣 **웨이크워드**: "Jarvis" 또는 "자비스" 둘 다 인식 (`faster-whisper tiny` 연속 청크 인식)
- 🎙 **STT**: `faster-whisper`, 한국어/영어 자동 감지
- 🔊 **TTS**: `edge-tts` — 영어는 `en-GB-RyanNeural` (Jarvis 분위기), 한국어는 `ko-KR-InJoonNeural`
- 🧠 **LLM 플러그블**: Anthropic / OpenAI / Ollama 공통 인터페이스
- 🛠 **스킬 시스템**: 앱 실행 / 시간 / 볼륨 / 스크린샷 / URL 열기 (LLM tool calling 자동 라우팅)
- 📡 **WebSocket**: 상태(STANDBY/LISTENING/THINKING/SPEAKING)와 자막 실시간 UI 반영

## 📦 프로젝트 구조

```
jarvis/
├── main.py                       # 진입점 — uvicorn 띄우고 브라우저 오픈
├── config.yaml                   # 음성/모델/서버 등 비-비밀 설정
├── requirements.txt
└── jarvis/
    ├── state.py                  # ~/.jarvis/state.json 관리 (사용자/키)
    ├── config.py                 # state + yaml 합쳐 Settings 만듦
    ├── core.py                   # 대화 루프 + tool 호출 오케스트레이터
    ├── server.py                 # FastAPI + WebSocket + 백그라운드 음성 루프
    ├── llm/                      # 공통 인터페이스 + 3개 provider + factory
    ├── speech/
    │   ├── stt.py                # faster-whisper, (text, lang) 반환
    │   ├── tts.py                # edge-tts + 언어별 보이스 + 폴백
    │   └── wake.py               # 연속 청크 → "jarvis"/"자비스" 감지
    ├── skills/                   # get_time / set_volume / screenshot / open_app / open_url
    └── web/                      # 정적 UI
        ├── index.html
        ├── style.css             # 아크 리액터 + 글래스 패널
        └── app.js                # WS 클라이언트 + 셋업 폼
```

## 🚀 설치 & 실행

> 현재는 **macOS 전용**입니다. 다른 OS 는 일부 스킬(`open`, `osascript`, `screencapture`, `afplay`)이 동작하지 않습니다.

### 사전 요구사항

- Python 3.10 이상 (`python3 --version` 으로 확인)
- [Homebrew](https://brew.sh) — `portaudio` 설치용

### 1) 시스템 라이브러리

```bash
brew install portaudio        # 마이크 입출력 (sounddevice 의존성)
```

### 2) 프로젝트 디렉토리로 이동

이미 `git clone` 해서 받았다면 그 디렉토리로 이동합니다.

```bash
cd jarvis                     # clone 한 폴더 이름
```

### 3) 가상환경 + 의존성 설치 (최초 1회)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4) 실행

```bash
source .venv/bin/activate     # 새 터미널이면 매번 활성화 필요
python main.py
```

- 브라우저가 자동으로 `http://localhost:8765` 를 엽니다.
- **첫 실행**: UI 모달에서 이름 / AI 종류 / API 키 입력 후 INITIALIZE
- macOS 가 **마이크 권한**을 묻는 다이얼로그를 한 번 띄웁니다 → 허용
- 이후엔 **"Jarvis"** 또는 **"자비스"** 라고 부르면 깨어납니다

### 옵션

```bash
python main.py --no-browser   # 브라우저 자동 오픈 끄기
python main.py --port 9999    # 포트 바꾸기
python main.py --host 0.0.0.0 # 같은 네트워크의 다른 기기에서 접속 허용
```

## 🪪 설정 저장 위치

- 사용자/AI/API 키: `~/.jarvis/state.json` (퍼미션 600)
- 음성/모델/서버 옵션: 프로젝트 루트의 `config.yaml`

`.env` 는 더 이상 사용하지 않습니다. AI 또는 키를 바꾸려면:
- UI 상단 셋업 모달을 다시 띄우거나
- `~/.jarvis/state.json` 을 직접 편집하거나
- 파일을 삭제하면 다음 실행 시 셋업 모달이 다시 뜹니다

## 🛠 스킬 추가하기

`jarvis/skills/` 아래 `Skill` 을 상속한 클래스를 만들고 `jarvis/skills/__init__.py` 의 `default_registry()` 에 등록하세요. LLM 이 알아서 tool calling 으로 호출합니다.

```python
# jarvis/skills/my_skill.py
from .base import Skill

class HelloSkill(Skill):
    name = "say_hello"
    description = "사용자에게 인사를 건넵니다"
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    def run(self, name: str) -> str:
        return f"안녕하세요, {name}님!"
```

## 📚 사용한 오픈소스

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — STT / 웨이크워드
- [edge-tts](https://github.com/rany2/edge-tts) — TTS
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python), [OpenAI SDK](https://github.com/openai/openai-python), [Ollama Python](https://github.com/ollama/ollama-python)
- [FastAPI](https://github.com/fastapi/fastapi) + [uvicorn](https://github.com/encode/uvicorn) — 웹 서버
- [pyautogui](https://github.com/asweigart/pyautogui) — 데스크탑 제어

## 📝 라이선스

MIT
