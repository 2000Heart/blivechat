# -*- coding: utf-8 -*-
"""
将 dycast 转发的 JSON 消息映射为注入队列项。

- kind=text：blcsdk.send_text
- kind=gift：blcsdk.send_gift（需主程序与插件 blcsdk ≥ 1.1）

消息结构与 dycast CastMethod / DyMessage 一致。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('douyin-relay.' + __name__)

# 与 dycast CastMethod 字符串一致
CHAT = 'WebcastChatMessage'
GIFT = 'WebcastGiftMessage'
LIKE = 'WebcastLikeMessage'
MEMBER = 'WebcastMemberMessage'
SOCIAL = 'WebcastSocialMessage'
EMOJI_CHAT = 'WebcastEmojiChatMessage'
ROOM_USER_SEQ = 'WebcastRoomUserSeqMessage'
CONTROL = 'WebcastControlMessage'
ROOM_RANK = 'WebcastRoomRankMessage'
ROOM_STATS = 'WebcastRoomStatsMessage'
FANSCLUB = 'WebcastFansclubMessage'
ROOM_DATA_SYNC = 'WebcastRoomDataSyncMessage'
CUSTOM = 'CustomMessage'


def _user_name(u: Optional[Dict[str, Any]]) -> str:
    if not u:
        return ''
    return str(u.get('name') or '').strip()


def _user_id(u: Optional[Dict[str, Any]]) -> str:
    if not u:
        return ''
    return str(u.get('id') or '').strip()


def _user_avatar(u: Optional[Dict[str, Any]]) -> str:
    if not u:
        return ''
    return str(u.get('avatar') or '').strip()


def _medal_from_user(u: Optional[Dict[str, Any]]) -> tuple[int, str]:
    """粉丝团 → blivechat 勋章位：medal_level / medal_name（兼容 camelCase）。"""
    if not u:
        return 0, ''
    raw_lv = u.get('medal_level', u.get('medalLevel', 0))
    try:
        level = int(raw_lv)
    except (TypeError, ValueError):
        level = 0
    name = u.get('medal_name', u.get('medalName', ''))
    return max(0, level), str(name or '').strip()


def _gift_count(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def _gift_id_numeric(raw: Any) -> int:
    """抖礼物 id 可能很长，压缩为 31 位整数供前端使用。"""
    if raw is None:
        return 0
    s = str(raw).strip()
    if not s:
        return 0
    if s.isdigit():
        return int(s) % (2 ** 31) or 0
    return abs(hash(s)) % (2 ** 31) or 1


def _flatten_rtf(rtf: Optional[List[Dict[str, Any]]]) -> str:
    if not rtf:
        return ''
    parts: List[str] = []
    for piece in rtf:
        t = piece.get('type')
        text = piece.get('text')
        url = piece.get('url')
        if text:
            parts.append(str(text))
        elif url:
            parts.append('[表情]')
    return ''.join(parts).strip()


def map_dy_payload(
    msg: Dict[str, Any],
    *,
    content_prefix: str,
    include_gift: bool,
    native_gift: bool,
    include_like: bool,
    include_member: bool,
    include_social: bool,
) -> Optional[Dict[str, Any]]:
    """
    返回注入队列字典，或 None 表示跳过。

    kind=text：content, author_name, uid, avatar_url
    kind=gift：上述 + medal_level、medal_name（粉丝团，来自 user）
    """
    method = msg.get('method')
    msg_id = msg.get('id')
    user = msg.get('user') if isinstance(msg.get('user'), dict) else None
    author_name = _user_name(user) or '抖音用户'
    uid = _user_id(user)
    avatar_url = _user_avatar(user)

    def prefixed(text: str) -> str:
        p = (content_prefix or '').strip()
        if not p:
            return text
        if text.startswith(p):
            return text
        return f'{p} {text}'.strip()

    if method == CHAT:
        content = msg.get('content')
        if content is None or str(content).strip() == '':
            content = _flatten_rtf(msg.get('rtfContent'))
        if not content:
            return None
        return {
            'kind': 'text',
            'content': prefixed(str(content)),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    if method == EMOJI_CHAT:
        url = msg.get('content')
        if url and str(url).startswith('http'):
            text = '[会员表情]'
        else:
            text = str(url or '[表情]').strip() or '[表情]'
        return {
            'kind': 'text',
            'content': prefixed(text),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    if method == GIFT and include_gift:
        gift = msg.get('gift') if isinstance(msg.get('gift'), dict) else {}
        gname = str(gift.get('name') or '礼物').strip()
        count = _gift_count(gift.get('count', '1'))
        if native_gift:
            ml, mn = _medal_from_user(user)
            return {
                'kind': 'gift',
                'gift_name': gname,
                'num': count,
                'author_name': author_name,
                'uid': uid,
                'avatar_url': avatar_url,
                'gift_id': _gift_id_numeric(gift.get('id')),
                'gift_icon_url': str(gift.get('icon') or '').strip(),
                'total_coin': 0,
                'total_free_coin': 0,
                'medal_level': ml,
                'medal_name': mn,
            }
        text = f'赠送了 {gname} x{count}'
        return {
            'kind': 'text',
            'content': prefixed(text),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    if method == LIKE and include_like:
        text = msg.get('content') or '为主播点赞'
        return {
            'kind': 'text',
            'content': prefixed(str(text)),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    if method == MEMBER and include_member:
        text = msg.get('content') or '进入直播间'
        return {
            'kind': 'text',
            'content': prefixed(str(text)),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    if method == SOCIAL and include_social:
        text = msg.get('content') or '关注了主播'
        return {
            'kind': 'text',
            'content': prefixed(str(text)),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
        }

    return None


def is_live_info_object(data: Dict[str, Any]) -> bool:
    """dycast 连接成功后首包：直播间信息对象（非数组）。"""
    if not isinstance(data, dict):
        return False
    if 'method' in data and data.get('method'):
        return False
    return 'roomId' in data or 'roomNum' in data


def parse_incoming_json(raw: str) -> tuple[str, Any]:
    """
    返回 (kind, payload)
    kind: 'live_info' | 'messages' | 'unknown'
    """
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning('Invalid JSON from dycast client')
        return 'unknown', None

    if isinstance(data, dict):
        if is_live_info_object(data):
            return 'live_info', data
        if 'method' in data:
            return 'messages', [data]
        logger.debug('Ignored dict payload keys=%s', list(data.keys())[:10])
        return 'unknown', data

    if isinstance(data, list):
        return 'messages', data

    return 'unknown', data
