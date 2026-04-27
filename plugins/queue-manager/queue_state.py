# -*- coding: utf-8 -*-
from __future__ import annotations

import dataclasses
import time
from typing import Any

import blcsdk.models as sdk_models

QUEUE_KEYWORD = "排队"


@dataclasses.dataclass
class QueueEntry:
    user_key: str
    uid: str
    author_name: str
    avatar_url: str
    join_timestamp: int
    gift_total_value: int = 0
    gift_count: int = 0
    last_gift_timestamp: int = 0
    guard_level: int = 0
    medal_level: int = 0
    medal_name: str = ""

    def to_dict(self, rank: int) -> dict[str, Any]:
        return {
            "rank": rank,
            "userKey": self.user_key,
            "uid": self.uid,
            "authorName": self.author_name,
            "avatarUrl": self.avatar_url,
            "joinTimestamp": self.join_timestamp,
            "giftTotalValue": self.gift_total_value,
            "giftCount": self.gift_count,
            "lastGiftTimestamp": self.last_gift_timestamp,
            "guardLevel": self.guard_level,
            "medalLevel": self.medal_level,
            "medalName": self.medal_name,
        }


@dataclasses.dataclass
class RoomQueue:
    room_key_str: str
    entries: dict[str, QueueEntry] = dataclasses.field(default_factory=dict)
    version: int = 0
    updated_at: int = 0

    def sorted_entries(self) -> list[QueueEntry]:
        return sorted(
            self.entries.values(),
            key=lambda e: (-e.gift_total_value, e.join_timestamp, e.user_key),
        )


def room_key_to_str(room_key: sdk_models.RoomKey | None) -> str:
    if room_key is None:
        return "all"
    return f"{int(room_key.type)}:{room_key.value}"


class QueueState:
    def __init__(self) -> None:
        self._rooms: dict[str, RoomQueue] = {}

    def _get_room(self, room_key_str: str) -> RoomQueue:
        room = self._rooms.get(room_key_str)
        if room is None:
            room = RoomQueue(room_key_str=room_key_str)
            self._rooms[room_key_str] = room
        return room

    def room_keys(self) -> list[str]:
        return sorted(self._rooms.keys())

    def enqueue(
        self,
        room_key_str: str,
        user_key: str,
        uid: str,
        author_name: str,
        avatar_url: str,
        join_ts: int | None = None,
        guard_level: int = 0,
        medal_level: int = 0,
        medal_name: str = "",
        max_queue_size: int = 200,
    ) -> bool:
        room = self._get_room(room_key_str)
        if user_key in room.entries:
            return False
        if len(room.entries) >= max_queue_size:
            return False
        ts = int(time.time()) if join_ts is None else int(join_ts)
        room.entries[user_key] = QueueEntry(
            user_key=user_key,
            uid=uid,
            author_name=author_name,
            avatar_url=avatar_url,
            join_timestamp=ts,
            guard_level=guard_level,
            medal_level=medal_level,
            medal_name=medal_name,
        )
        self._touch(room)
        return True

    def add_gift(self, room_key_str: str, user_key: str, value: int, ts: int | None = None) -> bool:
        room = self._rooms.get(room_key_str)
        if room is None:
            return False
        entry = room.entries.get(user_key)
        if entry is None:
            return False
        entry.gift_total_value += max(0, int(value))
        entry.gift_count += 1
        entry.last_gift_timestamp = int(time.time()) if ts is None else int(ts)
        self._touch(room)
        return True

    def pass_next(self, room_key_str: str) -> dict[str, Any] | None:
        room = self._rooms.get(room_key_str)
        if room is None or not room.entries:
            return None
        first = room.sorted_entries()[0]
        room.entries.pop(first.user_key, None)
        self._touch(room)
        return first.to_dict(rank=1)

    def remove_user(self, room_key_str: str, user_key: str) -> bool:
        room = self._rooms.get(room_key_str)
        if room is None:
            return False
        existed = room.entries.pop(user_key, None) is not None
        if existed:
            self._touch(room)
        return existed

    def snapshot(self, room_key_str: str) -> dict[str, Any]:
        room = self._get_room(room_key_str)
        items = [entry.to_dict(idx) for idx, entry in enumerate(room.sorted_entries(), start=1)]
        return {
            "roomKey": room_key_str,
            "version": room.version,
            "updatedAt": room.updated_at,
            "size": len(items),
            "items": items,
        }

    def _touch(self, room: RoomQueue) -> None:
        room.version += 1
        room.updated_at = int(time.time())


def is_queue_keyword(content: str) -> bool:
    return content.strip() == QUEUE_KEYWORD


if __name__ == "__main__":
    qs = QueueState()
    qs.enqueue(room_key_str="1:100", user_key="u1", uid="u1", author_name="A", avatar_url="", join_ts=1)
    qs.enqueue(room_key_str="1:100", user_key="u2", uid="u2", author_name="B", avatar_url="", join_ts=2)
    qs.add_gift(room_key_str="1:100", user_key="u2", value=100)
    assert qs.snapshot("1:100")["items"][0]["userKey"] == "u2"
    print("queue_state self-check passed")
