# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from aiohttp import web

import config
from queue_state import QueueState

logger = logging.getLogger("queue-manager." + __name__)


class WebServer:
    def __init__(self, state: QueueState):
        self._state = state
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._ws_clients: dict[str, set[web.WebSocketResponse]] = {}
        self._register_routes()

    @property
    def admin_url(self) -> str:
        cfg = config.get_config()
        return f"http://{cfg.web_host}:{cfg.web_port}/index.html?token={cfg.admin_token}"

    @property
    def overlay_url(self) -> str:
        cfg = config.get_config()
        return f"http://{cfg.web_host}:{cfg.web_port}/overlay.html?token={cfg.overlay_token}"

    async def start(self) -> None:
        cfg = config.get_config()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=cfg.web_host, port=cfg.web_port)
        await self._site.start()
        logger.info("queue web server listening on http://%s:%d", cfg.web_host, cfg.web_port)

    async def stop(self) -> None:
        for client_set in self._ws_clients.values():
            await asyncio.gather(*(ws.close() for ws in list(client_set)), return_exceptions=True)
        self._ws_clients.clear()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def broadcast_room(self, room_key_str: str) -> None:
        payload = {
            "type": "queueUpdate",
            "queue": self._state.snapshot(room_key_str),
        }
        clients = list(self._ws_clients.get(room_key_str, set()))
        if not clients:
            return
        body = json.dumps(payload, ensure_ascii=False)
        for ws in clients:
            if ws.closed:
                self._ws_clients[room_key_str].discard(ws)
                continue
            await ws.send_str(body)

    def _register_routes(self) -> None:
        self._app.router.add_get("/index.html", self._serve_index)
        self._app.router.add_get("/overlay.html", self._serve_overlay)
        self._app.router.add_get("/js/{name}", self._serve_js)
        self._app.router.add_get("/css/{name}", self._serve_css)

        self._app.router.add_get("/api/rooms", self._api_rooms)
        self._app.router.add_get("/api/queue", self._api_queue)
        self._app.router.add_post("/api/queue/pass", self._api_pass)
        self._app.router.add_post("/api/queue/remove", self._api_remove)
        self._app.router.add_get("/api/settings", self._api_settings_get)
        self._app.router.add_post("/api/settings/update", self._api_settings_update)
        self._app.router.add_get("/ws/queue", self._ws_queue)

    def _verify_admin(self, request: web.Request) -> bool:
        token = request.query.get("token", "")
        if token == "":
            token = request.headers.get("X-Queue-Token", "")
        return token == config.get_config().admin_token

    def _verify_overlay(self, request: web.Request) -> bool:
        token = request.query.get("token", "")
        return token == config.get_config().overlay_token or token == config.get_config().admin_token

    @staticmethod
    def _bad_auth() -> web.Response:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    async def _serve_index(self, request: web.Request) -> web.StreamResponse:
        if not self._verify_admin(request):
            return self._bad_auth()
        return web.FileResponse(os.path.join(config.WEB_PATH, "index.html"))

    async def _serve_overlay(self, request: web.Request) -> web.StreamResponse:
        if not self._verify_overlay(request):
            return self._bad_auth()
        return web.FileResponse(os.path.join(config.WEB_PATH, "overlay.html"))

    async def _serve_js(self, request: web.Request) -> web.StreamResponse:
        if not self._verify_overlay(request):
            return self._bad_auth()
        return web.FileResponse(os.path.join(config.WEB_PATH, "js", request.match_info["name"]))

    async def _serve_css(self, request: web.Request) -> web.StreamResponse:
        if not self._verify_overlay(request):
            return self._bad_auth()
        return web.FileResponse(os.path.join(config.WEB_PATH, "css", request.match_info["name"]))

    async def _api_rooms(self, request: web.Request) -> web.Response:
        if not self._verify_admin(request):
            return self._bad_auth()
        return web.json_response({"ok": True, "rooms": self._state.room_keys()})

    async def _api_queue(self, request: web.Request) -> web.Response:
        if not self._verify_overlay(request):
            return self._bad_auth()
        room_key = request.query.get("roomKey", "all")
        return web.json_response({"ok": True, "queue": self._state.snapshot(room_key)})

    async def _api_pass(self, request: web.Request) -> web.Response:
        if not self._verify_admin(request):
            return self._bad_auth()
        payload = await request.json()
        room_key = str(payload.get("roomKey", "all"))
        popped = self._state.pass_next(room_key)
        await self.broadcast_room(room_key)
        return web.json_response({"ok": True, "popped": popped, "queue": self._state.snapshot(room_key)})

    async def _api_remove(self, request: web.Request) -> web.Response:
        if not self._verify_admin(request):
            return self._bad_auth()
        payload = await request.json()
        room_key = str(payload.get("roomKey", "all"))
        user_key = str(payload.get("userKey", ""))
        removed = False
        if user_key != "":
            removed = self._state.remove_user(room_key, user_key)
        await self.broadcast_room(room_key)
        return web.json_response({"ok": True, "removed": removed, "queue": self._state.snapshot(room_key)})

    async def _api_settings_get(self, request: web.Request) -> web.Response:
        if not self._verify_admin(request):
            return self._bad_auth()
        return web.json_response({"ok": True, "settings": config.get_config().to_public_dict()})

    async def _api_settings_update(self, request: web.Request) -> web.Response:
        if not self._verify_admin(request):
            return self._bad_auth()
        payload: dict[str, Any] = await request.json()
        cfg = config.update_from_payload(payload)
        return web.json_response({"ok": True, "settings": cfg.to_public_dict()})

    async def _ws_queue(self, request: web.Request) -> web.StreamResponse:
        if not self._verify_overlay(request):
            return self._bad_auth()
        room_key = request.query.get("roomKey", "all")
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        self._ws_clients.setdefault(room_key, set()).add(ws)
        await ws.send_json({"type": "queueUpdate", "queue": self._state.snapshot(room_key)})
        try:
            async for _msg in ws:
                pass
        finally:
            self._ws_clients.get(room_key, set()).discard(ws)
        return ws
