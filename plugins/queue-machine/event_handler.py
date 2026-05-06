from __future__ import annotations

import __main__
import time
from typing import Callable, Optional
import webbrowser

import blcsdk
import blcsdk.models as sdk_models

import config
from queue_engine import QueueEngine


def _join_identity_complete(message: sdk_models.AddTextMsg) -> bool:
    """入队需可区分用户且可展示昵称：uid 与 author_name 均非空。"""
    uid = str(message.uid or "").strip()
    name = str(message.author_name or "").strip()
    return bool(uid and name)


class MsgHandler(blcsdk.BaseHandler):
    def __init__(self, engine: QueueEngine, on_changed: Callable[[], None]):
        self._engine = engine
        self._on_changed = on_changed
        self._seen_gift = {}

    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        __main__.start_shut_down()

    def _on_add_text(self, client: blcsdk.BlcPluginClient, message: sdk_models.AddTextMsg, extra: sdk_models.ExtraData):
        if message.is_mirror:
            return
        text = (message.content or "").strip()
        if text == self._engine.cfg.join_keyword:
            if not _join_identity_complete(message):
                return
            changed = self._engine.join_queue(
                uid=str(message.uid or "").strip(),
                name=str(message.author_name or "").strip(),
                avatar_url=str(message.avatar_url or ""),
                medal_level=int(message.medal_level or 0),
                privilege_type=int(message.privilege_type or 0),
            )
            if changed:
                self._on_changed()
        elif text == self._engine.cfg.cancel_keyword:
            if self._engine.cancel_queue(str(message.uid or "")):
                self._on_changed()

    def _on_add_gift(self, client: blcsdk.BlcPluginClient, message: sdk_models.AddGiftMsg, extra: sdk_models.ExtraData):
        gid = str(message.id or "")
        if gid:
            now = time.time()
            self._prune_seen(now)
            if gid in self._seen_gift:
                return
            self._seen_gift[gid] = now
        changed = self._engine.add_gift_value_coin(str(message.uid or ""), int(message.total_coin or 0))
        if changed:
            self._on_changed()

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        cfg = config.get_config()
        webbrowser.open_new_tab(f"http://{cfg.host}:{cfg.port}/admin")

    def _prune_seen(self, now: float) -> None:
        expired = [k for k, ts in self._seen_gift.items() if now - ts > 600]
        for k in expired:
            self._seen_gift.pop(k, None)


def install(engine: QueueEngine, on_changed: Callable[[], None]) -> None:
    blcsdk.set_msg_handler(MsgHandler(engine, on_changed))


def uninstall() -> None:
    blcsdk.set_msg_handler(None)
