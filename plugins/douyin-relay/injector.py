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

    def get_metrics(self) -> Dict[str, int]:
        return {
            'sent': self._sent,
            'dropped': self._dropped,
            'queue_size': self._queue.qsize(),
            'queue_max': self._queue.maxsize,
        }

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
                try:
                    guard_level = max(0, int(item.get('guard_level', 0)))
                except (TypeError, ValueError):
                    guard_level = 0
                if kind == 'gift':
                    gift_name = str(item.get('gift_name', '礼物'))
                    gift_num = int(item.get('num', 1))
                    total_coin = int(item.get('total_coin', 0))
                    logger.info(
                        'gift dual-send start worker=%d gift=%s num=%d total_coin=%d uid=%s',
                        wid,
                        gift_name,
                        gift_num,
                        total_coin,
                        str(item.get('uid', '')),
                    )
                    await blcsdk.send_gift(
                        gift_name,
                        num=gift_num,
                        author_name=item.get('author_name', ''),
                        gift_id=int(item.get('gift_id', 0)),
                        gift_icon_url=item.get('gift_icon_url', ''),
                        total_coin=total_coin,
                        total_free_coin=int(item.get('total_free_coin', 0)),
                        uid=item.get('uid', ''),
                        avatar_url=item.get('avatar_url', ''),
                        guard_level=guard_level,
                        medal_level=medal_level,
                        medal_name=str((mn or '粉丝团') if medal_level > 0 else ''),
                        identity_ext=item.get('identity_ext', {}),
                    )
                    # # 调试双线发送：礼物同时以文本弹幕注入，便于定位是礼物渲染还是链路问题
                    # await blcsdk.send_text(
                    #     content=f"[礼物文本] {gift_name} x{gift_num}",
                    #     author_name=item.get('author_name', ''),
                    #     uid=item.get('uid', ''),
                    #     avatar_url=item.get('avatar_url', ''),
                    #     guard_level=guard_level,
                    #     medal_level=medal_level,
                    #     medal_name=str(mn or ''),
                    #     identity_ext=item.get('identity_ext', {}),
                    # )
                    logger.info('gift dual-send done worker=%d gift=%s num=%d', wid, gift_name, gift_num)
                else:
                    await blcsdk.send_text(
                        content=item['content'],
                        author_name=item.get('author_name', ''),
                        uid=item.get('uid', ''),
                        avatar_url=item.get('avatar_url', ''),
                        guard_level=guard_level,
                        medal_level=medal_level,
                        medal_name=str((mn or '粉丝团') if medal_level > 0 else ''),
                        content_type=int(item.get('content_type', 0)),
                        content_type_params=item.get('content_type_params', []),
                        identity_ext=item.get('identity_ext', {}),
                    )
                self._sent += 1
            except Exception:
                logger.exception('inject failed worker=%d kind=%s', wid, item.get('kind', 'text'))
