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
import douyin_cookie_help

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
        from tkinter import messagebox, scrolledtext, ttk
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

    cookie_tool = ttk.Frame(frm)
    cookie_tool.pack(fill=tk.X, padx=12, pady=(2, 4))

    def on_open_douyin_live():
        try:
            webbrowser.open_new_tab(douyin_cookie_help.DOUYIN_LIVE_URL)
        except Exception:
            logger.exception('open douyin live')
            messagebox.showerror('打开失败', '无法打开浏览器，请手动访问 live.douyin.com', parent=root)

    def on_show_cookie_help():
        help_win = tk.Toplevel(root)
        help_win.title('如何从浏览器获取 Cookie')
        help_win.transient(root)
        help_win.geometry('560x420')
        txt = scrolledtext.ScrolledText(
            help_win, wrap=tk.WORD, width=72, height=18, font=(mono['family'], mono['size'])
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, douyin_cookie_help.COOKIE_HELP_TEXT)
        txt.insert(tk.END, '\n\n--- 小书签链接（新建书签时粘贴到「网址」）---\n\n')
        txt.insert(tk.END, douyin_cookie_help.bookmarklet_href())
        txt.configure(state=tk.DISABLED)
        btn_close = ttk.Frame(help_win)
        btn_close.pack(fill=tk.X, padx=8, pady=(0, 8))

        def copy_bm():
            help_win.clipboard_clear()
            help_win.clipboard_append(douyin_cookie_help.bookmarklet_href())
            help_win.update()
            messagebox.showinfo('已复制', '小书签链接已复制，请到浏览器新建书签并粘贴为网址。', parent=help_win)

        ttk.Button(btn_close, text='复制小书签链接', command=copy_bm).pack(side=tk.LEFT)
        ttk.Button(btn_close, text='关闭', command=help_win.destroy).pack(side=tk.RIGHT)

    def on_copy_bookmarklet_only():
        root.clipboard_clear()
        root.clipboard_append(douyin_cookie_help.bookmarklet_href())
        root.update()
        messagebox.showinfo(
            '已复制',
            '小书签链接已复制。\n在浏览器中新建书签，将网址替换为剪贴板内容；'
            '打开 live.douyin.com 已登录页面后点击该书签，即可把可见 Cookie 写入剪贴板。',
            parent=root,
        )

    ttk.Button(cookie_tool, text='打开抖音直播', command=on_open_douyin_live).pack(side=tk.LEFT)
    ttk.Button(cookie_tool, text='如何获取 Cookie…', command=on_show_cookie_help).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(cookie_tool, text='复制小书签链接', command=on_copy_bookmarklet_only).pack(side=tk.LEFT, padx=(8, 0))

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
        text = json.dumps(status, ensure_ascii=False, sort_keys=True)
        if text != status_var.get():
            status_var.set(text)
        root.after(1500, render_status)

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
            # Windows 上 Tk 的 update 很重：20ms 约等于 50Hz 会持续占满单核并拖慢同线程的 WS。
            # 50–80ms 仍足够响应点击与输入，CPU 占用显著下降。
            await asyncio.sleep(0.06)
    finally:
        closed = True
        try:
            if root.winfo_exists():
                root.destroy()
        except tk.TclError:
            pass


# -------------------- PySide6 implementation (override) --------------------
import concurrent.futures
import threading

_plugin_loop_thread_id: Optional[int] = None
_ui_lock = threading.Lock()
_ui_thread: Optional[threading.Thread] = None
_ui_bridge: Optional[Any] = None


def bind_plugin_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """绑定插件 asyncio loop，供 UI 线程安全调用。"""
    global _plugin_loop, _plugin_loop_thread_id
    _plugin_loop = loop
    _plugin_loop_thread_id = threading.get_ident()


def _is_plugin_thread() -> bool:
    return _plugin_loop_thread_id is not None and threading.get_ident() == _plugin_loop_thread_id


def _call_on_plugin_loop_sync(fn: Callable[[], Any], timeout: float = 8.0) -> Any:
    loop = _plugin_loop
    if loop is None:
        raise RuntimeError('plugin event loop not bound')
    if _is_plugin_thread():
        return fn()
    future: concurrent.futures.Future[Any] = concurrent.futures.Future()

    def _invoke() -> None:
        try:
            future.set_result(fn())
        except Exception as e:
            future.set_exception(e)

    loop.call_soon_threadsafe(_invoke)
    return future.result(timeout=timeout)


def _collect_status() -> Dict[str, Any]:
    if _status_provider is None:
        return {}
    try:
        return _call_on_plugin_loop_sync(lambda: (_status_provider() or {}), timeout=3.0)
    except Exception:
        logger.exception('Failed to collect runtime status')
        return {'error': 'status provider failed'}


