# -*- coding: utf-8 -*-
import json
import os
import secrets
from typing import Any, Dict

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(BASE_PATH, 'data')
MEDIA_PATH = os.path.join(DATA_PATH, 'media')
LOG_PATH = os.path.join(BASE_PATH, 'log')
ADMIN_PATH = os.path.join(BASE_PATH, 'admin')
OVERLAY_PATH = os.path.join(BASE_PATH, 'overlay')

WEB_CONFIG_PATH = os.path.join(DATA_PATH, 'web_config.json')
SETTINGS_PATH = os.path.join(DATA_PATH, 'settings.json')

DEFAULT_WEB_HOST = '127.0.0.1'
DEFAULT_WEB_PORT = 18770

# 允许上传的媒体类型
ALLOWED_MEDIA_EXTS = {
    '.mp4': 'video',
    '.webm': 'video',
    '.mov': 'video',
    '.png': 'image',
    '.jpg': 'image',
    '.jpeg': 'image',
    '.webp': 'image',
    '.gif': 'gif',
}

# 确保目录存在
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(MEDIA_PATH, exist_ok=True)
os.makedirs(LOG_PATH, exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def _write_json(path: str, raw: Dict[str, Any]) -> None:
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


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


_raw_web_config = _read_json(WEB_CONFIG_PATH)
WEB_HOST = _str_or_default(_raw_web_config.get('host'), DEFAULT_WEB_HOST)
WEB_PORT = _int_or_default(_raw_web_config.get('port'), DEFAULT_WEB_PORT)
ADMIN_TOKEN = _str_or_default(_raw_web_config.get('adminToken'), secrets.token_hex(16))

_write_json(WEB_CONFIG_PATH, {
    'host': WEB_HOST,
    'port': WEB_PORT,
    'adminToken': ADMIN_TOKEN,
})


def build_admin_url() -> str:
    return f'http://{WEB_HOST}:{WEB_PORT}/?token={ADMIN_TOKEN}'


def build_overlay_url() -> str:
    return f'http://{WEB_HOST}:{WEB_PORT}/overlay?token={ADMIN_TOKEN}'
