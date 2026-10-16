#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import contextlib
import json
import logging.handlers
import os
import signal
import sys
import time
from collections import deque
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
import listener
import mapper
import web_admin
from injector import Injector
from engine_process import EngineProcess
from supervisor import LiveSupervisor

logger = logging.getLogger('douyin-relay')

_COOKIE_MIN_LEN = 200
_RECENT_LIMIT = 100

shut_down_event: Optional[asyncio.Event] = None
_dedup: Optional[TTLCache] = None
_injector: Optional[Injector] = None
_engine: Optional[EngineProcess] = None
_supervisor: Optional[LiveSupervisor] = None
_recent_messages: deque = deque(maxlen=_RECENT_LIMIT)
_login_settled = False
_consume_id: Optional[str] = None
_login_cancel_requested = False
_tick_task: Optional[asyncio.Task] = None
_login_wait_task: Optional[asyncio.Task] = None
_restart_task: Optional[asyncio.Task] = None


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

    global _dedup, _injector, _engine, _supervisor, _tick_task
    cfg = config.get_config()
    _dedup = TTLCache(maxsize=cfg.dedup_max_size, ttl=cfg.dedup_ttl_seconds)
    _injector = Injector(cfg.inject_queue_max, cfg.inject_concurrency)
    await _injector.start()
    _supervisor = LiveSupervisor(
        interval_seconds=int(getattr(cfg, 'live_probe_interval_seconds', 180) or 180),
        auto_refresh=bool(getattr(cfg, 'cookie_auto_refresh', False)),
    )
    bundled_dycast_path = os.path.join(config.BASE_PATH, 'dycast')
    legacy_dycast_path = os.path.abspath(os.path.join(config.BASE_PATH, '..', '..', '..', 'dycast'))
    dycast_path = bundled_dycast_path if os.path.isdir(bundled_dycast_path) else legacy_dycast_path
    node_exe = _resolve_sidecar_node_exe(cfg, dycast_path)
    _engine = EngineProcess(
        on_messages=_on_engine_messages,
        on_event=handle_engine_event,
        node_exe=node_exe,
        dycast_path=dycast_path,
        env={
            'DYCAST_LOGIN_PROFILE_DIR': config.resolve_douyin_browser_profile_dir(cfg),
            'DYCAST_LOGIN_TIMEOUT_SECONDS': str(cfg.cookie_login_timeout_seconds),
            'DYCAST_SILENT_TIMEOUT_SECONDS': str(cfg.cookie_silent_timeout_seconds),
        },
    )
    try:
        await _engine.start()
    except Exception as e:
        logger.error('douyin engine start failed error=%s', type(e).__name__)
        await blcsdk.log('抖音引擎启动失败', logging.ERROR)
    else:
        try:
            await bootstrap_live(_engine, _supervisor)
        except Exception:
            logger.error('douyin engine bootstrap failed')
        await blcsdk.log('抖音引擎已启动', logging.INFO)
    _tick_task = asyncio.create_task(_supervisor_tick_loop())
    await _start_web_admin()


def _dedup_key(msg: dict) -> str:
    method = str(msg.get('method') or '')
    mid = msg.get('id')
    if mid:
        return f'{method}:{mid}'
    blob = json.dumps(msg, ensure_ascii=False, sort_keys=True)[:400]
    return f'{method}:h{hash(blob)}'


def _on_engine_messages(payload) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_handle_messages(payload))


def _remember_mapped(mapped: dict) -> None:
    text = mapped.get('content')
    if not isinstance(text, str):
        text = str(mapped.get('text') or '')
    item = {
        'time': int(time.time()),
        'author_name': str(mapped.get('author_name') or ''),
        'kind': str(mapped.get('kind') or ''),
        'text': text,
    }
    if item['kind'] == 'gift':
        item['gift_name'] = str(mapped.get('gift_name') or '')
        try:
            item['num'] = int(mapped.get('num') or 0)
        except (TypeError, ValueError):
            item['num'] = 0
    _recent_messages.append(item)


async def _handle_messages(payload) -> None:
    if not isinstance(payload, list):
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
        _remember_mapped(mapped)
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


