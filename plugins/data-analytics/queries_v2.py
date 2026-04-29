# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import config

SOURCE_ALL = 'all'
VALID_SOURCES = {'bilibili', 'douyin', SOURCE_ALL}
VIEW_ALL = 'all'
VALID_VIEWS = {'session', 'time', VIEW_ALL}


@dataclass
class QueryContext:
    room_id: Optional[int] = None
    from_ts: Optional[int] = None
    to_ts: Optional[int] = None
    source: str = SOURCE_ALL
    view_mode: str = VIEW_ALL
    granularity: str = 'day'


def ensure_v2_schema() -> None:
    conn = sqlite3.connect(config.DB_V2_PATH, timeout=5)
    try:
        conn.executescript(
            '''
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS fact_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                room_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'bilibili',
                uid TEXT,
                author_name TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL DEFAULT 0,
                quantity INTEGER NOT NULL DEFAULT 1,
                gift_name TEXT NOT NULL DEFAULT '',
                author_type INTEGER NOT NULL DEFAULT 0,
                privilege_type INTEGER NOT NULL DEFAULT 0,
                medal_level INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS dim_sessions (
                session_id TEXT PRIMARY KEY,
                room_id INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'all',
                start_ts INTEGER NOT NULL,
                end_ts INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agg_revenue_daily (
                stat_date TEXT NOT NULL,
                room_id INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'all',
                gift_amount REAL NOT NULL DEFAULT 0,
                sc_amount REAL NOT NULL DEFAULT 0,
                member_amount REAL NOT NULL DEFAULT 0,
                total_revenue REAL NOT NULL DEFAULT 0,
                payer_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (stat_date, room_id, source)
            );

            CREATE TABLE IF NOT EXISTS metric_definitions (
                metric_key TEXT PRIMARY KEY,
                metric_name TEXT NOT NULL,
                expression TEXT NOT NULL,
                unit TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_fact_room_time ON fact_events(room_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_fact_source_time ON fact_events(source, timestamp);
            CREATE INDEX IF NOT EXISTS idx_fact_event_time ON fact_events(event_type, timestamp);
            '''
        )
        conn.execute(
            '''
            INSERT OR REPLACE INTO metric_definitions(metric_key, metric_name, expression, unit)
            VALUES
            ('total_revenue', '总营收', 'gift + super_chat + member', 'CNY'),
            ('gift_revenue', '礼物营收', 'sum(gift.amount)', 'CNY'),
            ('sc_revenue', 'SC营收', 'sum(super_chat.amount)', 'CNY'),
            ('member_revenue', '上舰营收', 'sum(member.amount)', 'CNY')
            '''
        )
        cur = conn.execute('PRAGMA table_info(fact_events)')
        cols = [r[1] for r in cur.fetchall()]
        if 'content' not in cols:
            conn.execute("ALTER TABLE fact_events ADD COLUMN content TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def parse_context(params: Dict[str, str]) -> QueryContext:
    source = (params.get('source') or SOURCE_ALL).strip().lower()
    view_mode = (params.get('view_mode') or VIEW_ALL).strip().lower()
    granularity = (params.get('granularity') or 'day').strip().lower()
    return QueryContext(
        room_id=_parse_int(params.get('room_id')),
        from_ts=_parse_int(params.get('from_ts')),
        to_ts=_parse_int(params.get('to_ts')),
        source=source if source in VALID_SOURCES else SOURCE_ALL,
        view_mode=view_mode if view_mode in VALID_VIEWS else VIEW_ALL,
        granularity=granularity if granularity in {'day', 'week', 'month'} else 'day',
    )


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query(sql: str, args: Sequence[Any] = (), *, one: bool = False) -> Any:
    conn = sqlite3.connect(config.DB_V2_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, args)
        if one:
            row = cur.fetchone()
            return dict(row) if row else {}
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _where(ctx: QueryContext) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    args: List[Any] = []
    if ctx.room_id is not None:
        clauses.append('room_id = ?')
        args.append(ctx.room_id)
    if ctx.from_ts is not None:
        clauses.append('timestamp >= ?')
        args.append(ctx.from_ts)
    if ctx.to_ts is not None:
        clauses.append('timestamp <= ?')
        args.append(ctx.to_ts)
    if ctx.source != SOURCE_ALL:
        clauses.append('source = ?')
        args.append(ctx.source)
    return (' WHERE ' + ' AND '.join(clauses), args) if clauses else ('', args)


async def get_kpis(ctx: QueryContext) -> Dict[str, Any]:
    return await asyncio.to_thread(_get_kpis_sync, ctx)


def _get_kpis_sync(ctx: QueryContext) -> Dict[str, Any]:
    where, args = _where(ctx)
    revenue_row = _query(
        f'''
        SELECT
            SUM(CASE WHEN event_type = 'gift' THEN amount ELSE 0 END) AS gift_revenue,
            SUM(CASE WHEN event_type = 'super_chat' THEN amount ELSE 0 END) AS sc_revenue,
            SUM(CASE WHEN event_type = 'member' THEN amount ELSE 0 END) AS member_revenue,
            SUM(CASE WHEN event_type IN ('gift', 'super_chat', 'member') THEN amount ELSE 0 END) AS total_revenue,
            COUNT(DISTINCT CASE WHEN event_type IN ('gift', 'super_chat', 'member') AND uid IS NOT NULL AND uid != '' THEN uid END) AS payer_count,
            COUNT(DISTINCT CASE WHEN event_type = 'danmaku' AND uid IS NOT NULL AND uid != '' THEN uid END) AS engager_count
        FROM fact_events{where}
        ''',
        args,
        one=True,
    )
    payer_count = int(revenue_row.get('payer_count', 0) or 0)
    total_revenue = float(revenue_row.get('total_revenue', 0) or 0)
    arppu = total_revenue / payer_count if payer_count else 0.0
    return {
        'totalRevenue': round(total_revenue, 2),
        'giftRevenue': round(float(revenue_row.get('gift_revenue', 0) or 0), 2),
        'scRevenue': round(float(revenue_row.get('sc_revenue', 0) or 0), 2),
        'memberRevenue': round(float(revenue_row.get('member_revenue', 0) or 0), 2),
        'payerCount': payer_count,
        'engagerCount': int(revenue_row.get('engager_count', 0) or 0),
        'arppu': round(arppu, 2),
    }


async def get_revenue_trend(ctx: QueryContext) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_revenue_trend_sync, ctx)


