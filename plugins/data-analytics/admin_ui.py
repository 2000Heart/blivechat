# -*- coding: utf-8 -*-
import logging
import webbrowser

import config

logger = logging.getLogger('data-analytics.admin_ui')


def open_plugin_admin_ui() -> None:
    url = config.build_admin_url()
    try:
        webbrowser.open(url)
        logger.info('Opened admin dashboard: %s', url)
    except Exception:
        logger.exception('failed to open admin dashboard: %s', url)
