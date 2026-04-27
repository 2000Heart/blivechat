# -*- coding: utf-8 -*-
"""异步注入队列 + 并发 worker，避免阻塞 WS 接收。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import blcsdk

logger = logging.getLogger('douyin-relay.' + __name__)


class Injector:
    def __init__(self, queue_max: int, concurrency: int):
        self._queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue(maxsize=queue_max)
        self._concurrency = max(1, concurrency)
        self._workers: List[asyncio.Task] = []
        self._dropped = 0
        self._sent = 0

    async def start(self) -> None:
        for i in range(self._concurrency):
            self._workers.append(asyncio.create_task(self._worker(i), name=f'douyin-inject-{i}'))

    async def stop(self) -> None:
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info('Injector stopped sent=%d dropped_queue=%d', self._sent, self._dropped)

    async def enqueue(self, item: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped % 50 == 1:
                logger.warning('Inject queue full, dropped %d messages so far', self._dropped)

    async def _worker(self, wid: int) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            try:
                kind = item.get('kind', 'text')
                ml = item.get('medal_level', item.get('medalLevel', 0))
                mn = item.get('medal_name', item.get('medalName', ''))
                try:
                    medal_level = max(0, int(ml))
                except (TypeError, ValueError):
                    medal_level = 0
                if kind == 'gift':
                    await blcsdk.send_gift(
                        item['gift_name'],
                        num=int(item.get('num', 1)),
                        author_name=item.get('author_name', ''),
                        gift_id=int(item.get('gift_id', 0)),
                        gift_icon_url=item.get('gift_icon_url', ''),
                        total_coin=int(item.get('total_coin', 0)),
                        total_free_coin=int(item.get('total_free_coin', 0)),
                        uid=item.get('uid', ''),
                        avatar_url=item.get('avatar_url', ''),
                        medal_level=medal_level,
                        medal_name=str(mn or ''),
                    )
                else:
                    await blcsdk.send_text(
                        content=item['content'],
                        author_name=item.get('author_name', ''),
                        uid=item.get('uid', ''),
                        avatar_url=item.get('avatar_url', ''),
                        medal_level=medal_level,
                        medal_name=str(mn or ''),
                    )
                self._sent += 1
            except Exception:
                logger.exception('inject failed worker=%d kind=%s', wid, item.get('kind', 'text'))