def _bucket_expr(granularity: str) -> str:
    if granularity == 'week':
        return "strftime('%Y-W%W', datetime(timestamp, 'unixepoch'))"
    if granularity == 'month':
        return "strftime('%Y-%m', datetime(timestamp, 'unixepoch'))"
    return "strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch'))"


def _get_revenue_trend_sync(ctx: QueryContext) -> List[Dict[str, Any]]:
    where, args = _where(ctx)
    bucket = _bucket_expr(ctx.granularity)
    return _query(
        f'''
        SELECT
            {bucket} AS bucket,
            SUM(CASE WHEN event_type = 'gift' THEN amount ELSE 0 END) AS gift,
            SUM(CASE WHEN event_type = 'super_chat' THEN amount ELSE 0 END) AS super_chat,
            SUM(CASE WHEN event_type = 'member' THEN amount ELSE 0 END) AS member,
            SUM(CASE WHEN event_type IN ('gift', 'super_chat', 'member') THEN amount ELSE 0 END) AS total
        FROM fact_events
        {where}
        GROUP BY bucket
        ORDER BY bucket ASC
        ''',
        args,
    )


async def get_user_segments(ctx: QueryContext) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_user_segments_sync, ctx)


def _get_user_segments_sync(ctx: QueryContext) -> List[Dict[str, Any]]:
    where, args = _where(ctx)
    rows = _query(
        f'''
        SELECT
            COALESCE(NULLIF(uid, ''), author_name, 'unknown') AS user_key,
            SUM(CASE WHEN event_type IN ('gift', 'super_chat', 'member') THEN amount ELSE 0 END) AS revenue,
            SUM(CASE WHEN event_type = 'danmaku' THEN quantity ELSE 0 END) AS danmaku_count
        FROM fact_events
        {where}
        GROUP BY user_key
        ''',
        args,
    )
    result = {'high': 0, 'mid': 0, 'low': 0, 'zero': 0}
    for row in rows:
        revenue = float(row.get('revenue', 0) or 0)
        if revenue >= 200:
            result['high'] += 1
        elif revenue >= 50:
            result['mid'] += 1
        elif revenue > 0:
            result['low'] += 1
        else:
            result['zero'] += 1
    return [{'segment': k, 'count': v} for k, v in result.items()]


