#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import json
import logging.handlers
import os
import signal
import sys
from typing import *

import blcsdk
from cachetools import TTLCache

import config
from douyin_client import DouyinClient, StubDirectMessageSource
from douyin_protocol import DouyinProtocol
import listener
import mapper
import admin_ui
from injector import Injector
from relay_server import DouyinRelayServer

logger = logging.getLogger('douyin-relay')

shut_down_event: Optional[asyncio.Event] = None
_dedup: Optional[TTLCache] = None
_injector: Optional[Injector] = None
_relay: Optional[DouyinRelayServer] = None
_direct_client: Optional[DouyinClient] = None
_protocol: Optional[DouyinProtocol] = None


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

    global _dedup, _injector, _relay, _direct_client, _protocol
    cfg = config.get_config()
    _dedup = TTLCache(maxsize=cfg.dedup_max_size, ttl=cfg.dedup_ttl_seconds)
    _injector = Injector(cfg.inject_queue_max, cfg.inject_concurrency)
    await _injector.start()
    _protocol = DouyinProtocol()
    admin_ui.set_status_provider(get_runtime_status)

    if cfg.mode == 'relay':
        _relay = DouyinRelayServer(
            cfg.listen_host,
            cfg.listen_port,
            cfg.ws_path,
            on_text=_on_ws_text,
        )
        await _relay.start()
        await blcsdk.log(
            f'抖音中继已启动，请在 dycast 填写 ws://{cfg.listen_host}:{cfg.listen_port}{cfg.ws_path}',
            logging.INFO,
        )
    else:
        source = StubDirectMessageSource(_protocol, cfg.douyin_room_id)
        _direct_client = DouyinClient(
            _protocol,
            source,
            _on_protocol_payload,
            max_retries=cfg.direct_max_retries,
            backoff_base_seconds=cfg.direct_backoff_base_seconds,
            backoff_max_seconds=cfg.direct_backoff_max_seconds,
        )
        if cfg.auto_start:
            await _direct_client.start()
            await blcsdk.log('抖音 direct 模式已启动（stub 消息源）', logging.INFO)
        else:
            await blcsdk.log('抖音 direct 模式未自动启动（auto_start=false）', logging.WARNING)


def _dedup_key(msg: dict) -> str:
    method = str(msg.get('method') or '')
    mid = msg.get('id')
    if mid:
        return f'{method}:{mid}'
    blob = json.dumps(msg, ensure_ascii=False, sort_keys=True)[:400]
    return f'{method}:h{hash(blob)}'


async def _on_ws_text(raw: str) -> None:
    assert _protocol is not None
    kind, payload = _protocol.parse_raw_payload(raw)
    await _on_protocol_payload(kind, payload)


async def _on_protocol_payload(kind: str, payload: Any) -> None:
    if kind == 'unknown' or payload is None:
        return
    if kind == 'live_info' and isinstance(payload, dict):
        title = payload.get('title', '')
        room = payload.get('roomNum') or payload.get('roomId', '')
        logger.info('dycast live info: room=%s title=%s', room, title)
        return
    if kind != 'messages':
        return

    cfg = config.get_config()
    assert _dedup is not None and _injector is not None

    for item in payload:
        if not isinstance(item, dict):
            continue
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
        _dedup[key] = True
        await _injector.enqueue(mapped)


def get_runtime_status() -> Dict[str, Any]:
    cfg = config.get_config()
    injector_metrics: Dict[str, Any] = {}
    if _injector is not None:
        injector_metrics = _injector.get_metrics()
    direct_snapshot: Dict[str, Any] = {}
    if _direct_client is not None:
        direct_snapshot = _direct_client.get_runtime_snapshot()
    state = direct_snapshot.get('state', 'stopped') if cfg.mode == 'direct' else 'n/a'
    reconnect_count = int(direct_snapshot.get('reconnect_count', 0)) if cfg.mode == 'direct' else 0
    last_error = str(direct_snapshot.get('last_error') or '')
    return {
        'current_mode': cfg.mode,
        'state': state,
        'sent': int(injector_metrics.get('sent', 0)),
        'dropped': int(injector_metrics.get('dropped', 0)),
        'queue_size': int(injector_metrics.get('queue_size', 0)),
        'reconnect_count': reconnect_count,
        'last_error': last_error,
    }


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
    global _relay, _injector, _direct_client
    listener.shut_down()
    if _relay is not None:
        await _relay.stop()
        _relay = None
    if _direct_client is not None:
        await _direct_client.stop()
        _direct_client = None
    if _injector is not None:
        await _injector.stop()
        _injector = None
    logger.info('runtime status(final): %s', json.dumps(get_runtime_status(), ensure_ascii=False, sort_keys=True))
    await blcsdk.shut_down()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
