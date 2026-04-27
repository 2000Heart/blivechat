# -*- coding: utf-8 -*-
from __future__ import annotations

import __main__
import logging
from typing import Optional

import blcsdk
import blcsdk.models as sdk_models

import admin_ui
import config
from queue_state import QueueState, is_queue_keyword, room_key_to_str

logger = logging.getLogger("queue-manager." + __name__)

_msg_handler: Optional["QueueHandler"] = None
_web_server = None
_queue_state: Optional[QueueState] = None


def init(web_server, queue_state: QueueState) -> None:
    global _msg_handler, _web_server, _queue_state
    _web_server = web_server
    _queue_state = queue_state
    _msg_handler = QueueHandler()
    blcsdk.set_msg_handler(_msg_handler)


def shut_down() -> None:
    blcsdk.set_msg_handler(None)


class QueueHandler(blcsdk.BaseHandler):
    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        logger.info("blivechat disconnected")
        __main__.start_shut_down()

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        if _web_server is None:
            return
        admin_ui.open_plugin_admin_ui(_web_server.admin_url)

    def _on_add_text(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddTextMsg, extra: sdk_models.ExtraData
    ):
        if extra.is_from_plugin or _queue_state is None or _web_server is None:
            return
        if not is_queue_keyword(message.content):
            return
        if not _eligible(message):
            return
        room_key_str = room_key_to_str(extra.room_key)
        user_key = message.uid.strip() or message.author_name.strip()
        if user_key == "":
            return
        cfg = config.get_config()
        changed = _queue_state.enqueue(
            room_key_str=room_key_str,
            user_key=user_key,
            uid=message.uid,
            author_name=message.author_name,
            avatar_url=message.avatar_url,
            guard_level=message.privilege_type,
            medal_level=message.medal_level,
            medal_name=message.medal_name,
            max_queue_size=cfg.max_queue_size,
        )
        if changed:
            self._schedule_broadcast(room_key_str)

    def _on_add_gift(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddGiftMsg, extra: sdk_models.ExtraData
    ):
        if extra.is_from_plugin or _queue_state is None or _web_server is None:
            return
        room_key_str = room_key_to_str(extra.room_key)
        user_key = message.uid.strip() or message.author_name.strip()
        if user_key == "":
            return
        value = int(message.total_coin or 0)
        if value <= 0:
            value = int(message.total_free_coin or 0)
        if value <= 0:
            return
        if _queue_state.add_gift(room_key_str=room_key_str, user_key=user_key, value=value, ts=message.timestamp):
            self._schedule_broadcast(room_key_str)

    @staticmethod
    def _schedule_broadcast(room_key_str: str) -> None:
        if _web_server is None:
            return
        import asyncio

        asyncio.create_task(_web_server.broadcast_room(room_key_str))


def _eligible(message: sdk_models.AddTextMsg) -> bool:
    cfg = config.get_config()
    guard_level = int(message.privilege_type)
    medal_level = int(message.medal_level)
    if cfg.require_guard and guard_level < cfg.min_guard_level:
        return False
    if cfg.require_fans_medal and medal_level <= 0:
        return False
    if medal_level < cfg.min_fans_level:
        return False
    return True
