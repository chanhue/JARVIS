"""Jarvis 진입점.

서버를 띄우고 localhost UI를 브라우저로 연다.
첫 실행이면 UI에 셋업 모달이 떠서 사용자 이름/AI/API 키를 받는다.

사용:
    python main.py                  # 기본 호스트/포트 (config.yaml > server.*)
    python main.py --no-browser     # 브라우저 자동 오픈 비활성
    python main.py --port 9999
"""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn

from jarvis.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis - HUD UI 비서")
    parser.add_argument("--config", default="config.yaml", help="설정 파일")
    parser.add_argument("--host", default=None, help="바인드 호스트 override")
    parser.add_argument("--port", type=int, default=None, help="포트 override")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 오픈 끄기")
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    host = args.host or settings.server.host
    port = args.port or settings.server.port
    open_browser = settings.server.open_browser and not args.no_browser

    url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
    print(f"\nJARVIS booting at {url}\n")

    if open_browser:
        def _open():
            time.sleep(1.0)  # 서버가 LISTEN 들어갈 시간
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("jarvis.server:app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
