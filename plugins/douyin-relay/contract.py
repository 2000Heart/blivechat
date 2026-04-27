# -*- coding: utf-8 -*-
"""
douyin-relay 数据契约定义。

目标：
- 冻结 UnifiedEvent 顶层字段与空值语义。
- 明确 platform_meta 需按平台区分，避免跨平台字段误用。
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict, Union


class UnifiedActor(TypedDict):
    id: str
    name: str
    avatar_url: str


class UnifiedContent(TypedDict, total=False):
    text: str


class UnifiedMonetization(TypedDict, total=False):
    amount: int
    currency: str
    gift_name: str
    gift_count: int
    gift_id: str
    gift_icon_url: str


class UnifiedFanIdentity(TypedDict, total=False):
    level: int
    badge_name: str


class BilibiliPlatformMeta(TypedDict, total=False):
    platform: Literal['bilibili']
    medal_name: Optional[str]
    medal_level: Optional[int]


class DouyinPlatformMeta(TypedDict, total=False):
    platform: Literal['douyin']
    room_id: str
    room_num: str
    membership_type: Optional[str]
    membership_name: Optional[str]
    fans_badge_level: Optional[int]
    fans_badge_name: Optional[str]


PlatformMeta = Union[BilibiliPlatformMeta, DouyinPlatformMeta]


class UnifiedEvent(TypedDict):
    event_id: str
    platform: Literal['bilibili', 'douyin']
    event_type: str
    ts: int
    actor: UnifiedActor
    content: Optional[UnifiedContent]
    monetization: Optional[UnifiedMonetization]
    fan_identity: Optional[UnifiedFanIdentity]
    platform_meta: PlatformMeta