async def get_explore_events(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    return await asyncio.to_thread(_get_explore_events_sync, ctx, params)


def _get_explore_events_sync(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    where, args = _where(ctx)
    limit = min(max(_parse_int(params.get('limit')) or 50, 1), 300)
    offset = max(_parse_int(params.get('offset')) or 0, 0)
    event_type = (params.get('event_type') or '').strip().lower()
    keyword = (params.get('keyword') or '').strip()[:64]
    if event_type in {'danmaku', 'gift', 'super_chat', 'member'}:
        where += (' AND ' if where else ' WHERE ') + 'event_type = ?'
        args.append(event_type)
    if keyword:
        where += (' AND ' if where else ' WHERE ') + '(author_name LIKE ? OR gift_name LIKE ?)'
        args.extend([f'%{keyword}%', f'%{keyword}%'])
    total = _query(f'SELECT COUNT(*) AS total FROM fact_events{where}', args, one=True).get('total', 0)
    items = _query(
        f'''
        SELECT id, event_type, room_id, timestamp, source, uid, author_name, amount, quantity, gift_name
        FROM fact_events
        {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        ''',
        [*args, limit, offset],
    )
    return {'total': total or 0, 'limit': limit, 'offset': offset, 'items': items}


def meta_from_context(ctx: QueryContext, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'context': {
            'room_id': ctx.room_id,
            'from_ts': ctx.from_ts,
            'to_ts': ctx.to_ts,
            'source': ctx.source,
            'view_mode': ctx.view_mode,
            'granularity': ctx.granularity,
        }
    }
    if extra:
        payload.update(extra)
    return payload


def _user_key_sql() -> str:
    return "COALESCE(NULLIF(TRIM(uid), ''), NULLIF(TRIM(author_name), ''), '')"


async def get_active_hour_of_day(ctx: QueryContext) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_active_hour_of_day_sync, ctx)


def _get_active_hour_of_day_sync(ctx: QueryContext) -> List[Dict[str, Any]]:
    where, args = _where(ctx)
    base = (
        ' AND ' if where else ' WHERE '
    ) + "event_type IN ('danmaku', 'gift')"
    sql = f'''
        SELECT
            CAST(strftime('%H', datetime(timestamp, 'unixepoch', 'localtime')) AS INTEGER) AS hour,
            SUM(CASE WHEN event_type = 'danmaku' THEN 1 ELSE 0 END) AS danmaku_count,
            SUM(CASE WHEN event_type = 'gift' THEN 1 ELSE 0 END) AS gift_count,
            COUNT(*) AS event_count,
            COUNT(DISTINCT {_user_key_sql()}) AS unique_user_count
        FROM fact_events
        {where}{base}
        GROUP BY hour
        ORDER BY hour ASC
    '''
    rows = _query(sql, args)
    by_hour = {int(r['hour']): r for r in rows}
    out: List[Dict[str, Any]] = []
    for h in range(24):
        r = by_hour.get(h)
        if r:
            out.append({
                'hour': h,
                'danmakuCount': int(r.get('danmaku_count') or 0),
                'giftCount': int(r.get('gift_count') or 0),
                'eventCount': int(r.get('event_count') or 0),
                'uniqueUserCount': int(r.get('unique_user_count') or 0),
            })
        else:
            out.append({
                'hour': h,
                'danmakuCount': 0,
                'giftCount': 0,
                'eventCount': 0,
                'uniqueUserCount': 0,
            })
    return out


async def get_ranking_danmaku_authors(ctx: QueryContext, limit: int) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_ranking_danmaku_authors_sync, ctx, limit)


def _get_ranking_danmaku_authors_sync(ctx: QueryContext, limit: int) -> List[Dict[str, Any]]:
    where, args = _where(ctx)
    extra = (' AND ' if where else ' WHERE ') + "event_type = 'danmaku'"
    uk = _user_key_sql()
    sql = f'''
        SELECT
            {uk} AS user_key,
            MAX(CASE WHEN TRIM(IFNULL(uid, '')) != '' THEN uid END) AS uid,
            MAX(author_name) AS author_name,
            COUNT(*) AS danmaku_count
        FROM fact_events
        {where}{extra}
        GROUP BY user_key
        HAVING user_key != ''
        ORDER BY danmaku_count DESC
        LIMIT ?
    '''
    rows = _query(sql, [*args, limit])
    return [
        {
            'uid': row.get('uid') or '',
            'authorName': row.get('author_name') or '',
            'danmakuCount': int(row.get('danmaku_count') or 0),
        }
        for row in rows
    ]