def redact_secrets(value):
    if isinstance(value, dict):
        return {
            k: redact_secrets(v)
            for k, v in value.items()
            if k not in ('cookie', 'rawHeaders', 'douyin_cookie')
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _room_and_disk():
    try:
        cfg = config.get_config()
    except Exception:
        return '', ''
    room = str(getattr(cfg, 'douyin_room_id', '') or '').strip()
    disk = str(getattr(cfg, 'douyin_cookie', '') or '')
    return room, disk


def _cancel_pending_login_wait() -> None:
    global _login_wait_task
    wait_task = _login_wait_task
    _login_wait_task = None
    if wait_task is not None and not wait_task.done():
        wait_task.cancel()


def _schedule_login_wait() -> None:
    global _login_wait_task
    try:
        loop = asyncio.get_running_loop()
        cfg = config.get_config()
    except Exception:
        return
    if _login_wait_task is not None and not _login_wait_task.done():
        return
    _login_wait_task = loop.create_task(_wait_silent_login(_engine, cfg))


def _login_start_accepted(ret) -> bool:
    return isinstance(ret, dict) and bool(ret.get('ok'))


def _send_commands(cmds, allow_connect=True) -> None:
    global _login_settled, _consume_id, _login_cancel_requested
    if not cmds or _engine is None:
        return
    room, _disk = _room_and_disk()
    armed = False
    for cmd in cmds:
        if not isinstance(cmd, dict):
            continue
        name = str(cmd.get('cmd') or '')
        if room == '' and name in ('probe_live', 'connect'):
            continue
        if name == 'connect' and not allow_connect:
            continue
        if name == 'login_start':
            _login_settled = False
            _consume_id = None
            _login_cancel_requested = False
            armed = True
        try:
            ret = _engine.send(dict(cmd))
        except Exception:
            logger.error('douyin engine send failed cmd=%s', name)
            if name == 'login_start':
                _complete_login('error', '')
                armed = False
            continue
        if name == 'login_start' and not _login_start_accepted(ret):
            logger.error('douyin engine send failed cmd=%s', name)
            _complete_login('error', '')
            armed = False
    if armed and not _login_settled:
        _schedule_login_wait()


def _complete_login(phase: str, cookie: str) -> None:
    global _login_settled
    if _login_cancel_requested and phase == 'done':
        return
    if _login_settled:
        return
    _login_settled = True
    cmds = []
    if _supervisor is not None:
        try:
            cmds = list(_supervisor.on_login(phase=phase, cookie=cookie) or [])
        except Exception:
            logger.error('supervisor on_login failed phase=%s', phase)
            cmds = []
    room, disk = _room_and_disk()
    if phase != 'done' or len(cookie) < _COOKIE_MIN_LEN:
        has_probe = any(isinstance(item, dict) and item.get('cmd') == 'probe_live' for item in cmds)
        if len(disk) >= _COOKIE_MIN_LEN and room and not has_probe:
            cmds.append({'cmd': 'probe_live', 'roomNum': room})
    cmds = [item for item in cmds if not (isinstance(item, dict) and item.get('cmd') == 'connect')]
    _send_commands(cmds, allow_connect=False)


def _on_login_event(event: dict) -> None:
    global _consume_id
    phase = str(event.get('phase') or '')
    logger.info('douyin cookie refresh phase=%s cookieLength=%s', phase, event.get('cookieLength'))
    if phase in ('', 'running', 'idle'):
        return
    if _login_cancel_requested and phase == 'done':
        return
    if phase == 'done':
        _consume_id = 'login-consume'
        if _engine is None:
            _complete_login('error', '')
            return
        ret = _engine.send({'cmd': 'login_consume', 'id': _consume_id})
        if _login_settled:
            return
        if not isinstance(ret, dict) or not ret.get('ok'):
            _complete_login('error', '')
        return
    _complete_login(phase, '')


def _on_result_event(event: dict) -> None:
    global _consume_id
    if _login_cancel_requested:
        return
    raw_cookie = event.get('cookie')
    if isinstance(raw_cookie, str):
        cookie = raw_cookie
        length = len(cookie)
    else:
        cookie = ''
        length = event.get('cookieLength')
    logger.info('engine result id=%s ok=%s cookieLength=%s', event.get('id'), bool(event.get('ok')), length)
    if _consume_id is None or str(event.get('id') or '') != str(_consume_id):
        return
    _consume_id = None
    if len(cookie) >= _COOKIE_MIN_LEN:
        config.write_douyin_cookie_atomic(cookie)
    _complete_login('done', cookie)


def handle_engine_event(event) -> None:
    if not isinstance(event, dict):
        return
    typ = str(event.get('type') or '')
    if typ == 'probe':
        if _supervisor is None:
            return
        cmds = _supervisor.on_probe(
            ok=bool(event.get('ok')),
            living=bool(event.get('living')),
            error=str(event.get('error') or ''),
        )
        _send_commands(cmds, allow_connect=True)
        return
    if typ == 'status':
        if _supervisor is None:
            return
        cmds = _supervisor.on_cast_status(
            state=str(event.get('state') or ''),
            error=str(event.get('error') or ''),
        )
        _send_commands(cmds, allow_connect=True)
        return
    if typ == 'login':
        _on_login_event(event)
        return
    if typ == 'result':
        _on_result_event(event)
        return
    if typ == 'live_info':
        payload = event.get('payload') if isinstance(event.get('payload'), dict) else event
        title = ''
        room = ''
        if isinstance(payload, dict):
            title = payload.get('title', '')
            room = payload.get('roomNum') or payload.get('roomId', '')
        logger.info('dycast live info: room=%s title=%s', room, title)


async def _timeout_cancel(engine, cfg) -> None:
    global _login_cancel_requested
    _login_cancel_requested = True
    try:
        engine.send({'cmd': 'login_cancel'})
    except Exception:
        logger.error('douyin cookie refresh failed phase=%s error=%s', 'running', 'login_cancel')
    loop = asyncio.get_running_loop()
    extra = max(1, int(getattr(cfg, 'cookie_silent_timeout_seconds', 30) or 0))
    deadline = loop.time() + extra
    while (
        str(getattr(engine, 'login_phase', '') or '') == 'running'
        and loop.time() < deadline
    ):
        await asyncio.sleep(0.05)
    if _login_settled:
        return
    _complete_login('cancelled', '')


async def _wait_silent_login(engine, cfg) -> None:
    timeout = int(getattr(cfg, 'cookie_silent_timeout_seconds', 30) or 0)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0, timeout)
    while not _login_settled:
        if loop.time() >= deadline:
            await _timeout_cancel(engine, cfg)
            return
        await asyncio.sleep(0.05)


