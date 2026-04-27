# -*- coding: utf-8 -*-
"""
插件内本地 WebSocket 服务，供 dycast「转发」连接。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from aiohttp import web

logger = logging.getLogger('douyin-relay.' + __name__)

OnMessage = Callable[[str], Awaitable[None]]


class DouyinRelayServer:
    def __init__(
        self,
        host: str,
        port: int,
        path: str,
        on_text: OnMessage,
    ):
        self._host = host
        self._port = port
        p = (path or '/').strip()
        if not p.startswith('/'):
            p = '/' + p
        self._path = p.rstrip('/') or '/'
        self._on_text = on_text
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._app: Optional[web.Application] = None
        self._active_ws: Optional[web.WebSocketResponse] = None
        self._ws_lock = asyncio.Lock()

    async def start(self) -> None:
        self._app = web.Application()
        self._app.router.add_get(self._path, self._websocket_handler)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info(
            'Douyin relay WebSocket listening ws://%s:%s%s',
            self._host,
            self._port,
            self._path if self._path.startswith('/') else '/' + self._path,
        )

    async def stop(self) -> None:
        async with self._ws_lock:
            if self._active_ws is not None:
                await self._active_ws.close()
                self._active_ws = None
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self._app = None
        logger.info('Douyin relay server stopped')

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=8 * 1024 * 1024)
        await ws.prepare(request)
        peer = request.remote
        async with self._ws_lock:
            if self._active_ws is not None and self._active_ws is not ws:
                logger.warning('Replacing previous dycast forwarder connection')
                await self._active_ws.close()
            self._active_ws = ws
        logger.info('dycast forwarder connected from %s', peer)
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self._on_text(msg.data)
                elif msg.type == web.WSMsgType.BINARY:
                    logger.warning('Ignoring binary ws frame from dycast')
                elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.CLOSING, web.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('WebSocket handler error:')
        finally:
            async with self._ws_lock:
                if self._active_ws is ws:
                    self._active_ws = None
            logger.info('dycast forwarder disconnected from %s', peer)
        return ws
