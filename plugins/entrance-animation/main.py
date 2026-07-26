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
        sdk_parent = os.path.join(cur, 'blcsdk')
        if os.path.isfile(os.path.join(sdk_parent, 'blcsdk', '__init__.py')):
            if sdk_parent not in sys.path:
                sys.path.insert(0, sdk_parent)
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


_inject_project_root_for_local_packages()

import blcsdk

import config
import listener
import store
from web_server import EntranceAnimationWebServer

logger = logging.getLogger('entrance-animation')

shut_down_event: Optional[asyncio.Event] = None
web_server: Optional[EntranceAnimationWebServer] = None


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

    store.load()
    all_data = store.get_all()
    enabled_users = sum(1 for u in all_data['users'].values() if u.get('enabled', True) and u.get('animationId'))
    logger.info(
        'Config loaded: users=%d (enabled_with_animation=%d) animations=%d global.enabled=%s',
        len(all_data['users']), enabled_users, len(all_data['animations']),
        all_data['global'].get('enabled', True),
    )

    await blcsdk.init()
    if not blcsdk.is_sdk_version_compatible():
        raise RuntimeError('SDK version is not compatible')

    global web_server
    web_server = EntranceAnimationWebServer()
    await web_server.start()

    listener.init(web_server)
    logger.info('Entrance animation plugin started')
    logger.info('Admin URL: %s', config.build_admin_url())
    logger.info('OBS overlay URL: %s', config.build_overlay_url())


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
    if shut_down_event is not None:
        shut_down_event.set()


def init_logging():
    filename = os.path.join(config.LOG_PATH, 'entrance-animation.log')
    stream_handler = logging.StreamHandler()
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename, encoding='utf-8', when='midnight', backupCount=7, delay=True
    )
    log_level = logging.DEBUG if os.environ.get('ENTRANCE_ANIMATION_DEBUG') else logging.INFO
    logging.basicConfig(
        format='{asctime} {levelname} [{name}]: {message}',
        style='{',
        level=log_level,
        handlers=[stream_handler, file_handler],
    )
    if log_level == logging.DEBUG:
        logger.debug('Debug logging enabled (ENTRANCE_ANIMATION_DEBUG=1)')


async def run():
    logger.info('Waiting for messages...')
    await shut_down_event.wait()
    logger.info('Start to shut down')


async def shut_down():
    global web_server
    listener.shut_down()
    if web_server is not None:
        await web_server.stop()
        web_server = None
    await blcsdk.shut_down()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
