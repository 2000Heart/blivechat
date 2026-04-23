# -*- coding: utf-8 -*-
import __main__
import logging
from typing import *

import blcsdk
import blcsdk.models as sdk_models
import admin_ui
import config

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

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        try:
            admin_ui.open_plugin_admin_ui()
        except Exception:
            logger.exception('Failed to open plugin admin UI')
