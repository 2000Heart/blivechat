from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Tuple

logger = logging.getLogger('douyin-relay.' + __name__)

CHAT_METHOD = 'WebcastChatMessage'


class DouyinProtocol:
    """M1 最小协议层：统一解析 relay/direct 输入到同一消息语义。"""

    def parse_raw_payload(self, raw: str) -> Tuple[str, Any]:
        """
        返回 (kind, payload):
        - live_info: dict
        - messages: list[dict]
        - unknown: Any
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning('Invalid JSON payload for douyin protocol')
            return 'unknown', None

        if isinstance(data, dict):
            if self._is_live_info_object(data):
                return 'live_info', data
            if 'method' in data:
                return 'messages', [data]
            return 'unknown', data

        if isinstance(data, list):
            return 'messages', data

        return 'unknown', data

    def build_stub_chat_raw(self, *, seq: int, room_id: str) -> str:
        now_ms = int(time.time() * 1000)
        payload: Dict[str, Any] = {
            'id': f'direct-stub-{seq}',
            'method': CHAT_METHOD,
            'timestamp': now_ms,
            'roomId': room_id or '',
            'roomNum': room_id or '',
            'content': f'direct stub message #{seq}',
            'user': {
                'id': f'direct_user_{seq % 3}',
                'name': f'DirectStub{seq % 3}',
                'avatar': '',
            },
        }
        return json.dumps([payload], ensure_ascii=False)

    @staticmethod
    def _is_live_info_object(data: Dict[str, Any]) -> bool:
        if 'method' in data and data.get('method'):
            return False
        return 'roomId' in data or 'roomNum' in data