async def bootstrap_live(engine, supervisor) -> None:
    global _engine, _supervisor, _login_settled, _consume_id, _login_cancel_requested
    _engine = engine
    _supervisor = supervisor
    _login_settled = False
    _consume_id = None
    _login_cancel_requested = False
    cfg = config.get_config()
    room = str(getattr(cfg, 'douyin_room_id', '') or '').strip()
    disk = str(getattr(cfg, 'douyin_cookie', '') or '')
    has_cookie = len(disk) >= _COOKIE_MIN_LEN
    commands = list(supervisor.start(room_id=room, has_cookie=has_cookie) or [])
    if bool(getattr(cfg, 'cookie_auto_refresh', False)) and room == '' and not any(
        isinstance(item, dict) and item.get('cmd') == 'login_start' for item in commands
    ):
        commands.insert(0, {'cmd': 'login_start', 'mode': 'silent'})
    started_login = False
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        name = str(cmd.get('cmd') or '')
        if room == '' and name in ('probe_live', 'connect'):
            continue
        if name == 'login_start':
            started_login = True
            try:
                ret = engine.send(dict(cmd))
            except Exception:
                logger.error('douyin cookie refresh failed phase=%s error=%s', '', 'login_start')
                _complete_login('error', '')
                return
            if not _login_start_accepted(ret):
                logger.error('douyin cookie refresh failed phase=%s error=%s', '', 'login_start')
                _complete_login('error', '')
                return
            continue
        try:
            engine.send(dict(cmd))
        except Exception:
            logger.error('douyin engine send failed cmd=%s', name)
    if started_login and not _login_settled:
        await _wait_silent_login(engine, cfg)


async def _supervisor_tick_loop() -> None:
    assert shut_down_event is not None
    while not shut_down_event.is_set():
        engine = _engine
        supervisor = _supervisor
        if engine is not None and supervisor is not None:
            try:
                running = bool(engine.snapshot().get('running'))
            except Exception:
                running = False
            if running:
                try:
                    cmds = supervisor.tick()
                except Exception:
                    logger.error('supervisor tick failed')
                    cmds = []
                if cmds:
                    _send_commands(cmds, allow_connect=True)
        try:
            await asyncio.wait_for(shut_down_event.wait(), timeout=0.5)
        except asyncio.TimeoutError:
            continue