async def get_ranking_gift_authors(ctx: QueryContext, limit: int, sort: str) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_ranking_gift_authors_sync, ctx, limit, sort)


def _get_ranking_gift_authors_sync(ctx: QueryContext, limit: int, sort: str) -> List[Dict[str, Any]]:
    where, args = _where(ctx)
    extra = (' AND ' if where else ' WHERE ') + "event_type = 'gift'"
    uk = _user_key_sql()
    order = 'gift_count DESC' if sort == 'count' else 'gift_amount DESC'
    sql = f'''
        SELECT
            {uk} AS user_key,
            MAX(CASE WHEN TRIM(IFNULL(uid, '')) != '' THEN uid END) AS uid,
            MAX(author_name) AS author_name,
            SUM(quantity) AS gift_count,
            SUM(amount) AS gift_amount
        FROM fact_events
        {where}{extra}
        GROUP BY user_key
        HAVING user_key != ''
        ORDER BY {order}
        LIMIT ?
    '''
    rows = _query(sql, [*args, limit])
    return [
        {
            'uid': row.get('uid') or '',
            'authorName': row.get('author_name') or '',
            'giftCount': int(row.get('gift_count') or 0),
            'giftAmount': round(float(row.get('gift_amount') or 0), 4),
        }
        for row in rows
    ]


def _parse_user_params(params: Dict[str, str]) -> Tuple[str, str]:
    uid = (params.get('uid') or '').strip()
    author_name = (params.get('author_name') or '').strip()
    if uid:
        return uid, ''
    if author_name:
        return '', author_name
    raise ValueError('uid or author_name is required')


def _user_filter_clause(uid: str, author_name: str) -> Tuple[str, List[Any]]:
    if uid:
        return 'uid = ?', [uid]
    return "(uid IS NULL OR TRIM(uid) = '') AND author_name = ?", [author_name]


async def explore_user_danmaku(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    return await asyncio.to_thread(_explore_user_danmaku_sync, ctx, params)


def _explore_user_danmaku_sync(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    uid, author_name = _parse_user_params(params)
    limit = min(max(_parse_int(params.get('limit')) or 50, 1), 300)
    offset = max(_parse_int(params.get('offset')) or 0, 0)
    where, args = _where(ctx)
    user_where, user_args = _user_filter_clause(uid, author_name)
    where += (' AND ' if where else ' WHERE ') + "event_type = 'danmaku' AND " + user_where
    args.extend(user_args)
    total = _query(f'SELECT COUNT(*) AS total FROM fact_events{where}', args, one=True).get('total', 0)
    items = _query(
        f'''
        SELECT id, room_id, timestamp, uid, author_name, source,
               IFNULL(content, '') AS content
        FROM fact_events
        {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        ''',
        [*args, limit, offset],
    )
    return {'total': total or 0, 'limit': limit, 'offset': offset, 'items': items}


async def explore_user_gifts(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    return await asyncio.to_thread(_explore_user_gifts_sync, ctx, params)


def _explore_user_gifts_sync(ctx: QueryContext, params: Dict[str, str]) -> Dict[str, Any]:
    uid, author_name = _parse_user_params(params)
    limit = min(max(_parse_int(params.get('limit')) or 50, 1), 300)
    offset = max(_parse_int(params.get('offset')) or 0, 0)
    where, args = _where(ctx)
    user_where, user_args = _user_filter_clause(uid, author_name)
    where += (' AND ' if where else ' WHERE ') + "event_type = 'gift' AND " + user_where
    args.extend(user_args)
    total = _query(f'SELECT COUNT(*) AS total FROM fact_events{where}', args, one=True).get('total', 0)
    items = _query(
        f'''
        SELECT id, room_id, timestamp, uid, author_name, source,
               gift_name, quantity, amount
        FROM fact_events
        {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        ''',
        [*args, limit, offset],
    )
    return {'total': total or 0, 'limit': limit, 'offset': offset, 'items': items}
