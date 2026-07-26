# -*- coding: utf-8 -*-
"""
将 dycast 转发的 JSON 消息映射为注入队列项。

- kind=text：blcsdk.send_text
- kind=gift：blcsdk.send_gift（需主程序与插件 blcsdk ≥ 1.1）

消息结构与 dycast CastMethod / DyMessage 一致。
"""
from __future__ import annotations

import logging
import hashlib
import time
from typing import Any, Dict, List, Optional

from contract import UnifiedEvent

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


def _medal_from_nested_fans_club(fc: Any) -> tuple[int, str]:
    """user 上仍带 fansClub 嵌套（未走 dycast 扁平化）时的兜底。"""
    if not isinstance(fc, dict):
        return 0, ''
    candidates: List[Dict[str, Any]] = []
    data = fc.get('data')
    if isinstance(data, dict):
        candidates.append(data)
    pd = fc.get('preferData') or fc.get('prefer_data')
    if isinstance(pd, dict):
        for v in pd.values():
            if isinstance(v, dict):
                candidates.append(v)
    if not candidates:
        return 0, ''
    best = candidates[0]
    best_lv = int(best.get('level', 0) or 0)
    for c in candidates[1:]:
        try:
            lv = int(c.get('level', 0) or 0)
        except (TypeError, ValueError):
            lv = 0
        if lv > best_lv:
            best_lv = lv
            best = c
        elif lv == best_lv:
            bn = str(best.get('clubName', best.get('club_name', '')) or '').strip()
            cn = str(c.get('clubName', c.get('club_name', '')) or '').strip()
            if not bn and cn:
                best = c
    try:
        level = int(best.get('level', 0) or 0)
    except (TypeError, ValueError):
        level = 0
    name = str(
        best.get('clubName', best.get('club_name', '')) or ''
    ).strip()
    return max(0, level), name


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
    level = max(0, level)
    name = str(name or '').strip()
    if level <= 0 and not name:
        nl, nn = _medal_from_nested_fans_club(
            u.get('fans_club') or u.get('fansClub')
        )
        if nl > 0 or nn:
            level = max(level, nl)
            if not name:
                name = nn
    # 抖音粉丝团多数场景没有可用名称，统一兜底成固定文案，避免前端因空名不展示。
    if level > 0 and not name:
        name = '粉丝团'
    return level, name


