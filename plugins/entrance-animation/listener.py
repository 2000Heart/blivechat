# -*- coding: utf-8 -*-
import __main__
import asyncio
import logging
import time
import webbrowser
from typing import *

import blcsdk
import blcsdk.models as sdk_models

import config
import store

logger = logging.getLogger('entrance-animation.' + __name__)

_msg_handler: Optional['MsgHandler'] = None
_web_server = None
_last_play_time: Dict[str, float] = {}


def init(web_server):
    global _msg_handler, _web_server
    _web_server = web_server
    _msg_handler = MsgHandler()
    blcsdk.set_msg_handler(_msg_handler)


def shut_down():
    blcsdk.set_msg_handler(None)


def _cooldown_ok(uid: str, cooldown_sec: int) -> bool:
    if cooldown_sec <= 0:
        cooldown_sec = int(store.get_global().get('defaultCooldownSec', 300) or 0)
    now = time.monotonic()
    last = _last_play_time.get(uid, 0.0)
    if cooldown_sec > 0 and now - last < cooldown_sec:
        remaining = cooldown_sec - (now - last)
        logger.info(
            'Skip entrance for uid=%s: cooldown active (%.0fs remaining of %ds)',
            uid, remaining, cooldown_sec,
        )
        return False
    _last_play_time[uid] = now
    return True


async def _broadcast_play(animation: dict, user: dict) -> None:
    if _web_server is None:
        logger.error('Cannot broadcast play for uid=%s: web server not initialized', user.get('uid'))
        return
    try:
        count = await _web_server.broadcast_play(animation, user)
        if count == 0:
            logger.warning(
                'Play event not delivered: no overlay WebSocket clients connected (uid=%s, animation=%s). '
                'Add OBS browser source: %s',
                user.get('uid'), animation.get('id'), config.build_overlay_url(),
            )
        else:
            logger.info(
                'Play event delivered to %d overlay client(s): uid=%s animation=%s (%s)',
                count, user.get('uid'), animation.get('id'), animation.get('name', ''),
            )
    except Exception:
        logger.exception('Failed to broadcast play event for uid=%s', user.get('uid'))


class MsgHandler(blcsdk.BaseHandler):
    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        logger.info('blivechat disconnected')
        __main__.start_shut_down()

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        url = config.build_admin_url()
        try:
            webbrowser.open(url)
            logger.info('Opened admin UI: %s', url)
        except Exception:
            logger.exception('Failed to open admin UI: %s', url)

    def _on_add_interact(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddInteractMsg, extra: sdk_models.ExtraData
    ):
        logger.info(
            'Received interact: uid=%s username=%s msg_type=%d room_id=%s',
            message.uid, message.username, message.msg_type, extra.room_id,
        )

        # 只处理进入直播间
        if message.msg_type != 1:
            logger.debug('Skip interact uid=%s: msg_type=%d is not enter-room(1)', message.uid, message.msg_type)
            return

        global_cfg = store.get_global()
        if not global_cfg.get('enabled', True):
            logger.info('Skip entrance for uid=%s: global plugin disabled', message.uid)
            return

        user_cfg = store.get_user(message.uid)
        if user_cfg is None:
            logger.debug('Skip entrance for uid=%s: user not in watch list', message.uid)
            return
        if not user_cfg.get('enabled', True):
            logger.info('Skip entrance for uid=%s: user disabled in config', message.uid)
            return

        animation_id = user_cfg.get('animationId', '')
        if not animation_id:
            logger.info('Skip entrance for uid=%s: no animation bound', message.uid)
            return
        animation = store.get_animation(animation_id)
        if animation is None:
            logger.warning('Skip entrance for uid=%s: bound animation %s not found', message.uid, animation_id)
            return

        if not _cooldown_ok(message.uid, int(user_cfg.get('cooldownSec', 0) or 0)):
            return

        user = {
            'uid': message.uid,
            'name': message.username or user_cfg.get('name', ''),
            'avatarUrl': message.avatar_url,
        }
        logger.info(
            'Trigger entrance animation: user=%s uid=%s animation=%s (%s, type=%s)',
            user['name'], message.uid, animation_id, animation.get('name', ''), animation.get('type', ''),
        )
        asyncio.create_task(_broadcast_play(animation, user))
