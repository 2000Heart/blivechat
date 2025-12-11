# -*- coding: utf-8 -*-
import __main__
import logging
import sys
from typing import *

import blcsdk
import blcsdk.models as sdk_models

import config
import database

logger = logging.getLogger('data-analytics.' + __name__)

_msg_handler: Optional['DataAnalyticsHandler'] = None


async def init():
    global _msg_handler
    _msg_handler = DataAnalyticsHandler()
    blcsdk.set_msg_handler(_msg_handler)

    # 初始化数据库
    database.get_connection()
    logger.info('Data analytics plugin initialized, database: %s', config.DB_PATH)

    # 获取已有房间
    try:
        blc_rooms = await blcsdk.get_rooms()
        for blc_room in blc_rooms:
            if blc_room.room_id is not None:
                database.add_room(
                    blc_room.room_id,
                    blc_room.room_key.type,
                    blc_room.room_key.value
                )
                logger.info('Added existing room: %d', blc_room.room_id)
    except (blcsdk.SdkError, AttributeError):
        pass


def shut_down():
    blcsdk.set_msg_handler(None)
    database.close_connection()
    logger.info('Data analytics plugin shut down')


class DataAnalyticsHandler(blcsdk.BaseHandler):
    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        logger.info('blivechat disconnected')
        __main__.start_shut_down()

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        if sys.platform == 'win32':
            import os
            os.startfile(config.DATA_PATH)
        else:
            logger.info('Data path is "%s"', config.DATA_PATH)

    def _on_add_room(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddRoomMsg, extra: sdk_models.ExtraData
    ):
        """添加房间"""
        if extra.is_from_plugin:
            return
        if extra.room_key is not None:
            # 此时room_id可能还是None，等ROOM_INIT时再添加
            pass

    def _on_room_init(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.RoomInitMsg, extra: sdk_models.ExtraData
    ):
        """房间初始化"""
        if extra.is_from_plugin:
            return
        if message.is_success and extra.room_id is not None and extra.room_key is not None:
            database.add_room(
                extra.room_id,
                extra.room_key.type,
                extra.room_key.value
            )
            logger.info('Room initialized: %d', extra.room_id)

    def _on_add_text(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddTextMsg, extra: sdk_models.ExtraData
    ):
        """收到弹幕"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_danmaku(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                author_type=message.author_type,
                author_level=message.author_level,
                content=message.content,
                translation=message.translation,
                is_gift_danmaku=message.is_gift_danmaku,
                is_newbie=message.is_newbie,
                is_mobile_verified=message.is_mobile_verified,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                content_type=message.content_type,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save danmaku: %s', e)

    def _on_add_gift(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddGiftMsg, extra: sdk_models.ExtraData
    ):
        """有人送礼"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_gift(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                gift_id=message.gift_id,
                gift_name=message.gift_name,
                gift_icon_url=message.gift_icon_url,
                num=message.num,
                total_coin=message.total_coin,
                total_free_coin=message.total_free_coin,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save gift: %s', e)

    def _on_add_member(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddMemberMsg, extra: sdk_models.ExtraData
    ):
        """有人上舰"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_member(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                privilege_type=message.privilege_type,
                num=message.num,
                unit=message.unit,
                total_coin=message.total_coin,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save member: %s', e)

    def _on_add_super_chat(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddSuperChatMsg, extra: sdk_models.ExtraData
    ):
        """醒目留言"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_super_chat(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                price=message.price,
                content=message.content,
                translation=message.translation,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save super chat: %s', e)

