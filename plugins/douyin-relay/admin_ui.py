# -*- coding: utf-8 -*-
"""插件管理界面：展示 dycast 用的 WebSocket 地址，便于复制。"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import json
from typing import Any, Callable, Dict, Optional

import config

logger = logging.getLogger('douyin-relay.' + __name__)
_status_provider: Optional[Callable[[], Dict[str, Any]]] = None


def set_status_provider(provider: Callable[[], Dict[str, Any]]) -> None:
    global _status_provider
    _status_provider = provider


def _collect_status() -> Dict[str, Any]:
    if _status_provider is None:
        return {}
    try:
        return _status_provider() or {}
    except Exception:
        logger.exception('Failed to collect runtime status')
        return {'error': 'status provider failed'}


def _config_file_path() -> Optional[str]:
    for path in config.CONFIG_PATH_LIST:
        if os.path.exists(path):
            return path
    return None


def _open_config_in_file_manager(cfg_path: str) -> None:
    if sys.platform == 'win32':
        subprocess.run(['explorer', '/select,' + cfg_path], check=False)
    elif sys.platform == 'darwin':
        subprocess.run(['open', '-R', cfg_path], check=False)
    else:
        subprocess.run(['xdg-open', os.path.dirname(cfg_path)], check=False)


def open_plugin_admin_ui() -> None:
    """在 GUI 线程中阻塞运行直至窗口关闭（与 blivechat 其他插件一致）。"""
    try:
        import tkinter as tk
        import tkinter.font as tkfont
        from tkinter import messagebox, ttk
    except ImportError:
        logger.warning('tkinter 不可用，状态: %s', json.dumps(_collect_status(), ensure_ascii=False))
        return

    cfg = config.get_config()
    url = config.get_dycast_relay_ws_url()
    bind_host = (cfg.listen_host or '').strip() or '127.0.0.1'
    path_display = config.normalized_ws_path(cfg.ws_path)

    root = tk.Tk()
    root.title('抖音弹幕中继 — 管理')
    root.resizable(True, False)
    root.minsize(420, 0)

    pad = {'padx': 12, 'pady': 8}

    frm = ttk.Frame(root, padding=8)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text='将下列地址粘贴到 dycast 右侧「WS地址」，连接房间后点击「转发」：').pack(anchor=tk.W, **pad)

    row = ttk.Frame(frm)
    row.pack(fill=tk.X, **pad)
    var = tk.StringVar(value=url)
    mono = tkfont.nametofont('TkFixedFont').actual()
    entry = ttk.Entry(row, textvariable=var, font=(mono['family'], mono['size'] + 1))
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    entry.select_range(0, tk.END)
    entry.focus_set()

    def on_copy():
        root.clipboard_clear()
        root.clipboard_append(var.get())
        root.update()
        messagebox.showinfo('已复制', 'WebSocket 地址已复制到剪贴板。', parent=root)

    ttk.Button(row, text='复制', command=on_copy).pack(side=tk.RIGHT)

    hint = (
        f'插件监听：{bind_host}:{cfg.listen_port}{path_display}。'
        f'若 dycast 在另一台电脑，请将地址中的主机名改为本机局域网 IP。'
    )
    ttk.Label(frm, text=hint, wraplength=480, justify=tk.LEFT).pack(anchor=tk.W, **pad)

    ttk.Label(frm, text='运行状态（最小可观测）').pack(anchor=tk.W, padx=12, pady=(4, 0))
    status_var = tk.StringVar(value='{}')
    status_entry = ttk.Entry(frm, textvariable=status_var, font=(mono['family'], mono['size']))
    status_entry.pack(fill=tk.X, padx=12, pady=(4, 8))

    def render_status() -> None:
        status = _collect_status()
        status_var.set(json.dumps(status, ensure_ascii=False, sort_keys=True))
        root.after(1000, render_status)

    render_status()

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill=tk.X, **pad)

    def on_open_config():
        p = _config_file_path()
        if not p:
            messagebox.showwarning('未找到配置', '请确认存在 data/config.ini 或 data/config.example.ini。', parent=root)
            return
        _open_config_in_file_manager(p)

    ttk.Button(btn_row, text='打开配置文件所在目录', command=on_open_config).pack(side=tk.LEFT)
    ttk.Button(btn_row, text='关闭', command=root.destroy).pack(side=tk.RIGHT)

    root.mainloop()