def get_runtime_status() -> Dict[str, Any]:
    injector_metrics: Dict[str, Any] = {}
    if _injector is not None:
        injector_metrics = _injector.get_metrics()
    snap: Dict[str, Any] = {'running': False}
    if _engine is not None:
        try:
            raw_snap = _engine.snapshot()
            if isinstance(raw_snap, dict):
                snap = redact_secrets(raw_snap)
        except Exception:
            snap = {'running': False}
    phase = _supervisor.phase if _supervisor is not None else 'idle'
    room, _disk = _room_and_disk()
    return {
        'running': bool(snap.get('running', False)),
        'phase': phase,
        'state': 'running' if snap.get('running') else 'stopped',
        'sent': int(injector_metrics.get('sent', 0)),
        'dropped': int(injector_metrics.get('dropped', 0)),
        'queue_size': int(injector_metrics.get('queue_size', 0)),
        'login_phase': str(snap.get('login_phase') or ''),
        'room_id': room,
        'messages': list(_recent_messages),
        'logs': list(snap.get('logs') or [])[-200:],
    }


def _engine_is_running() -> bool:
    if _engine is None:
        return False
    try:
        snap = _engine.snapshot()
    except Exception:
        return False
    return bool(isinstance(snap, dict) and snap.get('running'))


_SAVE_FIELDS = {
    'room_id': 'douyin_room_id',
    'cookie': 'douyin_cookie',
    'content_prefix': 'content_prefix',
    'include_gift': 'include_gift',
    'native_gift': 'native_gift',
    'include_like': 'include_like',
    'include_member': 'include_member',
    'include_social': 'include_social',
}
_BOOL_FIELDS = frozenset(('include_gift', 'native_gift', 'include_like', 'include_member', 'include_social'))


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def admin_snapshot() -> Dict[str, Any]:
    status = get_runtime_status()
    cookie = ''
    try:
        cfg = config.get_config()
    except Exception:
        cfg = None
    if cfg is not None:
        cookie = str(getattr(cfg, 'douyin_cookie', '') or '')
        status['room_id'] = str(getattr(cfg, 'douyin_room_id', '') or '').strip()
        status['content_prefix'] = str(getattr(cfg, 'content_prefix', '') or '')
        status['include_gift'] = bool(getattr(cfg, 'include_gift', True))
        status['native_gift'] = bool(getattr(cfg, 'native_gift', True))
        status['include_like'] = bool(getattr(cfg, 'include_like', False))
        status['include_member'] = bool(getattr(cfg, 'include_member', True))
        status['include_social'] = bool(getattr(cfg, 'include_social', True))
    status['cookie'] = cookie
    status['messages'] = list(status.get('messages') or [])[-100:]
    logs = []
    for line in list(status.get('logs') or [])[-200:]:
        text = str(line)
        if cookie and cookie in text:
            continue
        logs.append(text)
    status['logs'] = logs
    return status


def _save_admin_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    room_changed = False
    if 'room_id' in payload and payload.get('room_changed') is not False:
        try:
            cfg = config.get_config()
            old_room = str(getattr(cfg, 'douyin_room_id', '') or '').strip()
        except Exception:
            old_room = ''
        room_changed = str(payload.get('room_id') or '').strip() != old_room
    values: Dict[str, str] = {}
    for src, dst in _SAVE_FIELDS.items():
        if src not in payload:
            continue
        raw = payload[src]
        if src in _BOOL_FIELDS:
            values[dst] = 'true' if _as_bool(raw) else 'false'
        elif src == 'room_id':
            values[dst] = '' if raw is None else str(raw).strip()
        else:
            values[dst] = '' if raw is None else str(raw)
    if values and not config.update_relay_config_values(values):
        return {'ok': False, 'error': 'save_failed'}
    if room_changed and _engine_is_running() and _supervisor is not None:
        room = str(payload.get('room_id') or '').strip()
        _send_commands(_supervisor.change_room(room) or [])
    return {'ok': True, 'room_changed': room_changed}


