#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import logging.handlers
import os
import signal
import sys
from typing import *


def _inject_project_root_for_local_packages() -> None:
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "blcsdk")):
            if cur not in sys.path:
                sys.path.append(cur)
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


_inject_project_root_for_local_packages()

import blcsdk
import config
import listener
import migrate_v2
import queries_v2
from web_server import DataAnalyticsWebServer

logger = logging.getLogger('data-analytics')

shut_down_event: Optional[asyncio.Event] = None
web_server: Optional[DataAnalyticsWebServer] = None


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
    _prepare_v2_database()

    await blcsdk.init()
    if not blcsdk.is_sdk_version_compatible():
        raise RuntimeError('SDK version is not compatible')

    await listener.init()
    global web_server
    web_server = DataAnalyticsWebServer()
    await web_server.start()
    logger.info('Admin dashboard URL: %s', config.build_admin_url())


def _prepare_v2_database() -> None:
    queries_v2.ensure_v2_schema()
    if not os.path.exists(config.DB_PATH):
        if os.path.exists(config.DB_BACKUP_PATH):
            logger.info('Legacy backup exists: %s (manual cleanup if no longer needed)', config.DB_BACKUP_PATH)
        logger.info('No legacy database found, running in v2-only mode: %s', config.DB_V2_PATH)
        return

    logger.info('Legacy database detected, migration required: %s', config.DB_PATH)
    result = migrate_v2.run(full=True)
    reconcile = result.get('reconcile', {})
    if not _reconcile_ok(reconcile):
        raise RuntimeError(f'Legacy migration reconcile failed: {reconcile}')

    if os.path.exists(config.DB_BACKUP_PATH):
        logger.warning('Legacy backup already exists and will be replaced: %s', config.DB_BACKUP_PATH)
    os.replace(config.DB_PATH, config.DB_BACKUP_PATH)
    logger.info('Legacy database migrated and renamed to backup: %s', config.DB_BACKUP_PATH)
    logger.info('Migration result: rows=%s reconcile=%s', result.get('rows'), reconcile)
    logger.info('Backup file is not auto-deleted, cleanup manually when appropriate')


def _reconcile_ok(reconcile: Dict[str, Any]) -> bool:
    for key in ('gift_delta', 'member_delta', 'sc_delta'):
        value = float(reconcile.get(key, 0.0) or 0.0)
        if abs(value) > config.RECONCILE_EPSILON:
            logger.error('Reconcile mismatch: %s=%s (epsilon=%s)', key, value, config.RECONCILE_EPSILON)
            return False
    return True


def init_signal_handlers():
    global shut_down_event
    shut_down_event = asyncio.Event()

    signums = (signal.SIGINT, signal.SIGTERM)
    try:
        loop = asyncio.get_running_loop()
        for signum in signums:
            loop.add_signal_handler(signum, start_shut_down)
    except NotImplementedError:
        # 不太安全，但Windows只能用这个
        for signum in signums:
            signal.signal(signum, start_shut_down)


def start_shut_down(*_args):
    shut_down_event.set()


def init_logging():
    filename = os.path.join(config.LOG_PATH, 'data-analytics.log')
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
    logger.info('Data analytics plugin running, database: %s', config.DB_V2_PATH)
    logger.info('Waiting for messages...')
    await shut_down_event.wait()
    logger.info('Start to shut down')


async def shut_down():
    global web_server
    if web_server is not None:
        await web_server.stop()
        web_server = None
    listener.shut_down()
    await blcsdk.shut_down()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

