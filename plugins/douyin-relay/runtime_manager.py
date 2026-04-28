from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
import subprocess
import signal
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dycast_bridge_client import DycastBridgeClient

logger = logging.getLogger('douyin-relay.' + __name__)


def _quote_exec_for_shell(exe_path: str) -> str:
    # Windows asyncio.create_subprocess_shell 走 cmd.exe，单引号不会被当作引号。
    # shlex.quote 在 Windows 会产生单引号，导致“文件名、目录名或卷标语法不正确”。
    if os.name == 'nt':
        return subprocess.list2cmdline([exe_path])
    return shlex.quote(exe_path)


@dataclass
class SidecarRuntimeConfig:
    host: str
    port: int
    start_timeout_seconds: int
    node_exe: str
    node_cmd: str
    dycast_path: str


class DycastRuntimeManager:
    def __init__(self, cfg: SidecarRuntimeConfig):
        self._cfg = cfg
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._client = DycastBridgeClient(cfg.host, cfg.port, timeout_seconds=3.0)
        self._last_error = ''

    def bridge_client(self) -> DycastBridgeClient:
        return self._client

    def snapshot(self) -> Dict[str, Any]:
        running = self._proc is not None and self._proc.returncode is None
        return {
            'running': running,
            'pid': self._proc.pid if running else 0,
            'host': self._cfg.host,
            'port': self._cfg.port,
            'last_error': self._last_error,
        }

    async def start(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            return
        if not os.path.isdir(self._cfg.dycast_path):
            raise RuntimeError(f'dycast path not found: {self._cfg.dycast_path}')
        cmd = self._cfg.node_cmd.format(
            port=self._cfg.port,
            node=_quote_exec_for_shell(self._cfg.node_exe),
        )
        kw: Dict[str, Any] = {
            'cwd': self._cfg.dycast_path,
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.STDOUT,
            'env': os.environ.copy(),
        }
        if os.name != 'nt':
            kw['start_new_session'] = True
        self._proc = await asyncio.create_subprocess_shell(cmd, **kw)
        asyncio.create_task(self._drain_output(), name='dycast-sidecar-log')
        await self._wait_until_ready()

    async def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.returncode is None:
            if os.name != 'nt':
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    self._proc.terminate()
            else:
                self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                if os.name != 'nt':
                    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                        os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                self._proc.kill()
                await self._proc.wait()
        self._proc = None

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def _wait_until_ready(self) -> None:
        deadline = asyncio.get_running_loop().time() + max(5, self._cfg.start_timeout_seconds)
        while True:
            if self._proc is not None and self._proc.returncode is not None:
                raise RuntimeError(f'dycast sidecar exited early: code={self._proc.returncode}')
            try:
                data = self._client.status()
                if isinstance(data, dict) and data.get('ok'):
                    return
            except Exception as e:
                self._last_error = str(e)
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f'dycast sidecar start timeout: {self._last_error}')
            await asyncio.sleep(0.6)

    async def _drain_output(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                logger.info('[dycast-sidecar] %s', line.decode('utf-8', errors='replace').rstrip())
        except Exception:
            logger.exception('dycast sidecar output reader failed')
        finally:
            with contextlib.suppress(Exception):
                if proc.returncode is None:
                    await proc.wait()
