# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
from typing import Any, Awaitable, Callable, Dict

from aiohttp import web

import config
import queries_v2

logger = logging.getLogger('data-analytics.web_server')


class DataAnalyticsWebServer:
    def __init__(self) -> None:
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._app = web.Application(middlewares=[self._auth_middleware])
        self._register_routes()

    def _register_routes(self) -> None:
        queries_v2.ensure_v2_schema()
        self._app.add_routes([
            web.get('/healthz', self._handle_healthz),
            web.get('/', self._handle_index),
            web.get('/api/v1/{tail:.*}', self._handle_v1_removed),
            web.get('/api/v2/kpis', self._handle_v2_kpis),
            web.get('/api/v2/trend/revenue', self._handle_v2_revenue_trend),
            web.get('/api/v2/segments/users', self._handle_v2_user_segments),
            web.get('/api/v2/explore/events', self._handle_v2_explore_events),
            web.get('/api/v2/series/active-hour-of-day', self._handle_v2_active_hour_of_day),
            web.get('/api/v2/rankings/danmaku-authors', self._handle_v2_ranking_danmaku),
            web.get('/api/v2/rankings/gift-authors', self._handle_v2_ranking_gifts),
            web.get('/api/v2/users/danmaku', self._handle_v2_user_danmaku),
            web.get('/api/v2/users/gifts', self._handle_v2_user_gifts),
        ])
        if os.path.isdir(config.WEB_ROOT):
            assets_dir = os.path.join(config.WEB_ROOT, 'assets')
            if os.path.isdir(assets_dir):
                self._app.router.add_static('/assets', assets_dir, show_index=False)
            self._app.router.add_static('/web', config.WEB_ROOT, show_index=False)

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=config.WEB_HOST, port=config.WEB_PORT)
        await self._site.start()
        logger.info('Data analytics web started: %s', config.build_admin_url())

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
        path = request.path
        if path == '/healthz' or path.startswith('/assets') or path.startswith('/web'):
            return await handler(request)
        if path == '/':
            token = request.query.get('token', '')
            if token != config.ADMIN_TOKEN:
                return web.Response(status=401, text='Unauthorized')
            return await handler(request)
        if path.startswith('/api/'):
            if not self._is_authorized(request):
                return self._json({'error': 'unauthorized'}, status=401)
        return await handler(request)

    def _is_authorized(self, request: web.Request) -> bool:
        token = request.query.get('token', '')
        if token == config.ADMIN_TOKEN:
            return True
        auth = request.headers.get('Authorization', '').strip()
        if auth.startswith('Bearer '):
            return auth[7:] == config.ADMIN_TOKEN
        return False

    def _json(self, body: Dict[str, Any], status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps(body, ensure_ascii=False),
            status=status,
            content_type='application/json',
        )

    def _safe_limit(self, value: str, default: int = 20) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(1, min(parsed, 200))

    async def _handle_healthz(self, request: web.Request) -> web.Response:
        return self._json({'ok': True})

    async def _handle_index(self, request: web.Request) -> web.Response:
        if not os.path.isfile(config.WEB_INDEX_PATH):
            return web.Response(status=500, text='Dashboard not built')
        return web.FileResponse(config.WEB_INDEX_PATH)

    async def _handle_v1_removed(self, request: web.Request) -> web.Response:
        return self._json({'code': 'v1_removed', 'message': 'Use /api/v2 endpoints'}, status=410)

    async def _handle_v2_kpis(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        data = await queries_v2.get_kpis(ctx)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})

    async def _handle_v2_revenue_trend(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        data = await queries_v2.get_revenue_trend(ctx)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})

    async def _handle_v2_user_segments(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        data = await queries_v2.get_user_segments(ctx)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})

    async def _handle_v2_explore_events(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        params = dict(request.query)
        data = await queries_v2.get_explore_events(ctx, params)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})

    async def _handle_v2_active_hour_of_day(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        data = await queries_v2.get_active_hour_of_day(ctx)
        meta = queries_v2.meta_from_context(ctx, {'timezoneNote': 'local_server'})
        return self._json({'data': data, 'meta': meta})

    async def _handle_v2_ranking_danmaku(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        limit = self._safe_limit(request.query.get('limit', '50'))
        data = await queries_v2.get_ranking_danmaku_authors(ctx, limit)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx, {'limit': limit})})

    async def _handle_v2_ranking_gifts(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        limit = self._safe_limit(request.query.get('limit', '50'))
        sort = (request.query.get('sort') or 'count').strip().lower()
        if sort not in ('count', 'amount'):
            sort = 'count'
        data = await queries_v2.get_ranking_gift_authors(ctx, limit, sort)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx, {'limit': limit, 'sort': sort})})

    async def _handle_v2_user_danmaku(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        params = dict(request.query)
        try:
            data = await queries_v2.explore_user_danmaku(ctx, params)
        except ValueError as e:
            return self._json({'error': str(e)}, status=400)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})

    async def _handle_v2_user_gifts(self, request: web.Request) -> web.Response:
        ctx = queries_v2.parse_context(dict(request.query))
        params = dict(request.query)
        try:
            data = await queries_v2.explore_user_gifts(ctx, params)
        except ValueError as e:
            return self._json({'error': str(e)}, status=400)
        return self._json({'data': data, 'meta': queries_v2.meta_from_context(ctx)})
