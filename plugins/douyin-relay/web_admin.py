# -*- coding: utf-8 -*-
"""Loopback browser admin for the Douyin relay plugin."""
import asyncio
import json
import logging
import webbrowser
from pathlib import Path

from aiohttp import web

logger = logging.getLogger('douyin-relay.web_admin')

_LOOPBACK_HOSTS = frozenset(('127.0.0.1', '::1'))
_SECRET_KEYS = frozenset(('cookie', 'rawHeaders', 'douyin_cookie'))
_HTML_PATH = Path(__file__).resolve().parent / 'web' / 'admin.html'

_runner = None


def _strip_secrets(value):
    if isinstance(value, dict):
        return {
            key: _strip_secrets(item)
            for key, item in value.items()
            if key not in _SECRET_KEYS
        }
    if isinstance(value, list):
        return [_strip_secrets(item) for item in value]
    return value


def _replace_secret(value, secret):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, '')
    if isinstance(value, dict):
        return {key: _replace_secret(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_secret(item, secret) for item in value]
    return value


def _status(status_provider):
    try:
        raw = status_provider() or {}
    except Exception:
        logger.exception('admin status failed')
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    data = dict(raw)
    messages = data.get('messages') or []
    logs = data.get('logs') or []
    data['messages'] = list(messages)[-100:]
    secret = str(data.get('cookie') or '')
    cleaned_logs = []
    for line in list(logs)[-200:]:
        text = _replace_secret(str(line), secret)
        if text:
            cleaned_logs.append(text)
    data['logs'] = cleaned_logs
    return data


def _event_payload(data):
    secret = str(data.get('cookie') or '')
    return _replace_secret(_strip_secrets(data), secret)


def build_app(status_provider, action_handler):
    async def admin_page(_request):
        return web.FileResponse(_HTML_PATH)

    async def snapshot(_request):
        return web.json_response(_status(status_provider))

    async def events(request):
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        )
        await response.prepare(request)
        try:
            while True:
                payload = _event_payload(_status(status_provider))
                blob = b'data: ' + json.dumps(payload, ensure_ascii=False).encode('utf-8') + b'\n\n'
                await response.write(blob)
                await asyncio.sleep(1)
        except (asyncio.CancelledError, ConnectionResetError, ConnectionAbortedError):
            raise
        return response

    async def action(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        name = body.get('action')
        payload = {key: value for key, value in body.items() if key != 'action'}
        if name == 'save_config':
            current = _status(status_provider)
            if 'room_id' in payload:
                new_room = str(payload.get('room_id') or '').strip()
                old_room = str(current.get('room_id') or '').strip()
                payload['room_changed'] = new_room != old_room
            else:
                payload['room_changed'] = False
        if name == 'login_start':
            payload.pop('mode', None)
        result = action_handler(name, payload)
        if asyncio.iscoroutine(result):
            result = await result
        if not isinstance(result, dict):
            result = {'ok': True}
        secret = str(_status(status_provider).get('cookie') or '')
        safe = _replace_secret(_strip_secrets(result), secret)
        return web.json_response(safe)

    app = web.Application()
    app.router.add_get('/admin', admin_page)
    app.router.add_get('/admin/snapshot', snapshot)
    app.router.add_get('/admin/events', events)
    app.router.add_post('/admin/action', action)
    return app


async def start_admin(host, port, status_provider, action_handler):
    global _runner
    if host not in _LOOPBACK_HOSTS:
        logger.error('admin host refused: %s', host)
        return None
    app = build_app(status_provider, action_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    try:
        await site.start()
    except OSError:
        logger.exception('admin listen failed host=%s port=%s', host, port)
        await runner.cleanup()
        return None
    _runner = runner
    return runner


def admin_is_running():
    return _runner is not None


async def stop_admin():
    global _runner
    runner = _runner
    _runner = None
    if runner is not None:
        await runner.cleanup()


def open_admin_browser(already_running, port, opener=webbrowser.open_new_tab):
    if not already_running:
        return
    opener('http://127.0.0.1:%s/admin' % port)
