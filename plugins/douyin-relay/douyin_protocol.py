from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger('douyin-relay.' + __name__)


class DouyinProtocol:
    """协议层：统一解析 dycast relay 输入到消息语义。"""

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

    @staticmethod
    def _is_live_info_object(data: Dict[str, Any]) -> bool:
        if 'method' in data and data.get('method'):
            return False
        return 'roomId' in data or 'roomNum' in data
