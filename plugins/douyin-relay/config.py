# -*- coding: utf-8 -*-
import configparser
import logging
import os
import shutil
from typing import *

logger = logging.getLogger('douyin-relay.' + __name__)

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
LOG_PATH = os.path.join(BASE_PATH, 'log')
DATA_PATH = os.path.join(BASE_PATH, 'data')

CONFIG_PATH_LIST = [
    os.path.join(DATA_PATH, 'config.ini'),
    os.path.join(DATA_PATH, 'config.example.ini'),
]

_config: Optional['AppConfig'] = None


def init():
    os.makedirs(LOG_PATH, exist_ok=True)
    os.makedirs(DATA_PATH, exist_ok=True)
    if reload():
        return
    logger.warning('Using default config (copy data/config.example.ini to data/config.ini)')
    global _config
    _config = AppConfig()


def reload() -> bool:
    config_path = ''
    for path in CONFIG_PATH_LIST:
        if os.path.exists(path):
            config_path = path
            break
    if config_path == '':
        return False
    config = AppConfig()
    if not config.load(config_path):
        return False
    global _config
    _config = config
    return True


def get_config() -> 'AppConfig':
    assert _config is not None
    return _config


def normalized_ws_path(ws_path: str) -> str:
    p = (ws_path or '/').strip()
    if not p.startswith('/'):
        p = '/' + p
    return p.rstrip('/') or '/'


def get_dycast_relay_ws_url() -> str:
    """
    供 dycast「WS地址」填写的 WebSocket URL。
    监听 0.0.0.0 / :: 时同机填写使用 127.0.0.1。
    """
    cfg = get_config()
    host = (cfg.listen_host or '').strip()
    if host in ('0.0.0.0', '::', ''):
        host = '127.0.0.1'
    p = normalized_ws_path(cfg.ws_path)
    return f'ws://{host}:{cfg.listen_port}{p}'


class AppConfig:
    """插件配置（见 data/config.example.ini）"""

    def __init__(self):
        self.mode = 'relay'
        self.relay_backend = 'legacy'
        self.listen_host = '127.0.0.1'
        self.listen_port = 18765
        self.ws_path = '/'
        self.sidecar_host = '127.0.0.1'
        self.sidecar_port = 5173
        self.sidecar_start_timeout_seconds = 20
        self.sidecar_node_exe = 'node'
        self.sidecar_node_cmd = '{node} ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port {port}'
        self.douyin_room_id = ''
        self.douyin_cookie = ''
        self.content_prefix = '[抖音]'
        self.include_gift = True
        self.native_gift = True
        self.include_like = False
        self.include_member = True
        self.include_social = True
        self.dedup_ttl_seconds = 120
        self.dedup_max_size = 8000
        self.inject_queue_max = 500
        self.inject_concurrency = 8

    def load(self, path: str) -> bool:
        try:
            cp = configparser.ConfigParser(interpolation=None)
            cp.read(path, encoding='utf-8-sig')
            sec = cp['relay'] if cp.has_section('relay') else None
            if sec is None:
                logger.warning('No [relay] section in config, using defaults')
                return True
            self.mode = sec.get('mode', self.mode).strip().lower() or self.mode
            self.relay_backend = sec.get('relay_backend', self.relay_backend).strip().lower() or self.relay_backend
            self.listen_host = sec.get('listen_host', self.listen_host)
            self.listen_port = sec.getint('listen_port', self.listen_port)
            self.ws_path = sec.get('ws_path', self.ws_path)
            self.sidecar_host = sec.get('sidecar_host', self.sidecar_host)
            self.sidecar_port = sec.getint('sidecar_port', self.sidecar_port)
            self.sidecar_start_timeout_seconds = sec.getint(
                'sidecar_start_timeout_seconds', self.sidecar_start_timeout_seconds
            )
            self.sidecar_node_exe = sec.get('sidecar_node_exe', self.sidecar_node_exe)
            self.sidecar_node_cmd = sec.get('sidecar_node_cmd', self.sidecar_node_cmd)
            self.douyin_room_id = sec.get('douyin_room_id', self.douyin_room_id)
            self.douyin_cookie = sec.get('douyin_cookie', self.douyin_cookie)
            self.content_prefix = sec.get('content_prefix', self.content_prefix)
            self.include_gift = sec.getboolean('include_gift', self.include_gift)
            self.native_gift = sec.getboolean('native_gift', self.native_gift)
            self.include_like = sec.getboolean('include_like', self.include_like)
            self.include_member = sec.getboolean('include_member', self.include_member)
            self.include_social = sec.getboolean('include_social', self.include_social)
            self.dedup_ttl_seconds = sec.getint('dedup_ttl_seconds', self.dedup_ttl_seconds)
            self.dedup_max_size = sec.getint('dedup_max_size', self.dedup_max_size)
            self.inject_queue_max = sec.getint('inject_queue_max', self.inject_queue_max)
            self.inject_concurrency = sec.getint('inject_concurrency', self.inject_concurrency)
            if self.mode != 'relay':
                logger.warning('Unknown mode=%s, fallback to relay', self.mode)
                self.mode = 'relay'
            if self.relay_backend not in ('legacy', 'sidecar', 'native'):
                logger.warning('Unknown relay_backend=%s, fallback to legacy', self.relay_backend)
                self.relay_backend = 'legacy'
        except Exception:
            logger.exception('Failed to load config:')
            return False
        return True


def _preferred_config_path() -> str:
    return os.path.join(DATA_PATH, 'config.ini')


def ensure_config_ini_exists() -> str:
    cfg_path = _preferred_config_path()
    if os.path.exists(cfg_path):
        return cfg_path
    example_path = os.path.join(DATA_PATH, 'config.example.ini')
    if os.path.exists(example_path):
        shutil.copyfile(example_path, cfg_path)
        return cfg_path
    cp = configparser.ConfigParser(interpolation=None)
    cp['relay'] = {}
    with open(cfg_path, 'w', encoding='utf-8') as f:
        cp.write(f)
    return cfg_path


def update_relay_config_values(values: Dict[str, str]) -> bool:
    """
    更新 data/config.ini 中 [relay] 配置并立即重载内存配置。
    """
    try:
        cfg_path = ensure_config_ini_exists()
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(cfg_path, encoding='utf-8-sig')
        if not cp.has_section('relay'):
            cp.add_section('relay')
        sec = cp['relay']
        for k, v in values.items():
            sec[str(k)] = str(v)
        with open(cfg_path, 'w', encoding='utf-8') as f:
            cp.write(f)
    except Exception:
        logger.exception('Failed to update relay config values')
        return False
    return reload()
