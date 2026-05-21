from .apps import OpenAppSkill, OpenURLSkill
from .base import Skill, SkillRegistry
from .system import GetTimeSkill, ScreenshotSkill, SetVolumeSkill


def default_registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(GetTimeSkill())
    reg.register(SetVolumeSkill())
    reg.register(ScreenshotSkill())
    reg.register(OpenAppSkill())
    reg.register(OpenURLSkill())
    return reg


__all__ = [
    "Skill",
    "SkillRegistry",
    "default_registry",
    "GetTimeSkill",
    "SetVolumeSkill",
    "ScreenshotSkill",
    "OpenAppSkill",
    "OpenURLSkill",
]
