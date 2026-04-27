from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class DycastBridgeClient:
    def __init__(self, host: str, port: int, timeout_seconds: float = 5.0):
        self._base = f'http://{host}:{port}'
        self._timeout = timeout_seconds

    def status(self) -> Dict[str, Any]:
        return self._request_json('GET', '/__api/dycast/control/status')

    def connect(self, room_num: str, relay_ws_url: str, raw_headers: str = '') -> Dict[str, Any]:
        payload = {
            'roomNum': room_num,
            'relayUrl': relay_ws_url,
            'rawHeaders': raw_headers,
            'autoReconnect': True,
        }
        return self._request_json('POST', '/__api/dycast/control/connect', payload)

    def disconnect(self) -> Dict[str, Any]:
        return self._request_json('POST', '/__api/dycast/control/disconnect', {})

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = None
        headers = {'Accept': 'application/json'}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json; charset=utf-8'
        req = urllib.request.Request(self._base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'HTTP {e.code} {path}: {body}') from e
        except Exception as e:
            raise RuntimeError(f'Request failed {method} {path}: {e}') from e
