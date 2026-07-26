#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import json
import logging.handlers
import os
import signal
import sys
from typing import *

def _inject_project_root_for_local_packages() -> None:
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, 'blcsdk')):
            if cur not in sys.path:
                sys.path.append(cur)
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


_inject_project_root_for_local_packages()

import blcsdk
from cachetools import TTLCache

import config
from douyin_protocol import DouyinProtocol
import listener
import mapper
import admin_ui
from injector import Injector
from relay_server import DouyinRelayServer
from runtime_manager import DycastRuntimeManager, SidecarRuntimeConfig

logger = logging.getLogger('douyin-relay')

shut_down_event: Optional[asyncio.Event] = None
_dedup: Optional[TTLCache] = None
_injector: Optional[Injector] = None
_relay: Optional[DouyinRelayServer] = None
_protocol: Optional[DouyinProtocol] = None
_sidecar: Optional[DycastRuntimeManager] = None


def _notify_admin_status_changed() -> None:
    try:
        admin_ui.notify_status_changed()
    except Exception:
        logger.exception('notify admin status changed failed')


def _resolve_sidecar_node_exe(cfg: config.AppConfig, dycast_path: str) -> str:
    raw = (cfg.sidecar_node_exe or '').strip() or 'node'
    if os.path.isabs(raw) and os.path.exists(raw):
        return raw

    # 优先使用 dycast 内置的便携 Node（用于打包分发）
    # 支持结构：
    # - dycast/.node/node.exe
    # - dycast/.node/bin/node
    # - dycast/.node/win-x64/node.exe
    # - dycast/.node/darwin-arm64/bin/node
    # - dycast/.node/darwin-x64/bin/node
    candidates = []
    if os.name == 'nt':
        candidates.extend(
            [
                os.path.join(dycast_path, '.node', 'win-x64', 'node.exe'),
                os.path.join(dycast_path, '.node', 'win-arm64', 'node.exe'),
                os.path.join(dycast_path, '.node', 'node.exe'),
                os.path.join(dycast_path, 'node', 'node.exe'),
            ]
        )
    else:
        # 优先按当前架构选择
        machine = (os.uname().machine or '').lower() if hasattr(os, 'uname') else ''
        if machine in ('arm64', 'aarch64'):
            candidates.append(os.path.join(dycast_path, '.node', 'darwin-arm64', 'bin', 'node'))
        elif machine in ('x86_64', 'amd64'):
            candidates.append(os.path.join(dycast_path, '.node', 'darwin-x64', 'bin', 'node'))
        candidates.extend(
            [
                os.path.join(dycast_path, '.node', 'darwin-arm64', 'bin', 'node'),
                os.path.join(dycast_path, '.node', 'darwin-x64', 'bin', 'node'),
                os.path.join(dycast_path, '.node', 'bin', 'node'),
                os.path.join(dycast_path, 'node', 'bin', 'node'),
            ]
        )
    for p in candidates:
        if os.path.isfile(p):
            return p
    return raw


async def main():
    try:
        await init()
        await run()
    finally:
        await shut_down()
    return 0


async def init():
    init_signal_handlers()
    init_logging()
    config.init()

    await blcsdk.init()
    if not blcsdk.is_sdk_version_compatible():
        raise RuntimeError('SDK version is not compatible')

    listener.init()
    admin_ui.bind_plugin_event_loop(asyncio.get_running_loop())

    global _dedup, _injector, _relay, _protocol, _sidecar
    cfg = config.get_config()
    _dedup = TTLCache(maxsize=cfg.dedup_max_size, ttl=cfg.dedup_ttl_seconds)
    _injector = Injector(cfg.inject_queue_max, cfg.inject_concurrency)
    await _injector.start()
    _protocol = DouyinProtocol()
    admin_ui.set_status_provider(get_runtime_status)
    admin_ui.set_action_handler(handle_admin_action)
    _notify_admin_status_changed()

    _relay = DouyinRelayServer(
        cfg.listen_host,
        cfg.listen_port,
        cfg.ws_path,
        on_text=_on_ws_text,
    )
    await _relay.start()
    if cfg.relay_backend == 'sidecar':
        try:
            # 优先使用插件内置 dycast（plugins/douyin-relay/dycast）
            bundled_dycast_path = os.path.join(config.BASE_PATH, 'dycast')
            # 兼容历史开发目录结构（blivechat 同级 dycast）
            legacy_dycast_path = os.path.abspath(
                os.path.join(config.BASE_PATH, '..', '..', '..', 'dycast')
            )
            dycast_path = bundled_dycast_path if os.path.isdir(bundled_dycast_path) else legacy_dycast_path
            node_exe = _resolve_sidecar_node_exe(cfg, dycast_path)
            _sidecar = DycastRuntimeManager(
                SidecarRuntimeConfig(
                    host=cfg.sidecar_host,
                    port=cfg.sidecar_port,
                    start_timeout_seconds=cfg.sidecar_start_timeout_seconds,
                    node_exe=node_exe,
                    node_cmd=cfg.sidecar_node_cmd,
                    dycast_path=dycast_path,
                )
            )
            await _sidecar.start()
            relay_ws = config.get_dycast_relay_ws_url()
            room_id = (cfg.douyin_room_id or '').strip()
            if room_id:
                _sidecar.bridge_client().connect(
                    room_num=room_id,
                    relay_ws_url=relay_ws,
                    raw_headers=cfg.douyin_cookie,
                )
                await blcsdk.log(
                    f'抖音中继 sidecar 已启动并下发连接: room={room_id} relay={relay_ws}',
                    logging.INFO,
                )
            else:
                await blcsdk.log(
                    '抖音中继 sidecar 已启动（未配置 douyin_room_id，等待管理页手动连接）',
                    logging.WARNING,
                )
            await blcsdk.log(
                f'sidecar 运行地址: http://{cfg.sidecar_host}:{cfg.sidecar_port}',
                logging.INFO,
            )
            _notify_admin_status_changed()
        except Exception as e:
            _sidecar = None
            await blcsdk.log(
                f'抖音 sidecar 启动失败: {e}',
                logging.ERROR,
            )
    else:
        await blcsdk.log(
            f'抖音中继已启动，请在 dycast 填写 ws://{cfg.listen_host}:{cfg.listen_port}{cfg.ws_path}',
            logging.INFO,
        )