def _run_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if _action_handler is None:
        return {'ok': False, 'error': 'action handler unavailable'}
    try:
        return _call_on_plugin_loop_sync(lambda: (_action_handler(action, payload) or {}), timeout=10.0)
    except Exception:
        logger.exception('Failed to run action: %s', action)
        return {'ok': False, 'error': 'action failed'}


def notify_status_changed() -> None:
    bridge = _ui_bridge
    if bridge is not None:
        try:
            bridge.statusChanged.emit()
        except Exception:
            logger.exception('Failed to emit statusChanged')


def _clear_ui_refs() -> None:
    global _ui_thread, _ui_bridge
    with _ui_lock:
        _ui_thread = None
        _ui_bridge = None


def open_plugin_admin_ui() -> None:
    global _ui_thread
    # macOS: Qt/Cocoa 要求主线程初始化 QApplication，插件场景下回退 Tk 以保证稳定可用。
    if sys.platform == 'darwin':
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

        _admin_ui_task = loop.create_task(_runner(), name='douyin-relay-admin-ui-tk')
        return

    with _ui_lock:
        if _ui_thread is not None and _ui_thread.is_alive():
            logger.info('抖音中继管理窗口已在运行，忽略重复打开')
            return
        _ui_thread = threading.Thread(target=_run_qt_admin_ui, name='douyin-relay-admin-ui', daemon=True)
        _ui_thread.start()


