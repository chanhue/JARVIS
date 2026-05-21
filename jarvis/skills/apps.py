from __future__ import annotations

import subprocess

from .base import Skill


class OpenAppSkill(Skill):
    name = "open_app"
    description = (
        "macOS 응용 프로그램을 실행한다. app_name 은 'Safari', 'Visual Studio Code' 처럼 표시 이름."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "실행할 macOS 앱 이름",
            }
        },
        "required": ["app_name"],
    }

    def run(self, app_name: str) -> str:
        result = subprocess.run(
            ["open", "-a", app_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return f"앱을 열지 못했어요: {result.stderr.strip() or app_name}"
        return f"{app_name} 실행했어요."


class OpenURLSkill(Skill):
    name = "open_url"
    description = "기본 브라우저로 URL을 연다."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "열고 싶은 URL"}
        },
        "required": ["url"],
    }

    def run(self, url: str) -> str:
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        subprocess.run(["open", url], check=False)
        return f"브라우저에서 {url} 열었어요."
