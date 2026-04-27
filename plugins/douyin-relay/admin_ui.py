# -*- coding: utf-8 -*-
"""插件管理界面：展示 dycast 用的 WebSocket 地址，便于复制。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import webbrowser
from typing import Any, Callable, Dict, Optional

import config

logger = logging.getLogger('douyin-relay.' + __name__)
_status_provider: Optional[Callable[[], Dict[str, Any]]] = None
_action_handler: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None
_plugin_loop: Optional[asyncio.AbstractEventLoop] = None
_admin_ui_task: Optional[asyncio.Task] = None


def set_status_provider(provider: Callable[[], Dict[str, Any]]) -> None:
    global _status_provider
    _status_provider = provider


def set_action_handler(handler: Callable[[str, Dict[str, Any]], Dict[str, Any]]) -> None:
    global _action_handler
    _action_handler = handler


def bind_plugin_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """供 main 在 asyncio 初始化后绑定；用于从管理窗口线程安全地投递协程。"""
    global _plugin_loop
    _plugin_loop = loop


def run_on_plugin_loop(fn: Callable[[], Any]) -> None:
    """在插件 asyncio 线程执行 fn（如 create_task 必须在 loop 线程调用）。"""
    loop = _plugin_loop
    if loop is None:
        raise RuntimeError('plugin event loop not bound')
    loop.call_soon_threadsafe(fn)


def _collect_status() -> Dict[str, Any]:
    if _status_provider is None:
        return {}
    try:
        return _status_provider() or {}
    except Exception:
        logger.exception('Failed to collect runtime status')
        return {'error': 'status provider failed'}


def _run_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if _action_handler is None:
        return {'ok': False, 'error': 'action handler unavailable'}
    try:
        return _action_handler(action, payload) or {}
    except Exception:
        logger.exception('Failed to run action: %s', action)
        return {'ok': False, 'error': 'action failed'}


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


def _dycast_preview_url(cfg: config.AppConfig) -> str:
    host = (cfg.sidecar_host or '').strip()
    if host in ('', '0.0.0.0', '::'):
        host = '127.0.0.1'
    return f'http://{host}:{cfg.sidecar_port}/'


def open_plugin_admin_ui() -> None:
    """
    在插件 asyncio 线程上打开 Tk（macOS 上子线程跑 Tk 常卡死或无窗口），
    但不使用 mainloop()：用 update + await sleep 协作泵送，避免阻塞 WS 心跳。
    """
    global _admin_ui_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning('抖音中继管理界面无法打开：当前无 asyncio running loop')
        return
    if _admin_ui_task is not None and not _admin_ui_task.done():
        logger.info('抖音中继管理窗口已在运行，忽略重复打开')
        return

    async def _runner() -> None:
        global _admin_ui_task
        try:
            await _open_plugin_admin_window_async()
        except Exception:
            logger.exception('plugin admin UI task failed')
        finally:
            _admin_ui_task = None

    _admin_ui_task = loop.create_task(_runner(), name='douyin-relay-admin-ui')


async def _open_plugin_admin_window_async() -> None:
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

    ttk.Label(frm, text='relay 地址（legacy 模式可手工使用；sidecar 模式由插件自动下发）：').pack(anchor=tk.W, **pad)

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

    ttk.Label(frm, text='抖音请求头或 Cookie（sidecar 使用）').pack(anchor=tk.W, padx=12, pady=(4, 0))
    cookie_var = tk.StringVar(value=str(cfg.douyin_cookie or ''))
    cookie_entry = ttk.Entry(frm, textvariable=cookie_var)
    cookie_entry.pack(fill=tk.X, padx=12, pady=(4, 8))

    ttk.Label(frm, text='抖音房间号（sidecar 使用）').pack(anchor=tk.W, padx=12, pady=(4, 0))
    room_var = tk.StringVar(value=str(cfg.douyin_room_id or ''))
    room_entry = ttk.Entry(frm, textvariable=room_var)
    room_entry.pack(fill=tk.X, padx=12, pady=(4, 8))

    ttk.Label(frm, text='转发弹幕类型（写入 config.ini [relay]）').pack(anchor=tk.W, padx=12, pady=(4, 0))
    include_member_var = tk.BooleanVar(value=bool(cfg.include_member))
    include_social_var = tk.BooleanVar(value=bool(cfg.include_social))
    row_include = ttk.Frame(frm)
    row_include.pack(fill=tk.X, padx=12, pady=(4, 8))
    ttk.Checkbutton(row_include, text='进入直播间', variable=include_member_var).pack(side=tk.LEFT)
    ttk.Checkbutton(row_include, text='关注主播', variable=include_social_var).pack(side=tk.LEFT, padx=(16, 0))

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

    def on_save_settings():
        new_cookie = cookie_var.get().strip()
        new_room = room_var.get().strip()
        ok = config.update_relay_config_values({
            'douyin_cookie': new_cookie,
            'douyin_room_id': new_room,
            'include_member': 'true' if include_member_var.get() else 'false',
            'include_social': 'true' if include_social_var.get() else 'false',
        })
        if ok:
            messagebox.showinfo('保存成功', '房间号/Cookie 已保存到 config.ini 并完成重载。', parent=root)
        else:
            messagebox.showerror('保存失败', '保存或重载配置失败，请查看插件日志。', parent=root)

    def on_sidecar_connect():
        ret = _run_action(
            'sidecar',
            {'op': 'connect', 'room_id': room_var.get().strip(), 'raw_headers': cookie_var.get().strip()},
        )
        if ret.get('ok'):
            messagebox.showinfo('已执行', '已向 sidecar 下发连接命令。', parent=root)
        else:
            messagebox.showerror('执行失败', str(ret.get('error') or ret), parent=root)

    def on_sidecar_disconnect():
        ret = _run_action('sidecar', {'op': 'disconnect'})
        if ret.get('ok'):
            messagebox.showinfo('已执行', '已向 sidecar 下发断开命令。', parent=root)
        else:
            messagebox.showerror('执行失败', str(ret.get('error') or ret), parent=root)

    def on_sidecar_restart():
        ret = _run_action('sidecar', {'op': 'restart'})
        if ret.get('ok'):
            messagebox.showinfo('已执行', '已触发 sidecar 重启。', parent=root)
        else:
            messagebox.showerror('执行失败', str(ret.get('error') or ret), parent=root)

    def on_open_dycast_preview():
        try:
            webbrowser.open_new_tab(_dycast_preview_url(cfg))
        except Exception:
            logger.exception('failed to open dycast preview page')
            messagebox.showerror('打开失败', '无法打开 dycast 预览页，请检查 sidecar 是否已启动。', parent=root)

    ttk.Button(btn_row, text='打开配置文件所在目录', command=on_open_config).pack(side=tk.LEFT)
    ttk.Button(btn_row, text='保存配置', command=on_save_settings).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(btn_row, text='打开预览', command=on_open_dycast_preview).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(btn_row, text='Sidecar 连接', command=on_sidecar_connect).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(btn_row, text='Sidecar 断开', command=on_sidecar_disconnect).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(btn_row, text='Sidecar 重启', command=on_sidecar_restart).pack(side=tk.LEFT, padx=(8, 0))

    closed = False

    def on_close_request() -> None:
        nonlocal closed
        closed = True
        try:
            root.quit()
        except tk.TclError:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

    ttk.Button(btn_row, text='关闭', command=on_close_request).pack(side=tk.RIGHT)
    root.protocol('WM_DELETE_WINDOW', on_close_request)

    # 协作泵送：不占用 mainloop，以便同线程上的 aiohttp / 心跳继续运行
    try:
        while not closed:
            try:
                if not root.winfo_exists():
                    break
            except tk.TclError:
                break
            try:
                root.update()
            except tk.TclError:
                break
            await asyncio.sleep(0.02)
    finally:
        closed = True
        try:
            if root.winfo_exists():
                root.destroy()
        except tk.TclError:
            pass