def _dedup_key(msg: dict) -> str:
    method = str(msg.get('method') or '')
    mid = msg.get('id')
    if mid:
        return f'{method}:{mid}'
    blob = json.dumps(msg, ensure_ascii=False, sort_keys=True)[:400]
    return f'{method}:h{hash(blob)}'


async def _on_ws_text(raw: str) -> None:
    assert _protocol is not None
    kind, payload = _protocol.parse_raw_payload(raw)
    await _on_protocol_payload(kind, payload)


async def _on_protocol_payload(kind: str, payload: Any) -> None:
    if kind == 'unknown' or payload is None:
        return
    if kind == 'live_info' and isinstance(payload, dict):
        title = payload.get('title', '')
        room = payload.get('roomNum') or payload.get('roomId', '')
        logger.info('dycast live info: room=%s title=%s', room, title)
        return
    if kind != 'messages':
        return

    cfg = config.get_config()
    assert _dedup is not None and _injector is not None

    total_count = 0
    mapped_count = 0
    gift_raw_count = 0
    gift_mapped_count = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        total_count += 1
        if str(item.get('method') or '') == mapper.GIFT:
            gift_raw_count += 1
        key = _dedup_key(item)
        if key in _dedup:
            continue
        mapped = mapper.map_dy_payload(
            item,
            content_prefix=cfg.content_prefix,
            include_gift=cfg.include_gift,
            native_gift=cfg.native_gift,
            include_like=cfg.include_like,
            include_member=cfg.include_member,
            include_social=cfg.include_social,
        )
        if mapped is None:
            continue
        mapped_count += 1
        if int(mapped.get('guard_level') or 0) == 3:
            logger.info(
                'star_guard mapped kind=%s uid=%s name=%s',
                str(mapped.get('kind', '')),
                str(mapped.get('uid', '')),
                str(mapped.get('author_name', '')),
            )
        if str(mapped.get('kind') or '') == 'gift':
            gift_mapped_count += 1
            logger.info(
                'gift mapped kind=gift name=%s num=%s total_coin=%s uid=%s',
                str(mapped.get('gift_name', '')),
                str(mapped.get('num', '')),
                str(mapped.get('total_coin', '')),
                str(mapped.get('uid', '')),
            )
        _dedup[key] = True
        await _injector.enqueue(mapped)
    if total_count > 0:
        metrics = _injector.get_metrics()
        logger.info(
            'dycast messages processed total=%d mapped=%d gift_raw=%d gift_mapped=%d sent=%d dropped=%d queue=%d',
            total_count,
            mapped_count,
            gift_raw_count,
            gift_mapped_count,
            int(metrics.get('sent', 0)),
            int(metrics.get('dropped', 0)),
            int(metrics.get('queue_size', 0)),
        )
        _notify_admin_status_changed()


def get_runtime_status() -> Dict[str, Any]:
    cfg = config.get_config()
    injector_metrics: Dict[str, Any] = {}
    if _injector is not None:
        injector_metrics = _injector.get_metrics()
    sidecar_snapshot: Dict[str, Any] = {}
    sidecar_state: Dict[str, Any] = {}
    if _sidecar is not None:
        sidecar_snapshot = _sidecar.snapshot()
        try:
            sidecar_state = _sidecar.bridge_client().status()
        except Exception as e:
            sidecar_state = {'ok': False, 'error': str(e)}
    sidecar_engine = {}
    if isinstance(sidecar_state, dict):
        sidecar_engine = sidecar_state.get('engine', {}) if isinstance(sidecar_state.get('engine', {}), dict) else {}
    return {
        'current_mode': cfg.mode,
        'relay_backend': cfg.relay_backend,
        'state': 'running',
        'sent': int(injector_metrics.get('sent', 0)),
        'dropped': int(injector_metrics.get('dropped', 0)),
        'queue_size': int(injector_metrics.get('queue_size', 0)),
        'sidecar_engine_state': str(sidecar_engine.get('state', '')),
        'sidecar_last_message_at': int(sidecar_engine.get('lastMessageAt', 0) or 0),
        'sidecar_relay_connected': bool(sidecar_engine.get('relayConnected', False)),
        'sidecar_runtime': sidecar_snapshot,
        'sidecar_status': sidecar_state,
    }


