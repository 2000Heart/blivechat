#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据分析示例脚本
用于分析保存的直播弹幕数据
"""
import sqlite3
import sys
from datetime import datetime
from typing import *

import config

def connect_db():
    """连接数据库"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_room_list(conn: sqlite3.Connection):
    """打印房间列表"""
    cursor = conn.cursor()
    cursor.execute('SELECT room_id, room_key_type, room_key_value, created_at FROM rooms ORDER BY created_at DESC')
    rooms = cursor.fetchall()
    
    if not rooms:
        print('没有找到房间数据')
        return
    
    print(f'\n找到 {len(rooms)} 个房间:\n')
    print(f"{'房间ID':<12} {'类型':<8} {'创建时间':<20}")
    print('-' * 50)
    for room in rooms:
        room_type = '房间ID' if room['room_key_type'] == 1 else '身份码'
        created_at = room['created_at']
        print(f"{room['room_id']:<12} {room_type:<8} {created_at:<20}")


def analyze_room(conn: sqlite3.Connection, room_id: int):
    """分析指定房间的数据"""
    cursor = conn.cursor()
    
    print(f'\n=== 房间 {room_id} 数据分析 ===\n')
    
    # 弹幕统计
    cursor.execute('SELECT COUNT(*) as count FROM danmaku WHERE room_id = ?', (room_id,))
    danmaku_count = cursor.fetchone()['count']
    print(f'📝 弹幕总数: {danmaku_count:,}')
    
    # 礼物统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(total_coin) as total_coin,
            SUM(total_free_coin) as total_free_coin
        FROM gifts
        WHERE room_id = ?
    ''', (room_id,))
    gift_row = cursor.fetchone()
    gift_count = gift_row['count'] or 0
    gift_total_coin = gift_row['total_coin'] or 0
    gift_total_free_coin = gift_row['total_free_coin'] or 0
    print(f'🎁 礼物总数: {gift_count:,}')
    print(f'   付费礼物价值: {gift_total_coin/1000:.2f} 元')
    print(f'   免费礼物价值: {gift_total_free_coin} 银瓜子')
    
    # 上舰统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(total_coin) as total_coin
        FROM members
        WHERE room_id = ?
    ''', (room_id,))
    member_row = cursor.fetchone()
    member_count = member_row['count'] or 0
    member_total_coin = member_row['total_coin'] or 0
    print(f'⚓ 上舰总数: {member_count:,}')
    print(f'   上舰总价值: {member_total_coin/1000:.2f} 元')
    
    # 醒目留言统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(price) as total_price
        FROM super_chat
        WHERE room_id = ?
    ''', (room_id,))
    sc_row = cursor.fetchone()
    sc_count = sc_row['count'] or 0
    sc_total_price = sc_row['total_price'] or 0
    print(f'💬 醒目留言总数: {sc_count:,}')
    print(f'   醒目留言总价值: {sc_total_price:.2f} 元')
    
    # 活跃用户TOP10
    print('\n👥 活跃用户 TOP 10:')
    cursor.execute('''
        SELECT author_name, COUNT(*) as count
        FROM danmaku
        WHERE room_id = ?
        GROUP BY uid, author_name
        ORDER BY count DESC
        LIMIT 10
    ''', (room_id,))
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f'   {i:2d}. {row["author_name"]:<20} {row["count"]:>6} 条弹幕')
    
    # 礼物排行TOP10
    print('\n🎁 礼物排行 TOP 10:')
    cursor.execute('''
        SELECT gift_name, SUM(num) as total_num, SUM(total_coin) as total_coin
        FROM gifts
        WHERE room_id = ?
        GROUP BY gift_name
        ORDER BY total_coin DESC
        LIMIT 10
    ''', (room_id,))
    for i, row in enumerate(cursor.fetchall(), 1):
        total_coin = row['total_coin'] or 0
        print(f'   {i:2d}. {row["gift_name"]:<20} {row["total_num"]:>6} 个, {total_coin/1000:>8.2f} 元')
    
    # 时间段统计
    print('\n⏰ 时间段统计 (每小时):')
    cursor.execute('''
        SELECT 
            strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(*) as count
        FROM danmaku
        WHERE room_id = ?
        GROUP BY hour
        ORDER BY hour
        LIMIT 24
    ''', (room_id,))
    for row in cursor.fetchall():
        print(f'   {row["hour"]}: {row["count"]:>6} 条弹幕')
    
    # 用户类型统计
    print('\n👤 用户类型统计:')
    cursor.execute('''
        SELECT 
            CASE author_type
                WHEN 0 THEN '普通用户'
                WHEN 1 THEN '舰队'
                WHEN 2 THEN '房管'
                WHEN 3 THEN '主播'
                ELSE '未知'
            END as type_name,
            COUNT(*) as count
        FROM danmaku
        WHERE room_id = ?
        GROUP BY author_type
        ORDER BY count DESC
    ''', (room_id,))
    for row in cursor.fetchall():
        print(f'   {row["type_name"]:<10}: {row["count"]:>6} 条弹幕')


def analyze_all(conn: sqlite3.Connection):
    """分析所有房间的数据"""
    cursor = conn.cursor()
    
    print('\n=== 全站数据分析 ===\n')
    
    # 弹幕统计
    cursor.execute('SELECT COUNT(*) as count FROM danmaku')
    danmaku_count = cursor.fetchone()['count']
    print(f'📝 弹幕总数: {danmaku_count:,}')
    
    # 礼物统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(total_coin) as total_coin,
            SUM(total_free_coin) as total_free_coin
        FROM gifts
    ''')
    gift_row = cursor.fetchone()
    gift_count = gift_row['count'] or 0
    gift_total_coin = gift_row['total_coin'] or 0
    gift_total_free_coin = gift_row['total_free_coin'] or 0
    print(f'🎁 礼物总数: {gift_count:,}')
    print(f'   付费礼物价值: {gift_total_coin/1000:.2f} 元')
    print(f'   免费礼物价值: {gift_total_free_coin} 银瓜子')
    
    # 上舰统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(total_coin) as total_coin
        FROM members
    ''')
    member_row = cursor.fetchone()
    member_count = member_row['count'] or 0
    member_total_coin = member_row['total_coin'] or 0
    print(f'⚓ 上舰总数: {member_count:,}')
    print(f'   上舰总价值: {member_total_coin/1000:.2f} 元')
    
    # 醒目留言统计
    cursor.execute('''
        SELECT 
            COUNT(*) as count,
            SUM(price) as total_price
        FROM super_chat
    ''')
    sc_row = cursor.fetchone()
    sc_count = sc_row['count'] or 0
    sc_total_price = sc_row['total_price'] or 0
    print(f'💬 醒目留言总数: {sc_count:,}')
    print(f'   醒目留言总价值: {sc_total_price:.2f} 元')
    
    # 房间统计
    cursor.execute('SELECT COUNT(*) as count FROM rooms')
    room_count = cursor.fetchone()['count']
    print(f'\n🏠 房间总数: {room_count}')


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print('''
数据分析工具

用法:
    python analyze.py              # 显示房间列表
    python analyze.py <room_id>    # 分析指定房间
    python analyze.py --all        # 分析所有房间
            ''')
            return
    
    conn = connect_db()
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == '--all':
            analyze_all(conn)
        elif len(sys.argv) > 1:
            try:
                room_id = int(sys.argv[1])
                analyze_room(conn, room_id)
            except ValueError:
                print(f'错误: 无效的房间ID: {sys.argv[1]}')
        else:
            print_room_list(conn)
            print('\n提示: 使用 "python analyze.py <room_id>" 分析指定房间')
            print('      使用 "python analyze.py --all" 分析所有房间')
    finally:
        conn.close()


if __name__ == '__main__':
    main()

