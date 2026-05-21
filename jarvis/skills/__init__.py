from ..calendar import EventStore
from .apps import OpenAppSkill, OpenURLSkill
from .base import Skill, SkillRegistry
from .calendar import CreateEventSkill, DeleteEventSkill, ListEventsSkill
from .system import GetTimeSkill, ScreenshotSkill, SetVolumeSkill


def default_registry() -> SkillRegistry:
    reg = SkillRegistry()
    # 시스템
    reg.register(GetTimeSkill())
    reg.register(SetVolumeSkill())
    reg.register(ScreenshotSkill())
    # 앱
    reg.register(OpenAppSkill())
    reg.register(OpenURLSkill())
    # 캘린더 (로컬 저장)
    store = EventStore()
    reg.register(CreateEventSkill(store))
    reg.register(ListEventsSkill(store))
    reg.register(DeleteEventSkill(store))
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
    "CreateEventSkill",
    "ListEventsSkill",
    "DeleteEventSkill",
]
