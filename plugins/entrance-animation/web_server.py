# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiohttp import web

import config
import store

logger = logging.getLogger('entrance-animation.web_server')

_SAFE_FILENAME_CHARS = set(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.'
)


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name or '')
    cleaned = ''.join(c if c in _SAFE_FILENAME_CHARS else '_' for c in name)
    return cleaned.strip('._') or 'file'


class EntranceAnimationWebServer:
    def __init__(self) -> None:
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._overlay_clients: Set[web.WebSocketResponse] = set()
        self._app = web.Application(
            middlewares=[self._auth_middleware],
            client_max_size=512 * 1024 * 1024,  # 允许上传较大的视频
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self._app.add_routes([
            web.get('/healthz', self._handle_healthz),
            web.get('/', self._handle_admin_index),
            web.get('/overlay', self._handle_overlay_index),
            web.get('/ws/overlay', self._handle_overlay_ws),
            web.get('/api/config', self._handle_get_config),
            web.post('/api/users', self._handle_upsert_user),
            web.delete('/api/users/{uid}', self._handle_delete_user),
            web.get('/api/animations', self._handle_list_animations),
            web.post('/api/animations', self._handle_upload_animation),
            web.post('/api/animations/{id}', self._handle_update_animation),
            web.delete('/api/animations/{id}', self._handle_delete_animation),
            web.post('/api/global', self._handle_update_global),
            web.post('/api/test', self._handle_test_play),
        ])
        if os.path.isdir(config.ADMIN_PATH):
            self._app.router.add_static('/assets', config.ADMIN_PATH, show_index=False)
        if os.path.isdir(config.OVERLAY_PATH):
            self._app.router.add_static('/overlay-assets', config.OVERLAY_PATH, show_index=False)
        self._app.router.add_static('/media', config.MEDIA_PATH, show_index=False)

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=config.WEB_HOST, port=config.WEB_PORT)
        await self._site.start()
        logger.info('Entrance animation web started: %s', config.build_admin_url())

    async def stop(self) -> None:
        for ws in list(self._overlay_clients):
            try:
                await ws.close()
            except Exception:  # noqa
                pass
        self._overlay_clients.clear()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    # ------------------------------------------------------------------ auth

    @web.middleware
    async def _auth_middleware(
        self, request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
    ):
        path = request.path
        # 静态资源与媒体、健康检查免鉴权（仅监听本地）
        if (
            path == '/healthz'
            or path.startswith('/assets')
            or path.startswith('/overlay-assets')
            or path.startswith('/media')
        ):
            return await handler(request)
        if not self._is_authorized(request):
            if path.startswith('/api/') or path == '/ws/overlay':
                return self._json({'error': 'unauthorized'}, status=401)
            return web.Response(status=401, text='Unauthorized')
        return await handler(request)

    def _is_authorized(self, request: web.Request) -> bool:
        token = request.query.get('token', '')
        if token == config.ADMIN_TOKEN:
            return True
        auth = request.headers.get('Authorization', '').strip()
        if auth.startswith('Bearer '):
            return auth[7:] == config.ADMIN_TOKEN
        return False

    # -------------------------------------------------------------- helpers

    def _json(self, body: Dict[str, Any], status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps(body, ensure_ascii=False),
            status=status,
            content_type='application/json',
        )

    def _media_url(self, filename: str) -> str:
        return f'/media/{filename}'

    def _build_play_event(self, animation: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        global_cfg = store.get_global()
        return {
            'type': 'play',
            'id': uuid.uuid4().hex,
            'animation': {
                'type': animation['type'],
                'url': self._media_url(animation['filename']),
                'durationSec': animation.get('durationSec', 5.0),
                'volume': animation.get('volume', 80),
                'name': animation.get('name', ''),
            },
            'global': {
                'position': global_cfg.get('position', 'center'),
                'size': global_cfg.get('size', 480),
            },
            'user': user,
        }

    async def broadcast_play(self, animation: Dict[str, Any], user: Dict[str, Any]) -> int:
        """向所有 overlay 客户端推送一次播放事件，返回收到的客户端数量。"""
        event = self._build_play_event(animation, user)
        client_count = len(self._overlay_clients)
        logger.info(
            'Broadcasting play event: user=%s uid=%s animation=%s url=%s overlay_clients=%d',
            user.get('name'), user.get('uid'), animation.get('name'),
            event['animation'].get('url'), client_count,
        )
        count = await self._broadcast(event)
        if count < client_count:
            logger.warning(
                'Play event partially delivered: sent=%d total_clients=%d event_id=%s',
                count, client_count, event.get('id'),
            )
        return count

    async def _broadcast(self, event: Dict[str, Any]) -> int:
        text = json.dumps(event, ensure_ascii=False)
        count = 0
        for ws in list(self._overlay_clients):
            try:
                await ws.send_str(text)
                count += 1
            except Exception as e:  # noqa
                logger.warning('Failed to send play event to overlay client: %s', e)
                self._overlay_clients.discard(ws)
        return count

    # --------------------------------------------------------------- routes

    async def _handle_healthz(self, request: web.Request) -> web.Response:
        return self._json({'ok': True})

    async def _handle_admin_index(self, request: web.Request) -> web.StreamResponse:
        index_path = os.path.join(config.ADMIN_PATH, 'index.html')
        if not os.path.isfile(index_path):
            return web.Response(status=500, text='Admin UI not found')
        return web.FileResponse(index_path)

    async def _handle_overlay_index(self, request: web.Request) -> web.StreamResponse:
        index_path = os.path.join(config.OVERLAY_PATH, 'index.html')
        if not os.path.isfile(index_path):
            return web.Response(status=500, text='Overlay page not found')
        return web.FileResponse(index_path)

    async def _handle_overlay_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._overlay_clients.add(ws)
        logger.info('Overlay client connected, total=%d', len(self._overlay_clients))
        try:
            async for _msg in ws:
                pass
        finally:
            self._overlay_clients.discard(ws)
            logger.info('Overlay client disconnected, total=%d', len(self._overlay_clients))
        return ws

    async def _handle_get_config(self, request: web.Request) -> web.Response:
        return self._json({'data': store.get_all()})

    async def _handle_upsert_user(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return self._json({'error': 'invalid json'}, status=400)

        uid = str(body.get('uid', '')).strip()
        if not uid:
            return self._json({'error': 'uid required'}, status=400)

        animation_id = str(body.get('animationId', '')).strip()
        if animation_id and store.get_animation(animation_id) is None:
            return self._json({'error': 'animation not found'}, status=400)

        user = store.upsert_user(
            uid=uid,
            name=str(body.get('name', '')),
            animation_id=animation_id,
            enabled=bool(body.get('enabled', True)),
            cooldown_sec=body.get('cooldownSec'),
        )
        return self._json({'data': user})

    async def _handle_delete_user(self, request: web.Request) -> web.Response:
        uid = request.match_info.get('uid', '')
        ok = store.delete_user(uid)
        return self._json({'ok': ok})

    async def _handle_list_animations(self, request: web.Request) -> web.Response:
        return self._json({'data': store.get_all()['animations']})

    async def _handle_upload_animation(self, request: web.Request) -> web.Response:
        reader = await request.multipart()
        name = ''
        duration_sec = 5.0
        volume = 80
        saved_filename = ''
        media_type = ''

        async for part in reader:
            if part.name == 'file':
                orig_name = _sanitize_filename(part.filename or '')
                ext = os.path.splitext(orig_name)[1].lower()
                media_type = config.ALLOWED_MEDIA_EXTS.get(ext, '')
                if not media_type:
                    return self._json({'error': f'unsupported file type: {ext}'}, status=400)
                saved_filename = f'{uuid.uuid4().hex}{ext}'
                dest = os.path.join(config.MEDIA_PATH, saved_filename)
                with open(dest, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
            elif part.name == 'name':
                name = (await part.text()).strip()
            elif part.name == 'durationSec':
                try:
                    duration_sec = float((await part.text()).strip())
                except (TypeError, ValueError):
                    duration_sec = 5.0
            elif part.name == 'volume':
                try:
                    volume = int((await part.text()).strip())
                except (TypeError, ValueError):
                    volume = 80

        if not saved_filename:
            return self._json({'error': 'no file uploaded'}, status=400)

        anim = store.add_animation(
            name=name,
            media_type=media_type,
            filename=saved_filename,
            duration_sec=duration_sec,
            volume=volume,
        )
        return self._json({'data': anim})

    async def _handle_update_animation(self, request: web.Request) -> web.Response:
        anim_id = request.match_info.get('id', '')
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return self._json({'error': 'invalid json'}, status=400)
        anim = store.update_animation(anim_id, body)
        if anim is None:
            return self._json({'error': 'animation not found'}, status=404)
        return self._json({'data': anim})

    async def _handle_delete_animation(self, request: web.Request) -> web.Response:
        anim_id = request.match_info.get('id', '')
        anim = store.delete_animation(anim_id)
        if anim is None:
            return self._json({'error': 'animation not found'}, status=404)
        # 删除媒体文件
        try:
            path = os.path.join(config.MEDIA_PATH, anim['filename'])
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            logger.warning('Failed to remove media file: %s', anim.get('filename'))
        return self._json({'ok': True})

    async def _handle_update_global(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return self._json({'error': 'invalid json'}, status=400)
        global_cfg = store.update_global(body)
        return self._json({'data': global_cfg})

    async def _handle_test_play(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return self._json({'error': 'invalid json'}, status=400)

        anim_id = str(body.get('animationId', '')).strip()
        animation = store.get_animation(anim_id)
        if animation is None:
            return self._json({'error': 'animation not found'}, status=404)

        user = {
            'uid': 'test',
            'name': str(body.get('name', '') or '测试用户'),
            'avatarUrl': '',
        }
        count = await self.broadcast_play(animation, user)
        logger.info('Test play requested: animation=%s clients=%d', anim_id, count)
        return self._json({'ok': True, 'clients': count})
