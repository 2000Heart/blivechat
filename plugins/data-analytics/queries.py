# -*- coding: utf-8 -*-
import asyncio
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import config

_SOURCE_ALL = 'all'
_VALID_SOURCE = {'bilibili', 'douyin', _SOURCE_ALL}


@dataclass
class QueryFilters:
    room_id: Optional[int] = None
    from_ts: Optional[int] = None
    to_ts: Optional[int] = None
    source: str = _SOURCE_ALL


def parse_filters(params: Dict[str, str]) -> QueryFilters:
    room_id = _parse_int(params.get('room_id'))
    from_ts = _parse_int(params.get('from_ts'))
    to_ts = _parse_int(params.get('to_ts'))
    source = (params.get('source') or _SOURCE_ALL).strip().lower()
    if source not in _VALID_SOURCE:
        source = _SOURCE_ALL
    return QueryFilters(room_id=room_id, from_ts=from_ts, to_ts=to_ts, source=source)


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query(
    sql: str,
    args: Sequence[Any] = (),
    *,
    one: bool = False,
) -> Any:
    conn = sqlite3.connect(config.DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout = 5000')
    try:
        cur = conn.execute(sql, args)
        if one:
            row = cur.fetchone()
            return dict(row) if row is not None else {}
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _filters_where(
    filters: QueryFilters,
    *,
    include_source: bool = False,
) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    args: List[Any] = []
    if filters.room_id is not None:
        clauses.append('room_id = ?')
        args.append(filters.room_id)
    if filters.from_ts is not None:
        clauses.append('timestamp >= ?')
        args.append(filters.from_ts)
    if filters.to_ts is not None:
        clauses.append('timestamp <= ?')
        args.append(filters.to_ts)
    if include_source and filters.source != _SOURCE_ALL:
        clauses.append("IFNULL(source, 'bilibili') = ?")
        args.append(filters.source)
    return (' WHERE ' + ' AND '.join(clauses), args) if clauses else ('', args)


def _limit(value: Optional[str], default: int, max_value: int = 200) -> int:
    parsed = _parse_int(value)
    if parsed is None:
        return default
    return max(1, min(parsed, max_value))


def _offset(value: Optional[str]) -> int:
    parsed = _parse_int(value)
    if parsed is None:
        return 0
    return max(0, parsed)


async def get_rooms() -> List[Dict[str, Any]]:
    return await asyncio.to_thread(
        _query,
        'SELECT room_id, room_key_type, room_key_value, created_at FROM rooms ORDER BY created_at DESC',
    )


async def get_time_bounds(filters: QueryFilters) -> Dict[str, Any]:
    return await asyncio.to_thread(_get_time_bounds_sync, filters)


def _get_time_bounds_sync(filters: QueryFilters) -> Dict[str, Any]:
    tables = ['danmaku', 'gifts', 'members', 'super_chat']
    data = {}
    global_min = None
    global_max = None
    for table in tables:
        where, args = _filters_where(filters, include_source=(table in ('danmaku', 'gifts')))
        row = _query(
            f'SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts FROM {table}{where}',
            args,
            one=True,
        )
        min_ts = row.get('min_ts')
        max_ts = row.get('max_ts')
        data[table] = {'minTs': min_ts, 'maxTs': max_ts}
        if min_ts is not None and (global_min is None or min_ts < global_min):
            global_min = min_ts
        if max_ts is not None and (global_max is None or max_ts > global_max):
            global_max = max_ts
    return {'globalMinTs': global_min, 'globalMaxTs': global_max, 'tables': data}


async def get_overview(filters: QueryFilters) -> Dict[str, Any]:
    return await asyncio.to_thread(_get_overview_sync, filters)


def _get_overview_sync(filters: QueryFilters) -> Dict[str, Any]:
    dm_where, dm_args = _filters_where(filters, include_source=True)
    gift_where, gift_args = _filters_where(filters, include_source=True)
    common_where, common_args = _filters_where(filters, include_source=False)
    dm_count = _query(f'SELECT COUNT(*) AS count FROM danmaku{dm_where}', dm_args, one=True).get('count', 0)
    gift_row = _query(
        f'SELECT COUNT(*) AS count, SUM(total_coin) AS total_coin, SUM(total_free_coin) AS total_free_coin FROM gifts{gift_where}',
        gift_args,
        one=True,
    )
    member_row = _query(
        f'SELECT COUNT(*) AS count, SUM(total_coin) AS total_coin FROM members{common_where}',
        common_args,
        one=True,
    )
    sc_row = _query(
        f'SELECT COUNT(*) AS count, SUM(price) AS total_price FROM super_chat{common_where}',
        common_args,
        one=True,
    )
    dm_douyin = _query(
        f"SELECT COUNT(*) AS count FROM danmaku{dm_where}{' AND ' if dm_where else ' WHERE '}IFNULL(source, 'bilibili') = 'douyin'",
        dm_args,
        one=True,
    )
    gift_douyin = _query(
        f"SELECT COUNT(*) AS count FROM gifts{gift_where}{' AND ' if gift_where else ' WHERE '}IFNULL(source, 'bilibili') = 'douyin'",
        gift_args,
        one=True,
    )
    return {
        'danmakuCount': dm_count or 0,
        'danmakuDouyinCount': dm_douyin.get('count', 0) or 0,
        'giftCount': gift_row.get('count', 0) or 0,
        'giftDouyinCount': gift_douyin.get('count', 0) or 0,
        'giftTotalCoin': gift_row.get('total_coin', 0) or 0,
        'giftTotalFreeCoin': gift_row.get('total_free_coin', 0) or 0,
        'memberCount': member_row.get('count', 0) or 0,
        'memberTotalCoin': member_row.get('total_coin', 0) or 0,
        'superChatCount': sc_row.get('count', 0) or 0,
        'superChatTotalPrice': sc_row.get('total_price', 0) or 0,
    }


async def get_danmaku_by_hour(filters: QueryFilters) -> List[Dict[str, Any]]:
    where, args = _filters_where(filters, include_source=True)
    sql = (
        "SELECT strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) AS hour, "
        "COUNT(*) AS count FROM danmaku"
        f"{where} GROUP BY hour ORDER BY hour ASC"
    )
    return await asyncio.to_thread(_query, sql, args)


async def get_gifts_by_name(filters: QueryFilters, limit: int) -> List[Dict[str, Any]]:
    where, args = _filters_where(filters, include_source=True)
    sql = (
        'SELECT gift_name, SUM(num) AS total_num, SUM(total_coin) AS total_coin '
        f'FROM gifts{where} GROUP BY gift_name ORDER BY total_coin DESC LIMIT ?'
    )
    return await asyncio.to_thread(_query, sql, [*args, limit])


async def get_author_type_distribution(filters: QueryFilters) -> List[Dict[str, Any]]:
    where, args = _filters_where(filters, include_source=True)
    sql = (
        'SELECT CASE author_type WHEN 0 THEN ? WHEN 1 THEN ? WHEN 2 THEN ? WHEN 3 THEN ? ELSE ? END AS type_name, '
        f'author_type, COUNT(*) AS count FROM danmaku{where} GROUP BY author_type ORDER BY count DESC'
    )
    return await asyncio.to_thread(
        _query,
        sql,
        ['普通用户', '舰队', '房管', '主播', '未知', *args],
    )


async def get_revenue_mix(filters: QueryFilters) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_revenue_mix_sync, filters)


