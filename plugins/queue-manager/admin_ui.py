# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import webbrowser

logger = logging.getLogger("queue-manager." + __name__)


def open_plugin_admin_ui(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        logger.exception("failed to open admin ui: %s", url)
