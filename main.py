"""Jarvis 진입점.

기본은 pywebview 네이티브 창. macOS WebKit 으로 자체 윈도우가 뜬다.
브라우저 사용 안 함.

사용:
    python main.py                  # 네이티브 창
    python main.py --browser        # 기본 브라우저로 대체
    python main.py --no-window      # 창/브라우저 없이 서버만 (헤드리스)
    python main.py --port 9999
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from jarvis.config import load_settings


def _wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    """uvicorn 이 LISTEN 상태로 올라올 때까지 대기."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _build_server(host: str, port: int) -> uvicorn.Server:
    """별도 스레드에서 돌릴 uvicorn 서버 인스턴스 생성.

    Server.install_signal_handlers 는 메인 스레드에서만 동작하므로 다른
    스레드에서 server.run() 호출 시 자동으로 스킵된다. 별도 처리 불필요.
    """
    config = uvicorn.Config(
        app="jarvis.server:app",
        host=host,
        port=port,
        log_level="info",
    )
    return uvicorn.Server(config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis - HUD UI 비서")
    parser.add_argument("--config", default="config.yaml", help="설정 파일")
    parser.add_argument("--host", default=None, help="바인드 호스트 override")
    parser.add_argument("--port", type=int, default=None, help="포트 override")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="네이티브 창 대신 시스템 기본 브라우저로 열기",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="창/브라우저 모두 띄우지 않고 서버만 (헤드리스)",
    )
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    host = args.host or settings.server.host
    port = args.port or settings.server.port

    display_host = host if host != "0.0.0.0" else "localhost"
    url = f"http://{display_host}:{port}"
    print(f"\nJARVIS booting at {url}\n")

    # 헤드리스: 서버만 메인 스레드에서 실행
    if args.no_window:
        uvicorn.run("jarvis.server:app", host=host, port=port, log_level="info")
        return 0

    # 서버는 백그라운드 스레드. 메인 스레드는 창 관리.
    server = _build_server(host, port)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    if not _wait_for_server(display_host, port, timeout=15.0):
        print("서버가 시간 안에 응답하지 않았습니다.", file=sys.stderr)
        return 1

    # --browser: 기존 동작 유지 (시스템 기본 브라우저)
    if args.browser:
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print()
        return 0

    # 기본 — pywebview 네이티브 창
    try:
        import webview  # noqa: PLC0415
    except ImportError:
        print(
            "pywebview 가 설치돼있지 않습니다. `pip install pywebview` 후 다시 시도하거나\n"
            "`python main.py --browser` 로 브라우저 모드로 실행하세요.",
            file=sys.stderr,
        )
        return 1

    webview.create_window(
        "JARVIS",
        url,
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#000308",
    )
    # 창 닫힐 때까지 블록. 닫히면 server 도 정리.
    try:
        webview.start()
    finally:
        server.should_exit = True
        server_thread.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
