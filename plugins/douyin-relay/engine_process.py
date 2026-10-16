# -*- coding: utf-8 -*-
"""Headless dycast process. Stdout is protocol JSON; stderr is logs."""
import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import threading

import config

logger = logging.getLogger('douyin-relay.engine_process')

_LOG_LIMIT = 200
_SECRET_RE = re.compile(
    r'(?i)(sessionid|ttwid|passport_csrf_token|sid_guard|odin_tt|rawheaders|douyin_cookie|cookie)'
)
_EVENT_TYPES = frozenset(('probe', 'status', 'login', 'result', 'ready', 'live_info'))


def _redact_line(line: str) -> str:
    if _SECRET_RE.search(line):
        return 'redacted cookieLength=%d' % len(line)
    return line


class EngineProcess:
    def __init__(self, on_messages=None, on_event=None, node_exe='node', dycast_path='.', env=None, popen=None):
        self._on_messages = on_messages
        self._on_event = on_event
        self._node_exe = node_exe or 'node'
        self._dycast_path = dycast_path or '.'
        self._env = dict(env or {})
        self._popen = subprocess.Popen if popen is None else popen
        self.log_lines = []
        self.login_phase = ''
        self._stdout_buf = ''
        self._stderr_buf = ''
        self._proc = None
        self._running = False
        self._ready = False
        self._loop = None
        self._ready_async = None
        self._stdout_thread = None
        self._stderr_thread = None
        self._seq = 0
        self._lock = threading.Lock()
        self._accepted = {}

    def command_argv(self):
        return [
            self._node_exe,
            './node_modules/tsx/dist/cli.mjs',
            '--tsconfig',
            'tsconfig.sidecar.json',
            'src/sidecar/headless.ts',
        ]

    def subprocess_env(self):
        env = os.environ.copy()
        for key, value in self._env.items():
            env[str(key)] = str(value)
        return env

    async def start(self):
        if self.snapshot().get('running'):
            return
        self._loop = asyncio.get_running_loop()
        self._ready_async = asyncio.Event()
        self._ready = False
        kwargs = {
            'cwd': self._dycast_path,
            'env': self.subprocess_env(),
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'encoding': 'utf-8',
            'errors': 'replace',
            'bufsize': 1,
        }
        if os.name != 'nt':
            kwargs['start_new_session'] = True
        self._proc = self._popen(self.command_argv(), **kwargs)
        self._running = True
        self._stdout_thread = threading.Thread(
            target=self._read_stdout, name='douyin-engine-stdout', daemon=True
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr, name='douyin-engine-stderr', daemon=True
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        try:
            await asyncio.wait_for(self._ready_async.wait(), timeout=20)
        except asyncio.TimeoutError:
            self.stop()
            raise RuntimeError('douyin engine ready timeout')
        if not self.snapshot().get('running'):
            raise RuntimeError('douyin engine exited before ready')

    def stop(self):
        # Process exit only clears running. This method does not call start().
        proc = self._proc
        self._running = False
        if proc is None:
            return
        if proc.poll() is None:
            if os.name == 'nt':
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=8)
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except OSError:
                    proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except OSError:
                        proc.kill()
                    proc.wait(timeout=8)
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=1)
        self._proc = None

    def send(self, command):
        if not isinstance(command, dict):
            return {'ok': False, 'error': 'engine_not_ready'}
        payload = dict(command)
        if not str(payload.get('id') or '').strip():
            self._seq += 1
            payload['id'] = str(self._seq)
        cmd = str(payload.get('cmd') or '')
        if cmd in ('probe_live', 'connect'):
            payload['rawHeaders'] = self._current_cookie()
        cookie_length = len(str(payload.get('rawHeaders') or '')) if 'rawHeaders' in payload else 0
        logger.info('engine send cmd=%s id=%s cookieLength=%s', cmd, payload.get('id'), cookie_length)
        if not self.snapshot().get('running'):
            return {'ok': False, 'error': 'engine_not_ready'}
        proc = self._proc
        if proc is None or proc.stdin is None:
            return {'ok': False, 'error': 'engine_not_ready'}
        try:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
            proc.stdin.flush()
        except Exception:
            logger.error('engine stdin write failed cmd=%s', cmd)
            return {'ok': False, 'error': 'engine_not_ready'}
        return {'ok': True, 'id': payload['id']}

    def feed_stdout(self, data: str) -> None:
        self._stdout_buf += data
        while '\n' in self._stdout_buf:
            line, self._stdout_buf = self._stdout_buf.split('\n', 1)
            self._handle_stdout_line(line.strip('\r').strip())

    def feed_stderr(self, data: str) -> None:
        self._stderr_buf += data
        while '\n' in self._stderr_buf:
            line, self._stderr_buf = self._stderr_buf.split('\n', 1)
            text = line.strip('\r').strip()
            if text:
                self._append_log(text)

    def snapshot(self):
        running = self._is_running()
        with self._lock:
            logs = list(self.log_lines[-_LOG_LIMIT:])
        return {
            'running': running,
            'pid': int(self._proc.pid) if running and self._proc is not None else 0,
            'login_phase': self.login_phase,
            'logs': logs,
        }

    def _current_cookie(self) -> str:
        try:
            cfg = config.get_config()
        except Exception:
            return ''
        return str(getattr(cfg, 'douyin_cookie', '') or '')

    def _is_running(self) -> bool:
        proc = self._proc
        if proc is not None and proc.poll() is not None:
            self._running = False
        return bool(self._running and proc is not None and proc.poll() is None)

    def _append_log(self, line: str) -> None:
        redacted = _redact_line(line)
        with self._lock:
            self.log_lines.append(redacted)
            if len(self.log_lines) > _LOG_LIMIT:
                del self.log_lines[:-_LOG_LIMIT]

    def _handle_stdout_line(self, line: str) -> None:
        if not line:
            return
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self._append_log(line)
            return
        if not isinstance(obj, dict):
            self._append_log(line)
            return
        typ = str(obj.get('type') or '')
        if typ == 'messages':
            payload = obj.get('payload')
            if not isinstance(payload, list):
                payload = []
            self._dispatch(self._on_messages, payload)
            return
        if typ == 'login':
            self.login_phase = str(obj.get('phase') or '')
        if typ == 'result':
            result_id = str(obj.get('id') or '')
            if result_id:
                self._accepted[result_id] = bool(obj.get('ok'))
        if typ == 'ready':
            self._mark_ready()
        if typ in _EVENT_TYPES:
            self._dispatch(self._on_event, obj)
            return
        self._append_log(line)

    def _dispatch(self, fn, arg) -> None:
        if fn is None:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is loop:
                fn(arg)
                return
            loop.call_soon_threadsafe(fn, arg)
            return
        fn(arg)

    def _mark_ready(self) -> None:
        self._ready = True
        loop = self._loop
        event = self._ready_async
        if loop is None or event is None:
            return
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is loop:
            event.set()
        else:
            loop.call_soon_threadsafe(event.set)

    def _note_process_exit(self) -> None:
        # Stdout/stderr closing is not a restart. Leave running false until an explicit start().
        proc = self._proc
        if proc is not None and proc.poll() is not None:
            self._running = False

    def _read_stdout(self) -> None:
        proc = self._proc
        stream = getattr(proc, 'stdout', None) if proc is not None else None
        try:
            if stream is None:
                return
            while True:
                line = stream.readline()
                if not line:
                    break
                self.feed_stdout(line)
        finally:
            self._note_process_exit()
            self._mark_ready()

    def _read_stderr(self) -> None:
        proc = self._proc
        stream = getattr(proc, 'stderr', None) if proc is not None else None
        try:
            if stream is None:
                return
            while True:
                line = stream.readline()
                if not line:
                    break
                self.feed_stderr(line if line.endswith('\n') else line + '\n')
        finally:
            self._note_process_exit()