def _run_qt_admin_ui() -> None:
    global _ui_bridge
    try:
        from PySide6.QtCore import QObject, QTimer, Signal, Slot
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QDialog,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QStatusBar,
            QVBoxLayout,
            QWidget,
        )
    except Exception:
        logger.exception('PySide6 不可用，无法打开管理界面')
        _clear_ui_refs()
        return

    class UiBridge(QObject):
        statusChanged = Signal()
        statusTextReady = Signal(str)
        opDone = Signal(str)
        opFailed = Signal(str)
        saveDone = Signal(bool, str)

    class HelpDialog(QDialog):
        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self.setWindowTitle('如何从浏览器获取 Cookie')
            self.resize(640, 440)
            layout = QVBoxLayout(self)
            txt = QPlainTextEdit(self)
            txt.setReadOnly(True)
            txt.setPlainText(
                douyin_cookie_help.COOKIE_HELP_TEXT
                + '\n\n--- 小书签链接（新建书签时粘贴到「网址」）---\n\n'
                + douyin_cookie_help.bookmarklet_href()
            )
            layout.addWidget(txt)
            row = QHBoxLayout()
            copy_btn = QPushButton('复制小书签链接', self)
            close_btn = QPushButton('关闭', self)
            row.addWidget(copy_btn)
            row.addStretch(1)
            row.addWidget(close_btn)
            layout.addLayout(row)
            copy_btn.clicked.connect(
                lambda: QApplication.clipboard().setText(douyin_cookie_help.bookmarklet_href())
            )
            close_btn.clicked.connect(self.close)

    class MainWindow(QMainWindow):
        def __init__(self, bridge: UiBridge) -> None:
            super().__init__()
            self._bridge = bridge
            self._last_status = ''
            self._refreshing = False
            self._refresh_lock = threading.Lock()
            self._init_ui()
            self._bridge.statusChanged.connect(self.request_status_refresh)
            self._bridge.statusTextReady.connect(self.on_status_text_ready)
            self._bridge.opDone.connect(self.on_op_done)
            self._bridge.opFailed.connect(self.on_op_failed)
            self._bridge.saveDone.connect(self.on_save_done)
            self._timer = QTimer(self)
            self._timer.setInterval(2000)
            self._timer.timeout.connect(self.request_status_refresh)
            self._timer.start()
            self.request_status_refresh()

        def _init_ui(self) -> None:
            cfg = config.get_config()
            ws_url = config.get_dycast_relay_ws_url()
            bind_host = (cfg.listen_host or '').strip() or '127.0.0.1'
            path_display = config.normalized_ws_path(cfg.ws_path)
            self.setWindowTitle('抖音弹幕中继 - 管理')
            self.resize(860, 640)
            self.setMinimumSize(760, 560)
            self.setStyleSheet(
                'QWidget{font-size:13px;background:#f7f9fc;color:#1f1f1f;}'
                'QGroupBox{border:1px solid #d9dce3;border-radius:10px;margin-top:12px;'
                'font-weight:600;background:#fff;}'
                'QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}'
                'QLineEdit,QPlainTextEdit{border:1px solid #c7ccd7;border-radius:8px;padding:6px;background:#fff;}'
                'QPushButton{border:1px solid #c8cfda;border-radius:8px;padding:7px 12px;background:#f4f7fb;}'
                'QPushButton:hover{background:#eaf2ff;border-color:#8cb5ff;}'
                'QPushButton:pressed{background:#d9e8ff;}'
                'QPushButton#primary{background:#0f6cbd;color:#fff;border-color:#0f6cbd;}'
            )
            center = QWidget(self)
            root = QVBoxLayout(center)
            root.setContentsMargins(14, 12, 14, 12)
            root.setSpacing(12)

            relay_box = QGroupBox('Relay 地址', center)
            relay_layout = QGridLayout(relay_box)
            relay_layout.setColumnStretch(0, 1)
            self.relay_edit = QLineEdit(ws_url, relay_box)
            self.relay_edit.setReadOnly(True)
            copy_btn = QPushButton('复制', relay_box)
            copy_btn.setObjectName('primary')
            relay_layout.addWidget(self.relay_edit, 0, 0)
            relay_layout.addWidget(copy_btn, 0, 1)
            hint = QLabel(
                f'插件监听：{bind_host}:{cfg.listen_port}{path_display}。'
                f'若 dycast 在另一台电脑，请将地址中的主机名改为本机局域网 IP。',
                relay_box,
            )
            hint.setWordWrap(True)
            relay_layout.addWidget(hint, 1, 0, 1, 2)
            root.addWidget(relay_box)
            copy_btn.clicked.connect(self.on_copy_relay)

            status_box = QGroupBox('运行状态', center)
            status_layout = QVBoxLayout(status_box)
            self.status_text = QPlainTextEdit(status_box)
            self.status_text.setReadOnly(True)
            self.status_text.setMinimumHeight(120)
            status_layout.addWidget(self.status_text)
            root.addWidget(status_box)

            sidecar_box = QGroupBox('Sidecar 配置与操作', center)
            sidecar_layout = QVBoxLayout(sidecar_box)
            tool_row = QHBoxLayout()
            btn_live = QPushButton('打开抖音直播', sidecar_box)
            btn_help = QPushButton('如何获取 Cookie...', sidecar_box)
            btn_bm = QPushButton('复制小书签链接', sidecar_box)
            tool_row.addWidget(btn_live)
            tool_row.addWidget(btn_help)
            tool_row.addWidget(btn_bm)
            tool_row.addStretch(1)
            sidecar_layout.addLayout(tool_row)
            btn_live.clicked.connect(self.on_open_douyin_live)
            btn_help.clicked.connect(self.on_show_cookie_help)
            btn_bm.clicked.connect(self.on_copy_bookmarklet_only)

            sidecar_layout.addWidget(QLabel('抖音请求头或 Cookie（sidecar 使用）', sidecar_box))
            self.cookie_input = QPlainTextEdit(sidecar_box)
            self.cookie_input.setPlainText(str(cfg.douyin_cookie or ''))
            self.cookie_input.setMinimumHeight(100)
            sidecar_layout.addWidget(self.cookie_input)
            sidecar_layout.addWidget(QLabel('抖音房间号（sidecar 使用）', sidecar_box))
            self.room_input = QLineEdit(str(cfg.douyin_room_id or ''), sidecar_box)
            sidecar_layout.addWidget(self.room_input)

            sidecar_layout.addWidget(QLabel('转发弹幕类型（写入 config.ini [relay]）', sidecar_box))
            include_row = QHBoxLayout()
            self.include_member = QCheckBox('进入直播间', sidecar_box)
            self.include_member.setChecked(bool(cfg.include_member))
            self.include_social = QCheckBox('关注主播', sidecar_box)
            self.include_social.setChecked(bool(cfg.include_social))
            include_row.addWidget(self.include_member)
            include_row.addWidget(self.include_social)
            include_row.addStretch(1)
            sidecar_layout.addLayout(include_row)
            root.addWidget(sidecar_box)

            action_row = QHBoxLayout()
            btn_open_cfg = QPushButton('打开配置文件所在目录', center)
            btn_save = QPushButton('保存配置', center)
            btn_save.setObjectName('primary')
            btn_preview = QPushButton('打开预览', center)
            btn_connect = QPushButton('Sidecar 连接', center)
            btn_disconnect = QPushButton('Sidecar 断开', center)
            btn_restart = QPushButton('Sidecar 重启', center)
            btn_close = QPushButton('关闭', center)
            for btn in [btn_open_cfg, btn_save, btn_preview, btn_connect, btn_disconnect, btn_restart]:
                action_row.addWidget(btn)
            action_row.addStretch(1)
            action_row.addWidget(btn_close)
            root.addLayout(action_row)
            self.setCentralWidget(center)
            self.setStatusBar(QStatusBar(self))
            self.statusBar().showMessage('就绪')
            btn_open_cfg.clicked.connect(self.on_open_config)
            btn_save.clicked.connect(self.on_save_settings)
            btn_preview.clicked.connect(self.on_open_dycast_preview)
            btn_connect.clicked.connect(lambda: self._run_sidecar_action('connect'))
            btn_disconnect.clicked.connect(lambda: self._run_sidecar_action('disconnect'))
            btn_restart.clicked.connect(lambda: self._run_sidecar_action('restart'))
            btn_close.clicked.connect(self.close)

        @Slot()
        def request_status_refresh(self) -> None:
            with self._refresh_lock:
                if self._refreshing:
                    return
                self._refreshing = True

            def _worker() -> None:
                try:
                    text = json.dumps(_collect_status(), ensure_ascii=False, sort_keys=True)
                    self._bridge.statusTextReady.emit(text)
                finally:
                    with self._refresh_lock:
                        self._refreshing = False

            threading.Thread(target=_worker, daemon=True).start()

        @Slot(str)
        def on_status_text_ready(self, text: str) -> None:
            if text == self._last_status:
                return
            self._last_status = text
            self.status_text.setPlainText(text)

        @Slot(str)
        def on_op_done(self, msg: str) -> None:
            self.statusBar().showMessage(msg, 3000)

        @Slot(str)
        def on_op_failed(self, msg: str) -> None:
            self.statusBar().showMessage(msg, 5000)
            QMessageBox.warning(self, '执行失败', msg)

        @Slot(bool, str)
        def on_save_done(self, ok: bool, msg: str) -> None:
            if ok:
                self.statusBar().showMessage(msg, 3000)
                notify_status_changed()
            else:
                self.statusBar().showMessage(msg, 5000)
                QMessageBox.warning(self, '保存失败', msg)

        def on_copy_relay(self) -> None:
            QApplication.clipboard().setText(self.relay_edit.text())
            self.statusBar().showMessage('WebSocket 地址已复制到剪贴板', 2500)

        def on_open_douyin_live(self) -> None:
            try:
                webbrowser.open_new_tab(douyin_cookie_help.DOUYIN_LIVE_URL)
            except Exception:
                logger.exception('open douyin live')
                QMessageBox.warning(self, '打开失败', '无法打开浏览器，请手动访问 live.douyin.com')

        def on_show_cookie_help(self) -> None:
            HelpDialog(self).exec()

        def on_copy_bookmarklet_only(self) -> None:
            QApplication.clipboard().setText(douyin_cookie_help.bookmarklet_href())
            self.statusBar().showMessage('小书签链接已复制到剪贴板', 3000)

        def on_open_config(self) -> None:
            p = _config_file_path()
            if not p:
                QMessageBox.warning(self, '未找到配置', '请确认存在 data/config.ini 或 data/config.example.ini。')
                return
            _open_config_in_file_manager(p)

        def on_save_settings(self) -> None:
            data = {
                'douyin_cookie': self.cookie_input.toPlainText().strip(),
                'douyin_room_id': self.room_input.text().strip(),
                'include_member': 'true' if self.include_member.isChecked() else 'false',
                'include_social': 'true' if self.include_social.isChecked() else 'false',
            }

            def _worker() -> None:
                ok = config.update_relay_config_values(data)
                if ok:
                    self._bridge.saveDone.emit(True, '房间号/Cookie 已保存到 config.ini 并完成重载')
                else:
                    self._bridge.saveDone.emit(False, '保存或重载配置失败，请查看插件日志')

            threading.Thread(target=_worker, daemon=True).start()

        def _run_sidecar_action(self, op: str) -> None:
            payload: Dict[str, Any] = {'op': op}
            if op == 'connect':
                payload['room_id'] = self.room_input.text().strip()
                payload['raw_headers'] = self.cookie_input.toPlainText().strip()

            def _worker() -> None:
                ret = _run_action('sidecar', payload)
                if ret.get('ok'):
                    notify_status_changed()
                    self._bridge.opDone.emit(f'Sidecar {op} 指令已执行')
                else:
                    self._bridge.opFailed.emit(str(ret.get('error') or ret))

            threading.Thread(target=_worker, daemon=True).start()

        def on_open_dycast_preview(self) -> None:
            try:
                webbrowser.open_new_tab(_dycast_preview_url(config.get_config()))
            except Exception:
                logger.exception('failed to open dycast preview page')
                QMessageBox.warning(self, '打开失败', '无法打开 dycast 预览页，请检查 sidecar 是否已启动。')

        def closeEvent(self, event: Any) -> None:
            super().closeEvent(event)
            _clear_ui_refs()

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(True)
    bridge = UiBridge()
    with _ui_lock:
        _ui_bridge = bridge
    window = MainWindow(bridge)
    window.show()
    try:
        app.exec()
    finally:
        _clear_ui_refs()
