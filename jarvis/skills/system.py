from __future__ import annotations

import datetime as _dt
import os
import subprocess
from pathlib import Path

from .base import Skill


class GetTimeSkill(Skill):
    name = "get_time"
    description = "현재 시각과 날짜를 알려준다."
    parameters = {"type": "object", "properties": {}}

    def run(self) -> str:
        now = _dt.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S (%A)")


class SetVolumeSkill(Skill):
    name = "set_volume"
    description = "macOS 시스템 출력 볼륨을 0-100 사이로 설정한다."
    parameters = {
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "0~100 사이의 볼륨 레벨",
                "minimum": 0,
                "maximum": 100,
            }
        },
        "required": ["level"],
    }

    def run(self, level: int) -> str:
        level = max(0, min(100, int(level)))
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"], check=False
        )
        return f"볼륨을 {level}으로 설정했어요."


class ScreenshotSkill(Skill):
    name = "take_screenshot"
    description = (
        "화면 전체를 캡처해서 ~/Desktop 에 PNG로 저장한다. 저장된 파일 경로를 돌려준다."
    )
    parameters = {"type": "object", "properties": {}}

    def run(self) -> str:
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path.home() / "Desktop" / f"jarvis_screenshot_{ts}.png"
        subprocess.run(["screencapture", "-x", str(out)], check=False)
        return f"스크린샷 저장: {out}"
