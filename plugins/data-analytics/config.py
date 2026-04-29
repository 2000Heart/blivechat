# -*- coding: utf-8 -*-
import json
import os
import secrets
from typing import Any, Dict

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(BASE_PATH, 'data')
DB_PATH = os.path.join(DATA_PATH, 'analytics.db')
DB_V2_PATH = os.path.join(DATA_PATH, 'analytics_v2.db')
DB_BACKUP_PATH = os.path.join(DATA_PATH, 'analytics.db.bak')
LOG_PATH = os.path.join(BASE_PATH, 'log')
WEB_BASE_PATH = os.path.join(BASE_PATH, 'web')
WEB_DIST_PATH = os.path.join(WEB_BASE_PATH, 'dist')
WEB_CONFIG_PATH = os.path.join(DATA_PATH, 'web_config.json')
RECONCILE_EPSILON = 1e-6

DEFAULT_WEB_HOST = '127.0.0.1'
DEFAULT_WEB_PORT = 18766

# 确保目录存在
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(LOG_PATH, exist_ok=True)


def _read_web_config() -> Dict[str, Any]:
    if not os.path.exists(WEB_CONFIG_PATH):
        return {}
    try:
        with open(WEB_CONFIG_PATH, encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def _write_web_config(raw: Dict[str, Any]) -> None:
    with open(WEB_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def _int_or_default(v: Any, default: int) -> int:
    try:
        iv = int(v)
        if iv <= 0:
            return default
        return iv
    except (TypeError, ValueError):
        return default


def _str_or_default(v: Any, default: str) -> str:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


_raw_web_config = _read_web_config()
WEB_HOST = _str_or_default(_raw_web_config.get('host'), DEFAULT_WEB_HOST)
WEB_PORT = _int_or_default(_raw_web_config.get('port'), DEFAULT_WEB_PORT)
ADMIN_TOKEN = _str_or_default(_raw_web_config.get('adminToken'), secrets.token_hex(16))

_write_web_config({
    'host': WEB_HOST,
    'port': WEB_PORT,
    'adminToken': ADMIN_TOKEN,
})

WEB_ROOT = WEB_DIST_PATH if os.path.isdir(WEB_DIST_PATH) else WEB_BASE_PATH
WEB_INDEX_PATH = os.path.join(WEB_ROOT, 'index.html')


def build_admin_url() -> str:
    return f'http://{WEB_HOST}:{WEB_PORT}/?token={ADMIN_TOKEN}'

