# -*- coding: utf-8 -*-
import logging
import sqlite3
import threading
from typing import *

import config
import queries_v2

logger = logging.getLogger('data-analytics.database')

# 线程本地存储，每个线程使用独立的数据库连接
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    if not hasattr(_local, 'connection') or _local.connection is None:
        queries_v2.ensure_v2_schema()
        _local.connection = sqlite3.connect(
            config.DB_V2_PATH,
            check_same_thread=False,
            isolation_level=None  # 自动提交模式
        )
        _local.connection.row_factory = sqlite3.Row
        _local.connection.execute('PRAGMA busy_timeout = 5000')
        _local.connection.execute('PRAGMA journal_mode = WAL')
        _init_database(_local.connection)
    return _local.connection


def close_connection():
    """关闭当前线程的数据库连接"""
    if hasattr(_local, 'connection') and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


def _init_database(conn: sqlite3.Connection):
    """初始化数据库表结构（v2-only）"""
    del conn
    queries_v2.ensure_v2_schema()
    logger.info('Database initialized (v2-only)')


def add_room(room_id: int, room_key_type: int, room_key_value: Union[int, str]):
    """v2 不再写 rooms 维表，保留接口避免调用侧改动。"""
    logger.debug('Skip room metadata in v2-only mode: room_id=%s type=%s value=%s', room_id, room_key_type, room_key_value)


def add_danmaku(
    msg_id: str,
    room_id: int,
    timestamp: int,
    uid: str,
    author_name: str,
    author_type: int,
    author_level: int,
    content: str,
    translation: str = '',
    is_gift_danmaku: bool = False,
    is_newbie: bool = False,
    is_mobile_verified: bool = True,
    privilege_type: int = 0,
    medal_level: int = 0,
    medal_name: str = '',
    content_type: int = 0,
    avatar_url: str = '',
    source: str = 'bilibili',
):
    """添加弹幕记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fact_events (
            id, event_type, room_id, timestamp, source, uid, author_name,
            amount, quantity, gift_name, author_type, privilege_type, medal_level, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, 'danmaku', room_id, timestamp, source, uid, author_name,
        0.0, 1, '', author_type, privilege_type, medal_level, content or '',
    ))
    conn.commit()


def add_gift(
    msg_id: str,
    room_id: int,
    timestamp: int,
    uid: str,
    author_name: str,
    gift_id: int,
    gift_name: str,
    gift_icon_url: str,
    num: int,
    total_coin: int,
    total_free_coin: int,
    privilege_type: int = 0,
    medal_level: int = 0,
    medal_name: str = '',
    avatar_url: str = '',
    source: str = 'bilibili',
):
    """添加礼物记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fact_events (
            id, event_type, room_id, timestamp, source, uid, author_name,
            amount, quantity, gift_name, author_type, privilege_type, medal_level, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, 'gift', room_id, timestamp, source, uid, author_name,
        float(total_coin or 0) / 1000.0, max(1, int(num or 1)), gift_name or '',
        0, privilege_type, medal_level, '',
    ))
    conn.commit()


def add_member(
    msg_id: str,
    room_id: int,
    timestamp: int,
    uid: str,
    author_name: str,
    privilege_type: int,
    num: int,
    unit: str,
    total_coin: int,
    medal_level: int = 0,
    medal_name: str = '',
    avatar_url: str = '',
    source: str = 'bilibili',
):
    """添加上舰记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fact_events (
            id, event_type, room_id, timestamp, source, uid, author_name,
            amount, quantity, gift_name, author_type, privilege_type, medal_level, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, 'member', room_id, timestamp, source, uid, author_name,
        float(total_coin or 0) / 1000.0, max(1, int(num or 1)), '',
        0, privilege_type, medal_level, '',
    ))
    conn.commit()


def add_super_chat(
    msg_id: str,
    room_id: int,
    timestamp: int,
    uid: str,
    author_name: str,
    price: int,
    content: str,
    translation: str = '',
    privilege_type: int = 0,
    medal_level: int = 0,
    medal_name: str = '',
    avatar_url: str = '',
    source: str = 'bilibili',
):
    """添加醒目留言记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fact_events (
            id, event_type, room_id, timestamp, source, uid, author_name,
            amount, quantity, gift_name, author_type, privilege_type, medal_level, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, 'super_chat', room_id, timestamp, source, uid, author_name,
        float(price or 0), 1, '', 0, privilege_type, medal_level, content or '',
    ))
    conn.commit()



