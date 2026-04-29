# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Dict, Iterable, List, Tuple

import config
import queries_v2


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _iter_source_rows(conn: sqlite3.Connection, sql: str) -> Iterable[sqlite3.Row]:
    cur = conn.execute(sql)
    for row in cur:
        yield row


def _event_rows_from_legacy(source_conn: sqlite3.Connection) -> List[Tuple]:
    rows: List[Tuple] = []
    for row in _iter_source_rows(
        source_conn,
        '''
        SELECT id, room_id, timestamp, IFNULL(source, 'bilibili') AS source, uid, author_name, author_type, privilege_type, medal_level, content
        FROM danmaku
        ''',
    ):
        rows.append((
            row['id'], 'danmaku', row['room_id'], row['timestamp'], row['source'], row['uid'], row['author_name'],
            0.0, 1, '', row['author_type'], row['privilege_type'], row['medal_level'],
            row['content'] if row['content'] is not None else '',
        ))
    for row in _iter_source_rows(
        source_conn,
        '''
        SELECT id, room_id, timestamp, IFNULL(source, 'bilibili') AS source, uid, author_name, gift_name, num, total_coin, privilege_type, medal_level
        FROM gifts
        ''',
    ):
        amount = float(row['total_coin'] or 0) / 1000.0
        rows.append((
            row['id'], 'gift', row['room_id'], row['timestamp'], row['source'], row['uid'], row['author_name'],
            amount, int(row['num'] or 1), row['gift_name'] or '', 0, row['privilege_type'], row['medal_level'], '',
        ))
    for row in _iter_source_rows(
        source_conn,
        '''
        SELECT id, room_id, timestamp, uid, author_name, total_coin, privilege_type, medal_level
        FROM members
        ''',
    ):
        amount = float(row['total_coin'] or 0) / 1000.0
        rows.append((
            row['id'], 'member', row['room_id'], row['timestamp'], 'all', row['uid'], row['author_name'],
            amount, 1, '', 0, row['privilege_type'], row['medal_level'], '',
        ))
    for row in _iter_source_rows(
        source_conn,
        '''
        SELECT id, room_id, timestamp, uid, author_name, price, privilege_type, medal_level
        FROM super_chat
        ''',
    ):
        amount = float(row['price'] or 0)
        rows.append((
            row['id'], 'super_chat', row['room_id'], row['timestamp'], 'all', row['uid'], row['author_name'],
            amount, 1, '', 0, row['privilege_type'], row['medal_level'], '',
        ))
    return rows


def _load_events(v2_conn: sqlite3.Connection, rows: List[Tuple]) -> None:
    v2_conn.executemany(
        '''
        INSERT OR REPLACE INTO fact_events(
            id, event_type, room_id, timestamp, source, uid, author_name,
            amount, quantity, gift_name, author_type, privilege_type, medal_level, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        rows,
    )


def _refresh_daily_agg(v2_conn: sqlite3.Connection) -> None:
    v2_conn.execute('DELETE FROM agg_revenue_daily')
    v2_conn.execute(
        '''
        INSERT INTO agg_revenue_daily(
            stat_date, room_id, source, gift_amount, sc_amount, member_amount, total_revenue, payer_count
        )
        SELECT
            strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch')) AS stat_date,
            room_id,
            source,
            SUM(CASE WHEN event_type = 'gift' THEN amount ELSE 0 END) AS gift_amount,
            SUM(CASE WHEN event_type = 'super_chat' THEN amount ELSE 0 END) AS sc_amount,
            SUM(CASE WHEN event_type = 'member' THEN amount ELSE 0 END) AS member_amount,
            SUM(CASE WHEN event_type IN ('gift', 'super_chat', 'member') THEN amount ELSE 0 END) AS total_revenue,
            COUNT(DISTINCT CASE WHEN event_type IN ('gift', 'super_chat', 'member') AND uid IS NOT NULL AND uid != '' THEN uid END) AS payer_count
        FROM fact_events
        GROUP BY stat_date, room_id, source
        '''
    )


def reconcile() -> Dict[str, float]:
    src = _connect(config.DB_PATH)
    dst = _connect(config.DB_V2_PATH)
    try:
        src_gift = src.execute('SELECT SUM(total_coin) AS v FROM gifts').fetchone()['v'] or 0
        src_member = src.execute('SELECT SUM(total_coin) AS v FROM members').fetchone()['v'] or 0
        src_sc = src.execute('SELECT SUM(price) AS v FROM super_chat').fetchone()['v'] or 0
        dst_gift = dst.execute("SELECT SUM(amount) AS v FROM fact_events WHERE event_type='gift'").fetchone()['v'] or 0
        dst_member = dst.execute("SELECT SUM(amount) AS v FROM fact_events WHERE event_type='member'").fetchone()['v'] or 0
        dst_sc = dst.execute("SELECT SUM(amount) AS v FROM fact_events WHERE event_type='super_chat'").fetchone()['v'] or 0
        return {
            'gift_delta': round(float(src_gift) / 1000.0 - float(dst_gift), 4),
            'member_delta': round(float(src_member) / 1000.0 - float(dst_member), 4),
            'sc_delta': round(float(src_sc) - float(dst_sc), 4),
        }
    finally:
        src.close()
        dst.close()


def run(full: bool) -> Dict[str, Any]:
    queries_v2.ensure_v2_schema()
    legacy_conn = _connect(config.DB_PATH)
    v2_conn = _connect(config.DB_V2_PATH)
    try:
        if full:
            v2_conn.execute('DELETE FROM fact_events')
        rows = _event_rows_from_legacy(legacy_conn)
        _load_events(v2_conn, rows)
        _refresh_daily_agg(v2_conn)
        v2_conn.commit()
    finally:
        legacy_conn.close()
        v2_conn.close()

    return {'rows': len(rows), 'reconcile': reconcile()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate analytics.db to analytics_v2.db')
    parser.add_argument('--full', action='store_true', help='Clear v2 fact table before import')
    args = parser.parse_args()
    result = run(full=args.full)
    print('migration_done', result)
