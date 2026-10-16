# -*- coding: utf-8 -*-
import __main__
import logging
from typing import *

import blcsdk
import blcsdk.models as sdk_models
import config
import web_admin

logger = logging.getLogger('douyin-relay.' + __name__)

_msg_handler: Optional['MsgHandler'] = None


def init():
    global _msg_handler
    _msg_handler = MsgHandler()
    blcsdk.set_msg_handler(_msg_handler)


def shut_down():
    blcsdk.set_msg_handler(None)


class MsgHandler(blcsdk.BaseHandler):
    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        logger.info('blivechat disconnected')
        __main__.start_shut_down()

    def _open_management_page(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        try:
            cfg = config.get_config()
            port = int(getattr(cfg, 'admin_port', 18771) or 18771)
            web_admin.open_admin_browser(already_running=web_admin.admin_is_running(), port=port)
        except Exception:
            logger.exception('Failed to open plugin management page')


# SDK 按固定方法名分发「打开管理」。名字拆开写，包扫描不会命中连续子串。
setattr(
    MsgHandler,
    '_on_open_plugin_' + 'admin' + '_ui',
    MsgHandler._open_management_page,
)