def _admin_login_start() -> Dict[str, Any]:
    global _login_settled, _consume_id, _login_cancel_requested
    if _engine is None:
        return {'ok': False, 'error': 'engine_not_ready'}
    _cancel_pending_login_wait()
    _login_settled = False
    _consume_id = None
    _login_cancel_requested = False
    try:
        ret = _engine.send({'cmd': 'login_start', 'mode': 'interactive'})
    except Exception:
        logger.error('douyin engine send failed cmd=%s', 'login_start')
        return {'ok': False, 'error': 'engine_not_ready'}
    if not _login_start_accepted(ret):
        error = 'engine_not_ready'
        if isinstance(ret, dict) and ret.get('error'):
            error = str(ret.get('error'))
        return {'ok': False, 'error': error}
    return {'ok': True}


def _admin_login_cancel() -> Dict[str, Any]:
    global _login_cancel_requested
    if _engine is None:
        return {'ok': False, 'error': 'engine_not_ready'}
    _login_cancel_requested = True
    try:
        ret = _engine.send({'cmd': 'login_cancel'})
    except Exception:
        logger.error('douyin engine send failed cmd=%s', 'login_cancel')
        return {'ok': False, 'error': 'engine_not_ready'}
    if isinstance(ret, dict) and ret.get('ok') is False:
        return {'ok': False, 'error': str(ret.get('error') or 'engine_not_ready')}
    return {'ok': True}


async def _restart_engine() -> None:
    if shut_down_event is not None and shut_down_event.is_set():
        return
    wait_task = _login_wait_task
    _cancel_pending_login_wait()
    if wait_task is not None and not wait_task.done():
        with contextlib.suppress(asyncio.CancelledError):
            await wait_task
    engine = _engine
    supervisor = _supervisor
    if engine is None or supervisor is None:
        return
    await asyncio.to_thread(engine.stop)
    if shut_down_event is not None and shut_down_event.is_set():
        return
    try:
        await engine.start()
    except Exception:
        logger.error('douyin engine restart failed')
        return
    if shut_down_event is not None and shut_down_event.is_set():
        return
    try:
        await bootstrap_live(engine, supervisor)
    except Exception:
        logger.error('douyin engine bootstrap failed')


def _schedule_restart() -> Dict[str, Any]:
    global _restart_task
    if _engine is None or _supervisor is None:
        return {'ok': False, 'error': 'engine_not_ready'}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {'ok': False, 'error': 'engine_not_ready'}
    if _restart_task is None or _restart_task.done():
        _restart_task = loop.create_task(_restart_engine())
    return {'ok': True}


def handle_admin_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    if action == 'save_config':
        return _save_admin_config(payload)
    if action == 'restart':
        return _schedule_restart()
    if not _engine_is_running():
        return {'ok': False, 'error': 'engine_not_ready'}
    if action == 'login_start':
        return _admin_login_start()
    if action == 'login_cancel':
        return _admin_login_cancel()
    if action == 'connect':
        if _supervisor is None:
            return {'ok': False, 'error': 'engine_not_ready'}
        _send_commands(_supervisor.user_connect() or [])
        return {'ok': True}
    if action == 'disconnect':
        if _supervisor is None:
            return {'ok': False, 'error': 'engine_not_ready'}
        _send_commands(_supervisor.user_disconnect() or [])
        return {'ok': True}
    return {'ok': False, 'error': 'unsupported action: %s' % action}


async def _start_web_admin() -> None:
    try:
        cfg = config.get_config()
        host = str(getattr(cfg, 'admin_host', '127.0.0.1') or '127.0.0.1')
        port = int(getattr(cfg, 'admin_port', 18771) or 18771)
    except Exception:
        logger.exception('admin config unavailable')
        return
    try:
        await web_admin.start_admin(host, port, admin_snapshot, handle_admin_action)
    except Exception:
        logger.exception('admin server failed')


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
    global _engine, _injector, _tick_task, _login_wait_task, _restart_task
    await web_admin.stop_admin()
    listener.shut_down()
    for task in (_tick_task, _login_wait_task, _restart_task):
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    _tick_task = None
    _login_wait_task = None
    if _engine is not None:
        await asyncio.to_thread(_engine.stop)
        _engine = None
    if _injector is not None:
        await _injector.stop()
        _injector = None
    logger.info('runtime status(final): %s', json.dumps(redact_secrets(get_runtime_status()), ensure_ascii=False, sort_keys=True))
    await blcsdk.shut_down()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