def _apply_sidecar_runtime_config() -> Dict[str, Any]:
    if _sidecar is None:
        return {'ok': False, 'error': 'sidecar manager is not running'}
    cfg = config.get_config()
    if cfg.relay_backend != 'sidecar':
        return {'ok': True, 'applied': False, 'reason': 'relay_backend is not sidecar'}

    room = (cfg.douyin_room_id or '').strip()
    raw_headers = str(cfg.douyin_cookie or '')
    relay_ws = config.get_dycast_relay_ws_url()
    client = _sidecar.bridge_client()

    # 配置更新后统一重新下发，确保 sidecar 使用最新 room/cookie。
    disconnect_ret = client.disconnect()
    if room == '':
        _notify_admin_status_changed()
        return {
            'ok': True,
            'applied': True,
            'disconnected': bool(disconnect_ret.get('ok', False)),
            'connected': False,
            'reason': 'empty room_id',
        }
    connect_ret = client.connect(room_num=room, relay_ws_url=relay_ws, raw_headers=raw_headers)
    _notify_admin_status_changed()
    return {
        'ok': bool(connect_ret.get('ok', False)),
        'applied': True,
        'disconnected': bool(disconnect_ret.get('ok', False)),
        'connected': bool(connect_ret.get('ok', False)),
        'connect_ret': connect_ret,
    }


def handle_admin_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if action != 'sidecar':
        return {'ok': False, 'error': f'unsupported action: {action}'}
    if _sidecar is None:
        return {'ok': False, 'error': 'sidecar manager is not running'}
    op = str(payload.get('op') or '').strip().lower()
    if op == 'status':
        return {'ok': True, 'data': get_runtime_status()}
    if op == 'disconnect':
        ret = _sidecar.bridge_client().disconnect()
        _notify_admin_status_changed()
        return ret
    if op == 'connect':
        cfg = config.get_config()
        room = str(payload.get('room_id') or cfg.douyin_room_id or '').strip()
        raw_headers = str(payload.get('raw_headers') or cfg.douyin_cookie or '')
        relay_ws = config.get_dycast_relay_ws_url()
        ret = _sidecar.bridge_client().connect(room_num=room, relay_ws_url=relay_ws, raw_headers=raw_headers)
        _notify_admin_status_changed()
        return ret
    if op == 'restart':
        # 管理窗口在独立线程时，create_task 必须在插件 asyncio 线程执行
        def _schedule() -> None:
            asyncio.create_task(_sidecar.restart())

        try:
            admin_ui.run_on_plugin_loop(_schedule)
        except RuntimeError as e:
            return {'ok': False, 'error': str(e)}
        _notify_admin_status_changed()
        return {'ok': True, 'scheduled': True}
    if op == 'apply_config':
        return _apply_sidecar_runtime_config()
    return {'ok': False, 'error': f'unsupported op: {op}'}


def init_signal_handlers():
    global shut_down_event
    shut_down_event = asyncio.Event()
    signums = (signal.SIGINT, signal.SIGTERM)
    try:
        loop = asyncio.get_running_loop()
        for signum in signums:
            loop.add_signal_handler(signum, start_shut_down)
    except NotImplementedError:
        for signum in signums:
            signal.signal(signum, start_shut_down)


def start_shut_down(*_args):
    shut_down_event.set()


def init_logging():
    os.makedirs(config.LOG_PATH, exist_ok=True)
    filename = os.path.join(config.LOG_PATH, 'douyin-relay.log')
    stream_handler = logging.StreamHandler()
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename, encoding='utf-8', when='midnight', backupCount=7, delay=True
    )
    logging.basicConfig(
        format='{asctime} {levelname} [{name}]: {message}',
        style='{',
        level=logging.INFO,
        handlers=[stream_handler, file_handler],
    )


async def run():
    logger.info('douyin-relay running, waiting for shutdown...')
    logger.info('runtime status: %s', json.dumps(get_runtime_status(), ensure_ascii=False, sort_keys=True))
    assert shut_down_event is not None
    await shut_down_event.wait()
    logger.info('Start to shut down')


async def shut_down():
    global _relay, _injector, _sidecar
    listener.shut_down()
    if _relay is not None:
        await _relay.stop()
        _relay = None
    if _injector is not None:
        await _injector.stop()
        _injector = None
    if _sidecar is not None:
        await _sidecar.stop()
        _sidecar = None
    _notify_admin_status_changed()
    logger.info('runtime status(final): %s', json.dumps(get_runtime_status(), ensure_ascii=False, sort_keys=True))
    await blcsdk.shut_down()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
