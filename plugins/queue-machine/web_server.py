from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Set

from aiohttp import web

import config


class QueueWebServer:
    def __init__(
        self,
        *,
        get_snapshot: Callable[[], Dict[str, Any]],
        apply_action: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ):
        self._get_snapshot = get_snapshot
        self._apply_action = apply_action
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._ws_clients: Set[web.WebSocketResponse] = set()

        self._app = web.Application()
        self._app.add_routes(
            [
                web.get("/healthz", self._handle_healthz),
                web.get("/api/snapshot", self._handle_snapshot),
                web.post("/api/admin/action", self._handle_admin_action),
                web.get("/ws", self._handle_ws),
                web.get("/", self._handle_overlay_page),
                web.get("/overlay", self._handle_overlay_page),
                web.get("/admin", self._handle_admin_page),
                web.static("/web", config.WEB_PATH),
            ]
        )

    async def start(self, host: str, port: int) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()

    async def stop(self) -> None:
        clients = list(self._ws_clients)
        self._ws_clients.clear()
        for ws in clients:
            await ws.close(code=1001, message=b"server shutdown")
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def broadcast_snapshot(self) -> None:
        if not self._ws_clients:
            return
        body = json.dumps({"type": "snapshot", "data": self._get_snapshot()}, ensure_ascii=False)
        dead = []
        for ws in list(self._ws_clients):
            try:
                await ws.send_str(body)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.discard(ws)

    async def _handle_healthz(self, req: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _handle_snapshot(self, req: web.Request) -> web.Response:
        return web.json_response(self._get_snapshot())

    async def _handle_admin_action(self, req: web.Request) -> web.Response:
        body = await req.json()
        action = str(body.get("action", "")).strip()
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        res = await self._apply_action(action, payload)
        return web.json_response(res)

    async def _handle_ws(self, req: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(req)
        self._ws_clients.add(ws)
        await ws.send_str(json.dumps({"type": "snapshot", "data": self._get_snapshot()}, ensure_ascii=False))
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT and msg.data == "ping":
                    await ws.send_str("pong")
                elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.ERROR):
                    break
        finally:
            self._ws_clients.discard(ws)
        return ws

    async def _handle_overlay_page(self, req: web.Request) -> web.Response:
        return web.FileResponse(config.WEB_PATH + "/overlay.html")

    async def _handle_admin_page(self, req: web.Request) -> web.Response:
        return web.FileResponse(config.WEB_PATH + "/admin.html")


def schedule(coro: Awaitable[Any]) -> None:
    asyncio.create_task(coro)
