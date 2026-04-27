#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import sys
from typing import Optional

import blcsdk

import config
import listener
from queue_state import QueueState
from web_server import WebServer

logger = logging.getLogger("queue-manager")
shut_down_event: Optional[asyncio.Event] = None
web_server: Optional[WebServer] = None


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
        raise RuntimeError("SDK version is not compatible")

    state = QueueState()
    global web_server
    web_server = WebServer(state)
    await web_server.start()
    listener.init(web_server=web_server, queue_state=state)

    cfg = config.get_config()
    await blcsdk.log(
        f"queue-manager started, admin={web_server.admin_url}, overlay={web_server.overlay_url}, token={cfg.overlay_token}",
        logging.INFO,
    )


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
    if shut_down_event is not None:
        shut_down_event.set()


def init_logging():
    os.makedirs(config.LOG_PATH, exist_ok=True)
    filename = os.path.join(config.LOG_PATH, "queue-manager.log")
    stream_handler = logging.StreamHandler()
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename, encoding="utf-8", when="midnight", backupCount=7, delay=True
    )
    logging.basicConfig(
        format="{asctime} {levelname} [{name}]: {message}",
        style="{",
        level=logging.INFO,
        handlers=[stream_handler, file_handler],
    )


async def run():
    logger.info("queue-manager running")
    assert shut_down_event is not None
    await shut_down_event.wait()
    logger.info("queue-manager shutdown requested")


async def shut_down():
    listener.shut_down()
    if web_server is not None:
        await web_server.stop()
    await blcsdk.shut_down()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
