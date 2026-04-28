#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import random
import signal
import sys
from typing import Any, Dict, Optional


def _inject_project_root_for_local_packages() -> None:
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "blcsdk")):
            if cur not in sys.path:
                sys.path.append(cur)
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


_inject_project_root_for_local_packages()

import blcsdk

import config
import event_handler
import store
from queue_engine import QueueConfig, QueueEngine
from web_server import QueueWebServer

logger = logging.getLogger("queue-machine")

shut_down_event: Optional[asyncio.Event] = None
_engine: Optional[QueueEngine] = None
_web: Optional[QueueWebServer] = None
_lock: Optional[asyncio.Lock] = None


async def main() -> int:
    try:
        await init()
        await run()
    finally:
        await shut_down()
    return 0


async def init() -> None:
    init_signal_handlers()
    config.init()
    init_logging()

    await blcsdk.init()
    if not blcsdk.is_sdk_version_compatible():
        raise RuntimeError("SDK version is not compatible")

    global _engine, _web, _lock
    cfg = config.get_config()
    _engine = QueueEngine(
        QueueConfig(
            min_medal_level=cfg.min_medal_level,
            join_keyword=cfg.join_keyword,
            cancel_keyword=cfg.cancel_keyword,
            reset_queue_time_on_unpass=cfg.reset_queue_time_on_unpass,
            board_color=cfg.board_color,
            board_opacity=cfg.board_opacity,
            board_radius=cfg.board_radius,
            item_color=cfg.item_color,
            item_opacity=cfg.item_opacity,
            item_radius=cfg.item_radius,
            banner_text=cfg.banner_text,
        )
    )
    _engine.load_state(store.load_state())
    _lock = asyncio.Lock()

    _web = QueueWebServer(get_snapshot=_engine.snapshot, apply_action=handle_admin_action)
    await _web.start(cfg.host, cfg.port)
    event_handler.install(_engine, on_engine_changed)
    await blcsdk.log(f"queue-machine 已启动: http://{cfg.host}:{cfg.port}/admin", logging.INFO)


def init_signal_handlers() -> None:
    global shut_down_event
    shut_down_event = asyncio.Event()
    signums = (signal.SIGINT, signal.SIGTERM)
    try:
        loop = asyncio.get_running_loop()
        for signum in signums:
            loop.add_signal_handler(signum, start_shut_down)
    except NotImplementedError:
        for signum in signums:
            signal.signal(signum, start_shut_down)


def start_shut_down(*_args: Any) -> None:
    if shut_down_event:
        shut_down_event.set()


def init_logging() -> None:
    filename = os.path.join(config.LOG_PATH, "queue-machine.log")
    stream_handler = logging.StreamHandler()
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename, encoding="utf-8", when="midnight", backupCount=7, delay=True
    )
    logging.basicConfig(
        format="{asctime} {levelname} [{name}]: {message}",
        style="{",
        level=logging.INFO,
        handlers=[stream_handler, file_handler],
    )


async def run() -> None:
    await shut_down_event.wait()


async def shut_down() -> None:
    event_handler.uninstall()
    if _engine is not None:
        store.save_state(_engine.export_state())
    if _web is not None:
        await _web.stop()
    await blcsdk.shut_down()


def on_engine_changed() -> None:
    store.save_state(_engine.export_state())
    if _web is not None:
        asyncio.create_task(_web.broadcast_snapshot())


async def handle_admin_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if _engine is None or _web is None or _lock is None:
        return {"ok": False, "error": "not initialized"}
    async with _lock:
        uid = str(payload.get("uid", ""))
        ok = True
        if action == "set_min_medal_level":
            new_value = int(payload.get("value", 0))
            _engine.set_min_medal_level(new_value)
            runtime_cfg = config.get_config()
            runtime_cfg.min_medal_level = max(0, new_value)
            config.save()
        elif action == "mark_passed":
            ok = _engine.mark_passed(uid)
        elif action == "unmark_passed":
            ok = _engine.unmark_passed(uid)
        elif action == "remove_user":
            ok = _engine.remove_user(uid)
        elif action == "call_user":
            ok = _engine.mark_called(uid)
        elif action == "clear_queue":
            _engine.clear_queue()
        elif action == "set_gift_value":
            ok = _engine.set_gift_value_coin(uid, int(payload.get("giftValueCoin", 0)), manual=True)
        elif action == "add_random_users":
            count = max(1, min(100, int(payload.get("count", 1))))
            min_medal = _engine.cfg.min_medal_level
            for _ in range(count):
                rid = random.randint(100000, 999999)
                medal_level = random.randint(min_medal, max(min_medal, 30))
                _engine.join_queue(
                    uid=f"test_{rid}",
                    name=f"测试用户{rid}",
                    avatar_url=f"https://api.dicebear.com/9.x/thumbs/svg?seed={rid}",
                    medal_level=medal_level,
                )
                # 给随机测试用户一些随机礼物值，便于验证排序效果
                _engine.add_gift_value_coin(f"test_{rid}", random.randint(0, 20000))
        elif action == "set_theme":
            board_color = _normalize_hex_color(str(payload.get("boardColor", "#000000")))
            item_color = _normalize_hex_color(str(payload.get("itemColor", "#000000")))
            board_opacity = _clamp_float(payload.get("boardOpacity", 0), 0.0, 1.0)
            item_opacity = _clamp_float(payload.get("itemOpacity", 0.5), 0.0, 1.0)
            board_radius = _clamp_int(payload.get("boardRadius", 0), 0, 80)
            item_radius = _clamp_int(payload.get("itemRadius", 10), 0, 80)
            _engine.cfg.board_color = board_color
            _engine.cfg.board_opacity = board_opacity
            _engine.cfg.board_radius = board_radius
            _engine.cfg.item_color = item_color
            _engine.cfg.item_opacity = item_opacity
            _engine.cfg.item_radius = item_radius

            runtime_cfg = config.get_config()
            runtime_cfg.board_color = board_color
            runtime_cfg.board_opacity = board_opacity
            runtime_cfg.board_radius = board_radius
            runtime_cfg.item_color = item_color
            runtime_cfg.item_opacity = item_opacity
            runtime_cfg.item_radius = item_radius
            config.save()
        elif action == "set_banner":
            raw = str(payload.get("text", ""))
            text = " ".join(raw.split())[:200]
            _engine.cfg.banner_text = text
            runtime_cfg = config.get_config()
            runtime_cfg.banner_text = text
            config.save()
        else:
            return {"ok": False, "error": f"unknown action: {action}"}
        if ok:
            on_engine_changed()
            return {"ok": True, "snapshot": _engine.snapshot()}
        return {"ok": False, "error": "target user not found"}


def _clamp_float(value: Any, min_v: float, max_v: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = min_v
    return max(min_v, min(max_v, num))


def _normalize_hex_color(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) == 7 and s.startswith("#"):
        hex_part = s[1:]
        if all(c in "0123456789abcdefABCDEF" for c in hex_part):
            return "#" + hex_part.lower()
    return "#000000"


def _clamp_int(value: Any, min_v: int, max_v: int) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        num = min_v
    return max(min_v, min(max_v, num))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