def _get_revenue_mix_sync(filters: QueryFilters) -> List[Dict[str, Any]]:
    gift_where, gift_args = _filters_where(filters, include_source=True)
    common_where, common_args = _filters_where(filters, include_source=False)
    rows = []
    gift = _query(f'SELECT SUM(total_coin) AS total FROM gifts{gift_where}', gift_args, one=True).get('total')
    member = _query(f'SELECT SUM(total_coin) AS total FROM members{common_where}', common_args, one=True).get('total')
    sc = _query(f'SELECT SUM(price) AS total FROM super_chat{common_where}', common_args, one=True).get('total')
    if gift:
        rows.append({'type': '礼物', 'value': float(gift) / 1000})
    if member:
        rows.append({'type': '上舰', 'value': float(member) / 1000})
    if sc:
        rows.append({'type': '醒目留言', 'value': float(sc)})
    return rows


async def get_active_danmaku_authors(filters: QueryFilters, limit: int) -> List[Dict[str, Any]]:
    where, args = _filters_where(filters, include_source=True)
    sql = (
        f'SELECT uid, author_name, COUNT(*) AS count FROM danmaku{where} '
        'GROUP BY uid, author_name ORDER BY count DESC LIMIT ?'
    )
    return await asyncio.to_thread(_query, sql, [*args, limit])


