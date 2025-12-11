# -*- coding: utf-8 -*-
import logging
import sqlite3
import threading
from datetime import datetime
from typing import *

import config

logger = logging.getLogger('data-analytics.database')

# 线程本地存储，每个线程使用独立的数据库连接
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = sqlite3.connect(
            config.DB_PATH,
            check_same_thread=False,
            isolation_level=None  # 自动提交模式
        )
        _local.connection.row_factory = sqlite3.Row
        _init_database(_local.connection)
    return _local.connection


def close_connection():
    """关闭当前线程的数据库连接"""
    if hasattr(_local, 'connection') and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


def _init_database(conn: sqlite3.Connection):
    """初始化数据库表结构"""
    cursor = conn.cursor()
    
    # 房间表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY,
            room_key_type INTEGER NOT NULL,
            room_key_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(room_id)
        )
    ''')
    
    # 弹幕表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS danmaku (
            id TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            uid TEXT,
            author_name TEXT NOT NULL,
            author_type INTEGER NOT NULL,
            author_level INTEGER NOT NULL,
            content TEXT NOT NULL,
            translation TEXT,
            is_gift_danmaku INTEGER NOT NULL DEFAULT 0,
            is_newbie INTEGER NOT NULL DEFAULT 0,
            is_mobile_verified INTEGER NOT NULL DEFAULT 1,
            privilege_type INTEGER NOT NULL DEFAULT 0,
            medal_level INTEGER NOT NULL DEFAULT 0,
            medal_name TEXT,
            content_type INTEGER NOT NULL DEFAULT 0,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')
    
    # 礼物表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gifts (
            id TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            uid TEXT,
            author_name TEXT NOT NULL,
            gift_id INTEGER NOT NULL,
            gift_name TEXT NOT NULL,
            gift_icon_url TEXT,
            num INTEGER NOT NULL,
            total_coin INTEGER NOT NULL DEFAULT 0,
            total_free_coin INTEGER NOT NULL DEFAULT 0,
            privilege_type INTEGER NOT NULL DEFAULT 0,
            medal_level INTEGER NOT NULL DEFAULT 0,
            medal_name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')
    
    # 上舰表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            uid TEXT,
            author_name TEXT NOT NULL,
            privilege_type INTEGER NOT NULL,
            num INTEGER NOT NULL,
            unit TEXT NOT NULL,
            total_coin INTEGER NOT NULL,
            medal_level INTEGER NOT NULL DEFAULT 0,
            medal_name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')
    
    # 醒目留言表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS super_chat (
            id TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            uid TEXT,
            author_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            content TEXT NOT NULL,
            translation TEXT,
            privilege_type INTEGER NOT NULL DEFAULT 0,
            medal_level INTEGER NOT NULL DEFAULT 0,
            medal_name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')
    
    # 创建索引以提高查询性能
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_danmaku_room_time ON danmaku(room_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_danmaku_uid ON danmaku(uid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gifts_room_time ON gifts(room_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gifts_uid ON gifts(uid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_members_room_time ON members(room_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_members_uid ON members(uid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_super_chat_room_time ON super_chat(room_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_super_chat_uid ON super_chat(uid)')
    
    conn.commit()
    logger.info('Database initialized')


def add_room(room_id: int, room_key_type: int, room_key_value: Union[int, str]):
    """添加或更新房间信息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO rooms (room_id, room_key_type, room_key_value)
        VALUES (?, ?, ?)
    ''', (room_id, room_key_type, str(room_key_value)))
    conn.commit()


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
    avatar_url: str = ''
):
    """添加弹幕记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO danmaku (
            id, room_id, timestamp, uid, author_name, author_type, author_level,
            content, translation, is_gift_danmaku, is_newbie, is_mobile_verified,
            privilege_type, medal_level, medal_name, content_type, avatar_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, room_id, timestamp, uid, author_name, author_type, author_level,
        content, translation, 1 if is_gift_danmaku else 0, 1 if is_newbie else 0,
        1 if is_mobile_verified else 0, privilege_type, medal_level, medal_name,
        content_type, avatar_url
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
    avatar_url: str = ''
):
    """添加礼物记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO gifts (
            id, room_id, timestamp, uid, author_name, gift_id, gift_name,
            gift_icon_url, num, total_coin, total_free_coin, privilege_type,
            medal_level, medal_name, avatar_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, room_id, timestamp, uid, author_name, gift_id, gift_name,
        gift_icon_url, num, total_coin, total_free_coin, privilege_type,
        medal_level, medal_name, avatar_url
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
    avatar_url: str = ''
):
    """添加上舰记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO members (
            id, room_id, timestamp, uid, author_name, privilege_type,
            num, unit, total_coin, medal_level, medal_name, avatar_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, room_id, timestamp, uid, author_name, privilege_type,
        num, unit, total_coin, medal_level, medal_name, avatar_url
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
    avatar_url: str = ''
):
    """添加醒目留言记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO super_chat (
            id, room_id, timestamp, uid, author_name, price, content,
            translation, privilege_type, medal_level, medal_name, avatar_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        msg_id, room_id, timestamp, uid, author_name, price, content,
        translation, privilege_type, medal_level, medal_name, avatar_url
    ))
    conn.commit()


def get_statistics(room_id: Optional[int] = None) -> dict:
    """获取统计数据"""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # 弹幕统计
    if room_id:
        cursor.execute('SELECT COUNT(*) as count FROM danmaku WHERE room_id = ?', (room_id,))
    else:
        cursor.execute('SELECT COUNT(*) as count FROM danmaku')
    stats['danmaku_count'] = cursor.fetchone()['count']
    
    # 礼物统计
    if room_id:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(total_coin) as total_coin, SUM(total_free_coin) as total_free_coin
            FROM gifts WHERE room_id = ?
        ''', (room_id,))
    else:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(total_coin) as total_coin, SUM(total_free_coin) as total_free_coin
            FROM gifts
        ''')
    gift_row = cursor.fetchone()
    stats['gift_count'] = gift_row['count'] or 0
    stats['gift_total_coin'] = gift_row['total_coin'] or 0
    stats['gift_total_free_coin'] = gift_row['total_free_coin'] or 0
    
    # 上舰统计
    if room_id:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(total_coin) as total_coin
            FROM members WHERE room_id = ?
        ''', (room_id,))
    else:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(total_coin) as total_coin
            FROM members
        ''')
    member_row = cursor.fetchone()
    stats['member_count'] = member_row['count'] or 0
    stats['member_total_coin'] = member_row['total_coin'] or 0
    
    # 醒目留言统计
    if room_id:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(price) as total_price
            FROM super_chat WHERE room_id = ?
        ''', (room_id,))
    else:
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(price) as total_price
            FROM super_chat
        ''')
    sc_row = cursor.fetchone()
    stats['super_chat_count'] = sc_row['count'] or 0
    stats['super_chat_total_price'] = sc_row['total_price'] or 0
    
    return stats

