from __future__ import annotations

import dataclasses
import time
from typing import Dict, List, Optional


def now_ts() -> int:
    return int(time.time())


@dataclasses.dataclass
class QueueConfig:
    min_medal_level: int = 0
    join_keyword: str = "排队"
    cancel_keyword: str = "取消排队"
    reset_queue_time_on_unpass: bool = True
    board_color: str = "#000000"
    board_opacity: float = 0.0
    board_radius: int = 0
    item_color: str = "#000000"
    item_opacity: float = 0.5
    item_radius: int = 10
    banner_text: str = ""
    banner_font_size: int = 15


@dataclasses.dataclass
class QueueUser:
    uid: str
    name: str
    avatar_url: str
    medal_level: int
    queued_at: int
    gift_value_coin: int = 0
    manual_adjusted: bool = False
    passed_at: Optional[int] = None
    called_at: Optional[int] = None

    @property
    def is_passed(self) -> bool:
        return self.passed_at is not None


class QueueEngine:
    def __init__(self, cfg: Optional[QueueConfig] = None):
        self.cfg = cfg or QueueConfig()
        self._users: Dict[str, QueueUser] = {}
        self._manual_calling_uid: Optional[str] = None

    def export_state(self) -> dict:
        return {
            "config": dataclasses.asdict(self.cfg),
            "manual_calling_uid": self._manual_calling_uid,
            "users": [dataclasses.asdict(u) for u in self._users.values()],
        }

    def load_state(self, data: dict) -> None:
        cfg = data.get("config", {})
        self.cfg = QueueConfig(
            min_medal_level=int(cfg.get("min_medal_level", 0)),
            join_keyword=str(cfg.get("join_keyword", "排队")),
            cancel_keyword=str(cfg.get("cancel_keyword", "取消排队")),
            reset_queue_time_on_unpass=bool(cfg.get("reset_queue_time_on_unpass", True)),
            board_color=str(cfg.get("board_color", "#000000")),
            board_opacity=float(cfg.get("board_opacity", 0.0)),
            board_radius=max(0, int(cfg.get("board_radius", 0))),
            item_color=str(cfg.get("item_color", "#000000")),
            item_opacity=float(cfg.get("item_opacity", 0.5)),
            item_radius=max(0, int(cfg.get("item_radius", 10))),
            banner_text=str(cfg.get("banner_text", ""))[:200],
            banner_font_size=max(12, min(64, int(cfg.get("banner_font_size", 15)))),
        )
        manual_calling_uid = data.get("manual_calling_uid")
        self._manual_calling_uid = str(manual_calling_uid) if manual_calling_uid else None
        self._users.clear()
        for row in data.get("users", []):
            uid = str(row.get("uid", "")).strip()
            if not uid:
                continue
            self._users[uid] = QueueUser(
                uid=uid,
                name=str(row.get("name", "")),
                avatar_url=str(row.get("avatar_url", "")),
                medal_level=int(row.get("medal_level", 0)),
                queued_at=int(row.get("queued_at", now_ts())),
                gift_value_coin=int(row.get("gift_value_coin", 0)),
                manual_adjusted=bool(row.get("manual_adjusted", False)),
                passed_at=row.get("passed_at"),
                called_at=row.get("called_at"),
            )

    def join_queue(self, *, uid: str, name: str, avatar_url: str, medal_level: int) -> bool:
        if medal_level < self.cfg.min_medal_level:
            return False
        uid = uid.strip()
        if not uid:
            return False
        existed = self._users.get(uid)
        if existed:
            existed.name = name or existed.name
            existed.avatar_url = avatar_url or existed.avatar_url
            existed.medal_level = medal_level
            return True
        self._users[uid] = QueueUser(
            uid=uid,
            name=name or uid,
            avatar_url=avatar_url or "",
            medal_level=medal_level,
            queued_at=now_ts(),
        )
        return True

    def cancel_queue(self, uid: str) -> bool:
        removed = self._users.pop(uid, None) is not None
        if removed and self._manual_calling_uid == uid:
            self._manual_calling_uid = None
        return removed

    def remove_user(self, uid: str) -> bool:
        return self.cancel_queue(uid)

    def clear_queue(self) -> None:
        self._users.clear()
        self._manual_calling_uid = None

    def mark_passed(self, uid: str) -> bool:
        u = self._users.get(uid)
        if not u:
            return False
        u.passed_at = now_ts()
        if self._manual_calling_uid == uid:
            self._manual_calling_uid = None
        return True

    def unmark_passed(self, uid: str) -> bool:
        u = self._users.get(uid)
        if not u:
            return False
        u.passed_at = None
        if self.cfg.reset_queue_time_on_unpass:
            u.queued_at = now_ts()
        return True

    def mark_called(self, uid: str) -> bool:
        u = self._users.get(uid)
        if not u or u.is_passed:
            return False
        u.called_at = now_ts()
        self._manual_calling_uid = uid
        return True

    def set_min_medal_level(self, value: int) -> None:
        self.cfg.min_medal_level = max(0, int(value))

    def set_gift_value_coin(self, uid: str, coin: int, *, manual: bool = True) -> bool:
        u = self._users.get(uid)
        if not u:
            return False
        u.gift_value_coin = max(0, int(coin))
        u.manual_adjusted = manual
        return True

    def add_gift_value_coin(self, uid: str, coin: int) -> bool:
        u = self._users.get(uid)
        if not u:
            return False
        if coin <= 0:
            return False
        u.gift_value_coin += int(coin)
        return True

    def ordered_users(self) -> List[QueueUser]:
        passed = [u for u in self._users.values() if u.is_passed]
        normal = [u for u in self._users.values() if not u.is_passed]
        passed.sort(key=lambda x: (x.passed_at or 0, x.queued_at))
        normal.sort(key=lambda x: (-x.gift_value_coin, x.queued_at))
        return passed + normal

    def calling_user_id(self) -> Optional[str]:
        if self._manual_calling_uid:
            u = self._users.get(self._manual_calling_uid)
            if u is not None and not u.is_passed:
                return self._manual_calling_uid
            self._manual_calling_uid = None
        normal = [u for u in self._users.values() if not u.is_passed]
        if not normal:
            return None
        normal.sort(key=lambda x: (-x.gift_value_coin, x.queued_at))
        return normal[0].uid

    def snapshot(self) -> dict:
        now = now_ts()
        users = []
        for idx, u in enumerate(self.ordered_users(), start=1):
            users.append(
                {
                    "rank": idx,
                    "uid": u.uid,
                    "name": u.name,
                    "avatarUrl": u.avatar_url,
                    "medalLevel": u.medal_level,
                    "queuedAt": u.queued_at,
                    "queuedSeconds": max(0, now - u.queued_at),
                    "giftValueCoin": u.gift_value_coin,
                    "giftValueYuan": round(u.gift_value_coin / 1000.0, 3),
                    "status": "passed" if u.is_passed else "normal",
                    "passedAt": u.passed_at,
                    "calledAt": u.called_at,
                    "manualAdjusted": u.manual_adjusted,
                }
            )
        return {
            "config": dataclasses.asdict(self.cfg),
            "users": users,
            "callingUserId": self.calling_user_id(),
            "updatedAt": now,
        }