async def explore_danmaku(filters: QueryFilters, query_params: Dict[str, str]) -> Dict[str, Any]:
    return await asyncio.to_thread(_explore_danmaku_sync, filters, query_params)


def _explore_danmaku_sync(filters: QueryFilters, query_params: Dict[str, str]) -> Dict[str, Any]:
    limit = _limit(query_params.get('limit'), 50)
    offset = _offset(query_params.get('offset'))
    keyword = (query_params.get('keyword') or '').strip()[:64]
    uid = (query_params.get('uid') or '').strip()[:64]
    where, args = _filters_where(filters, include_source=True)
    clauses = []
    if keyword:
        clauses.append('content LIKE ?')
        args.append(f'%{keyword}%')
    if uid:
        clauses.append('uid = ?')
        args.append(uid)
    if clauses:
        where += (' AND ' if where else ' WHERE ') + ' AND '.join(clauses)

    total_row = _query(f'SELECT COUNT(*) AS total FROM danmaku{where}', args, one=True)
    data = _query(
        'SELECT id, room_id, timestamp, uid, author_name, content, translation, source '
        f'FROM danmaku{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?',
        [*args, limit, offset],
    )
    return {'total': total_row.get('total', 0) or 0, 'limit': limit, 'offset': offset, 'items': data}


async def explore_gifts(filters: QueryFilters, query_params: Dict[str, str]) -> Dict[str, Any]:
    return await asyncio.to_thread(_explore_gifts_sync, filters, query_params)


def _explore_gifts_sync(filters: QueryFilters, query_params: Dict[str, str]) -> Dict[str, Any]:
    limit = _limit(query_params.get('limit'), 50)
    offset = _offset(query_params.get('offset'))
    keyword = (query_params.get('keyword') or '').strip()[:64]
    uid = (query_params.get('uid') or '').strip()[:64]
    where, args = _filters_where(filters, include_source=True)
    clauses = []
    if keyword:
        clauses.append('gift_name LIKE ?')
        args.append(f'%{keyword}%')
    if uid:
        clauses.append('uid = ?')
        args.append(uid)
    if clauses:
        where += (' AND ' if where else ' WHERE ') + ' AND '.join(clauses)

    total_row = _query(f'SELECT COUNT(*) AS total FROM gifts{where}', args, one=True)
    data = _query(
        'SELECT id, room_id, timestamp, uid, author_name, gift_name, num, total_coin, source '
        f'FROM gifts{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?',
        [*args, limit, offset],
    )
    return {'total': total_row.get('total', 0) or 0, 'limit': limit, 'offset': offset, 'items': data}


def meta_from_filters(filters: QueryFilters, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'filtersApplied': {
            'room_id': filters.room_id,
            'from_ts': filters.from_ts,
            'to_ts': filters.to_ts,
            'source': filters.source,
        }
    }
    if extra:
        payload.update(extra)
    return payload
