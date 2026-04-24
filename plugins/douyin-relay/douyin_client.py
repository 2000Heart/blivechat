from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Literal, Optional, Protocol

from douyin_protocol import DouyinProtocol

logger = logging.getLogger('douyin-relay.' + __name__)

OnProtocolPayload = Callable[[str, object], Awaitable[None]]
DirectState = Literal['idle', 'connecting', 'connected', 'reconnecting', 'failed', 'stopped']


class DirectMessageSource(Protocol):
    async def next_raw_payload(self) -> str:
        ...


class StubDirectMessageSource:
    def __init__(self, protocol: DouyinProtocol, room_id: str, interval_seconds: float = 2.0):
        self._protocol = protocol
        self._room_id = room_id
        self._interval_seconds = max(0.5, interval_seconds)
        self._seq = 0

    async def next_raw_payload(self) -> str:
        await asyncio.sleep(self._interval_seconds)
        self._seq += 1
        return self._protocol.build_stub_chat_raw(seq=self._seq, room_id=self._room_id)


class DouyinClient:
    """direct 模式客户端（M1: 可插拔消息源 + 协议解析）。"""

    def __init__(
        self,
        protocol: DouyinProtocol,
        source: DirectMessageSource,
        on_payload: OnProtocolPayload,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        backoff_max_seconds: float = 20.0,
    ):
        self._protocol = protocol
        self._source = source
        self._on_payload = on_payload
        self._max_retries = max(0, max_retries)
        self._backoff_base_seconds = max(0.5, backoff_base_seconds)
        self._backoff_max_seconds = max(self._backoff_base_seconds, backoff_max_seconds)
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._state: DirectState = 'idle'
        self._reconnect_count = 0
        self._last_error = ''

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        if self._task is not None and self._task.done():
            self._task = None
        self._running = True
        self._last_error = ''
        self._set_state('connecting')
        self._task = asyncio.create_task(self._run(), name='douyin-direct-client')
        logger.info(
            'Douyin direct client started max_retries=%d (max consecutive failures before stop)',
            self._max_retries,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._set_state('stopped')
        logger.info('Douyin direct client stopped')

    def get_runtime_snapshot(self) -> Dict[str, object]:
        return {
            'state': self._state,
            'reconnect_count': self._reconnect_count,
            'last_error': self._last_error,
            'running': self._running,
        }

    def _set_state(self, state: DirectState) -> None:
        if state == self._state:
            return
        prev = self._state
        self._state = state
        logger.info('direct state %s -> %s', prev, state)

    async def _run(self) -> None:
        retries = 0
        connected_once = False
        try:
            while self._running:
                try:
                    raw = await self._source.next_raw_payload()
                    if not connected_once:
                        connected_once = True
                        retries = 0
                        self._set_state('connected')
                    kind, payload = self._protocol.parse_raw_payload(raw)
                    await self._on_payload(kind, payload)
                    retries = 0
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    retries += 1
                    self._reconnect_count += 1
                    self._last_error = repr(e)
                    logger.exception(
                        'direct loop error, consecutive_failures=%d/%d',
                        retries,
                        self._max_retries,
                    )
                    if retries >= self._max_retries:
                        self._set_state('failed')
                        logger.error(
                            'direct loop failed permanently after reaching consecutive_failures limit (%d/%d)',
                            retries,
                            self._max_retries,
                        )
                        break
                    self._set_state('reconnecting')
                    delay = min(self._backoff_max_seconds, self._backoff_base_seconds * (2 ** (retries - 1)))
                    logger.warning(
                        'direct reconnecting in %.1fs (consecutive_failures=%d/%d)',
                        delay,
                        retries,
                        self._max_retries,
                    )
                    await asyncio.sleep(delay)
                    self._set_state('connecting')
        except asyncio.CancelledError:
            raise
        finally:
            self._running = False
            if self._state not in ('failed', 'stopped'):
                self._set_state('stopped')