def _gift_count(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def _gift_repeat_ended(gift: Optional[Dict[str, Any]]) -> bool:
    """抖音连击：过程帧无/0 repeatEnd，结束帧为非 0。只保留结束帧避免数量被前端累加翻倍。"""
    if not isinstance(gift, dict):
        return False
    raw = gift.get('repeatEnd', gift.get('repeat_end'))
    if raw is None:
        return False
    try:
        return int(raw) != 0
    except (TypeError, ValueError):
        return bool(raw)


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


def _first_non_negative_int(*raw_values: Any) -> int:
    for raw in raw_values:
        try:
            v = int(raw)
        except (TypeError, ValueError):
            continue
        if v >= 0:
            return v
    return 0


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


def _as_optional_non_empty_str(raw: Any) -> Optional[str]:
    text = str(raw or '').strip()
    return text or None


def _as_optional_non_negative_int(raw: Any) -> Optional[int]:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return v


def _pick_membership_fields(
    msg: Dict[str, Any],
    user: Optional[Dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """优先从 CastUser，再回落到消息根字段。"""
    sources: List[Dict[str, Any]] = []
    if isinstance(user, dict):
        sources.append(user)
    sources.append(msg)
    mtype: Optional[str] = None
    mname: Optional[str] = None
    for src in sources:
        if mtype is None:
            mtype = _as_optional_non_empty_str(src.get('membership_type', src.get('membershipType')))
        if mname is None:
            mname = _as_optional_non_empty_str(src.get('membership_name', src.get('membershipName')))
    return mtype, mname


def _is_star_guard(membership_type: Optional[str], membership_name: Optional[str]) -> bool:
    t = (membership_type or '').strip().lower()
    n = (membership_name or '').strip()
    if t == 'star_guard':
        return True
    if '星守护' in n:
        return True
    return False


def _base_douyin_platform_meta(msg: Dict[str, Any], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    medal_level, medal_name = _medal_from_user(user if isinstance(user, dict) else None)
    membership_type, membership_name = _pick_membership_fields(msg, user)
    return {
        'platform': 'douyin',
        'room_id': str(msg.get('roomId') or '').strip(),
        'room_num': str(msg.get('roomNum') or '').strip(),
        'membership_type': membership_type,
        'membership_name': membership_name,
        'fans_badge_level': _as_optional_non_negative_int(medal_level),
        'fans_badge_name': _as_optional_non_empty_str(medal_name),
    }


def _base_actor(user: Optional[Dict[str, Any]]) -> Dict[str, str]:
    return {
        'id': _user_id(user),
        'name': _user_name(user) or '抖音用户',
        'avatar_url': _user_avatar(user),
    }


def _to_unified_chat_event(msg: Dict[str, Any]) -> Optional[UnifiedEvent]:
    user = msg.get('user') if isinstance(msg.get('user'), dict) else None
    content = msg.get('content')
    if content is None or str(content).strip() == '':
        content = _flatten_rtf(msg.get('rtfContent'))
    text = str(content or '').strip()
    if not text:
        return None

    raw_ts = msg.get('timestamp', msg.get('ts'))
    try:
        ts = int(raw_ts)
    except (TypeError, ValueError):
        ts = int(time.time() * 1000)

    event_id = str(msg.get('id') or '').strip()
    if not event_id:
        fallback_basis = '\x1f'.join([
            _user_id(user),
            str(ts),
            str(msg.get('roomId') or '').strip(),
            str(msg.get('roomNum') or '').strip(),
            text,
        ])
        event_id = f'{CHAT}:{hashlib.sha1(fallback_basis.encode("utf-8")).hexdigest()[:16]}'

    return {
        'event_id': event_id,
        'platform': 'douyin',
        'event_type': 'chat.message',
        'ts': ts,
        'actor': _base_actor(user),
        'content': {
            'text': text,
        },
        'monetization': None,
        'fan_identity': None,
        'platform_meta': _base_douyin_platform_meta(msg, user),
    }


def _to_unified_text_event(msg: Dict[str, Any], *, event_type: str, default_text: str) -> Optional[UnifiedEvent]:
    user = msg.get('user') if isinstance(msg.get('user'), dict) else None
    text = str(msg.get('content') or default_text).strip()
    if not text:
        return None
    raw_ts = msg.get('timestamp', msg.get('ts'))
    try:
        ts = int(raw_ts)
    except (TypeError, ValueError):
        ts = int(time.time() * 1000)
    event_id = str(msg.get('id') or '').strip()
    if not event_id:
        fallback_basis = '\x1f'.join([
            event_type,
            _user_id(user),
            str(ts),
            str(msg.get('roomId') or '').strip(),
            str(msg.get('roomNum') or '').strip(),
            text,
        ])
        event_id = f'{event_type}:{hashlib.sha1(fallback_basis.encode("utf-8")).hexdigest()[:16]}'
    return {
        'event_id': event_id,
        'platform': 'douyin',
        'event_type': event_type,
        'ts': ts,
        'actor': _base_actor(user),
        'content': {'text': text},
        'monetization': None,
        'fan_identity': None,
        'platform_meta': _base_douyin_platform_meta(msg, user),
    }


def _to_unified_gift_event(msg: Dict[str, Any]) -> UnifiedEvent:
    user = msg.get('user') if isinstance(msg.get('user'), dict) else None
    gift = msg.get('gift') if isinstance(msg.get('gift'), dict) else {}
    gname = str(gift.get('name') or '礼物').strip()
    count = _gift_count(gift.get('count', '1'))
    # 不同来源字段命名不一致，尽量兜底提取礼物价值。
    # blivechat 前端：price = totalCoin/1000，即 totalCoin 为「元×1000」（毫元）。
    # dycast 把单礼物抖币价放在 gift.price（等同 GiftStruct.diamondCount），不在 diamondCount 根字段。
    total_coin = _first_non_negative_int(
        msg.get('totalCoin'),
        msg.get('total_coin'),
        msg.get('giftTotalCoin'),
        msg.get('gift_total_coin'),
        gift.get('totalCoin'),
        gift.get('total_coin'),
    )
    if total_coin <= 0:
        unit_diamond = _first_non_negative_int(
            gift.get('price'),
            msg.get('price'),
            gift.get('diamondCount'),
            gift.get('diamond_count'),
            msg.get('diamondCount'),
            msg.get('diamond_count'),
        )
        if unit_diamond > 0 and count > 0:
            # 抖币常见口径 ≈0.1 元/枚 → 1 抖币对应毫元 100；行总价 = 单价抖币×数量
            total_coin = unit_diamond * count * 100
    total_free_coin = _first_non_negative_int(
        msg.get('totalFreeCoin'),
        msg.get('total_free_coin'),
        msg.get('giftTotalFreeCoin'),
        msg.get('gift_total_free_coin'),
        gift.get('totalFreeCoin'),
        gift.get('total_free_coin'),
    )
    raw_ts = msg.get('timestamp', msg.get('ts'))
    try:
        ts = int(raw_ts)
    except (TypeError, ValueError):
        ts = int(time.time() * 1000)
    event_id = str(msg.get('id') or '').strip()
    if not event_id:
        fallback_basis = '\x1f'.join([
            GIFT,
            _user_id(user),
            str(ts),
            str(msg.get('roomId') or '').strip(),
            str(msg.get('roomNum') or '').strip(),
            str(gift.get('id') or '').strip(),
            gname,
            str(count),
        ])
        event_id = f'{GIFT}:{hashlib.sha1(fallback_basis.encode("utf-8")).hexdigest()[:16]}'

    meta = _base_douyin_platform_meta(msg, user)
    return {
        'event_id': event_id,
        'platform': 'douyin',
        'event_type': 'gift.send',
        'ts': ts,
        'actor': _base_actor(user),
        'content': {'text': f'赠送了 {gname} x{count}'},
        'monetization': {
            'gift_name': gname,
            'gift_count': count,
            'gift_id': str(gift.get('id') or '').strip(),
            'gift_icon_url': str(gift.get('icon') or '').strip(),
            'total_coin': total_coin,
            'total_free_coin': total_free_coin,
        },
        'fan_identity': None,
        'platform_meta': meta,
    }


def _unified_event_to_inject_item(
    event: UnifiedEvent,
    *,
    content_prefix: str,
    native_gift: bool,
) -> Optional[Dict[str, Any]]:
    event_type = str(event.get('event_type') or '').strip()
    if event_type not in {
        'chat.message',
        'like.action',
        'member.join',
        'social.follow',
        'gift.send',
    }:
        return None

    p = (content_prefix or '').strip()
    actor = event.get('actor', {})
    meta = event.get('platform_meta') if isinstance(event.get('platform_meta'), dict) else {}
    monetization = event.get('monetization') if isinstance(event.get('monetization'), dict) else {}
    fan_identity = event.get('fan_identity') if isinstance(event.get('fan_identity'), dict) else {}
    medal_level = _as_optional_non_negative_int(meta.get('fans_badge_level'))
    medal_name = str(meta.get('fans_badge_name') or '')
    membership_type = str(meta.get('membership_type') or '').strip().lower()
    membership_name = str(meta.get('membership_name') or '').strip()
    # blcsdk当前无平台扩展字段，这里通过稳定前缀传递来源平台，前端据此分流样式。
    raw_uid = str(actor.get('id') or '')
    uid = f'douyin:{raw_uid}' if raw_uid else 'douyin:'
    # 仅星守护映射为舰长同级 privilege（GuardLevel.LV1=3）；其它抖音身份不插队。
    guard_level = 3 if _is_star_guard(membership_type, membership_name) else 0
    identity_ext = {
        'platform': 'douyin',
        'platform_meta': {
            'platform': 'douyin',
            'room_id': str(meta.get('room_id') or ''),
            'room_num': str(meta.get('room_num') or ''),
            'membership_type': membership_type or None,
            'membership_name': membership_name or None,
            'fans_badge_level': medal_level,
            'fans_badge_name': medal_name or None,
        },
        'fan_identity': {
            'level': medal_level or 0,
            'badge_name': medal_name or '',
            **fan_identity,
        },
    }

    if event_type == 'gift.send' and native_gift:
        gift_name = str(monetization.get('gift_name') or meta.get('gift_name') or '礼物').strip()
        gift_count = _gift_count(monetization.get('gift_count', meta.get('gift_count', 1)))
        gift_id_raw = monetization.get('gift_id', meta.get('gift_id'))
        gift_icon_url = str(monetization.get('gift_icon_url') or meta.get('gift_icon_url') or '').strip()
        return {
            'kind': 'gift',
            'gift_name': gift_name,
            'num': gift_count,
            'author_name': str(actor.get('name') or '抖音用户'),
            'uid': uid,
            'avatar_url': str(actor.get('avatar_url') or ''),
            'gift_id': _gift_id_numeric(gift_id_raw),
            'gift_icon_url': gift_icon_url,
            'total_coin': _first_non_negative_int(monetization.get('total_coin'), meta.get('total_coin')),
            'total_free_coin': _first_non_negative_int(
                monetization.get('total_free_coin'),
                meta.get('total_free_coin'),
            ),
            'guard_level': guard_level,
            'medal_level': medal_level or 0,
            'medal_name': medal_name,
            'identity_ext': identity_ext,
        }

    content = event.get('content') or {}
    text = str(content.get('text') or '').strip()
    if not text:
        return None
    if p and not text.startswith(p):
        text = f'{p} {text}'.strip()
    return {
        'kind': 'text',
        'content': text,
        'author_name': str(actor.get('name') or '抖音用户'),
        'uid': uid,
        'avatar_url': str(actor.get('avatar_url') or ''),
        'guard_level': guard_level,
        'medal_level': medal_level or 0,
        'medal_name': medal_name,
        'identity_ext': identity_ext,
    }


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
        event = _to_unified_chat_event(msg)
        if event is None:
            return None
        return _unified_event_to_inject_item(
            event,
            content_prefix=content_prefix,
            native_gift=native_gift,
        )

    if method == EMOJI_CHAT:
        url = msg.get('content')
        medal_level, medal_name = _medal_from_user(user)
        content_type = 0
        content_type_params: List[Any] = []
        if url and str(url).startswith('http'):
            text = '[表情]'
            content_type = 1
            content_type_params = [str(url).strip()]
        else:
            text = str(url or '[表情]').strip() or '[表情]'
        return {
            'kind': 'text',
            'content': prefixed(text),
            'author_name': author_name,
            'uid': uid,
            'avatar_url': avatar_url,
            'content_type': content_type,
            'content_type_params': content_type_params,
            'identity_ext': {
                'platform': 'douyin',
                'platform_meta': {
                    'platform': 'douyin',
                    'room_id': str(msg.get('roomId') or '').strip(),
                    'room_num': str(msg.get('roomNum') or '').strip(),
                },
                'fan_identity': {
                    'level': _as_optional_non_negative_int(medal_level) or 0,
                    'badge_name': _as_optional_non_empty_str(medal_name) or '',
                },
            },
        }

    if method == GIFT and include_gift:
        gift = msg.get('gift') if isinstance(msg.get('gift'), dict) else None
        # 连击过程帧与结束帧都会带相同累计数量；前端 mergeGift 对 num 做累加。
        # 只转发 repeatEnd 结束帧，保证「送 1 个」只注入一次最终数量。
        if not _gift_repeat_ended(gift):
            return None
        event = _to_unified_gift_event(msg)
        return _unified_event_to_inject_item(
            event,
            content_prefix=content_prefix,
            native_gift=native_gift,
        )

    if method == LIKE and include_like:
        event = _to_unified_text_event(
            msg,
            event_type='like.action',
            default_text='为主播点赞',
        )
        if event is None:
            return None
        return _unified_event_to_inject_item(
            event,
            content_prefix=content_prefix,
            native_gift=native_gift,
        )

    if method == MEMBER and include_member:
        event = _to_unified_text_event(
            msg,
            event_type='member.join',
            default_text='进入直播间',
        )
        if event is None:
            return None
        return _unified_event_to_inject_item(
            event,
            content_prefix=content_prefix,
            native_gift=native_gift,
        )

    if method == SOCIAL and include_social:
        event = _to_unified_text_event(
            msg,
            event_type='social.follow',
            default_text='关注了主播',
        )
        if event is None:
            return None
        return _unified_event_to_inject_item(
            event,
            content_prefix=content_prefix,
            native_gift=native_gift,
        )

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
