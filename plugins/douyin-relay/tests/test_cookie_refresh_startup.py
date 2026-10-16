import asyncio
import importlib.util
import json
import pathlib
import sys
import types
import unittest
from unittest import mock

from supervisor import LiveSupervisor


def _load_main_module():
    fake_blcsdk = types.SimpleNamespace(
        init=lambda: None,
        is_sdk_version_compatible=lambda: True,
        log=lambda *_args, **_kwargs: None,
        shut_down=lambda: None,
    )
    sys.modules["blcsdk"] = fake_blcsdk
    sys.modules["cachetools"] = types.SimpleNamespace(TTLCache=dict)
    sys.modules["listener"] = types.SimpleNamespace(init=lambda: None, shut_down=lambda: None)
    sys.modules["mapper"] = types.SimpleNamespace(
        GIFT="WebcastGiftMessage",
        map_dy_payload=lambda *_args, **_kwargs: None,
    )

    class _InjectorStub:
        def __init__(self, *_args, **_kwargs):
            pass

        async def start(self):
            return None

        async def stop(self):
            return None

        async def enqueue(self, _item):
            return None

        def get_metrics(self):
            return {}

    sys.modules["injector"] = types.SimpleNamespace(Injector=_InjectorStub)
    plugin_dir = pathlib.Path(__file__).resolve().parents[1]
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    spec = importlib.util.spec_from_file_location(
        "douyin_relay_main_cookie_refresh",
        plugin_dir / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _cfg(**kwargs):
    values = dict(
        cookie_auto_refresh=True,
        douyin_room_id="9527",
        douyin_cookie="",
        cookie_silent_timeout_seconds=30,
        live_probe_interval_seconds=180,
    )
    values.update(kwargs)
    return types.SimpleNamespace(**values)


class _ScriptEngine:
    def __init__(self, mod, terminal_phase="need_login", consume_cookie="", fail_start=False, hang=False):
        self.mod = mod
        self.sent = []
        self.terminal_phase = terminal_phase
        self.consume_cookie = consume_cookie
        self.fail_start = fail_start
        self.hang = hang
        self.login_phase = ""
        self._n = 0

    def snapshot(self):
        return {"running": True, "login_phase": self.login_phase}

    def send(self, cmd):
        name = cmd.get("cmd")
        if name == "login_start" and self.fail_start:
            raise RuntimeError("login_start failed")
        self._n += 1
        out = dict(cmd)
        if not out.get("id"):
            out["id"] = "id-%d" % self._n
        self.sent.append(out)
        if name == "login_start":
            if self.hang:
                self.login_phase = "running"
                return {"ok": True, "id": out["id"]}
            phase = self.terminal_phase or "need_login"
            self.login_phase = phase
            self.mod.handle_engine_event(
                {
                    "type": "login",
                    "id": out["id"],
                    "phase": phase,
                    "mode": "silent",
                    "cookieLength": len(self.consume_cookie or ""),
                    "message": "",
                }
            )
            return {"ok": True, "id": out["id"]}
        if name == "login_consume":
            cookie = self.consume_cookie or ""
            self.mod.handle_engine_event(
                {
                    "type": "result",
                    "id": out["id"],
                    "ok": True,
                    "cookie": cookie,
                    "cookieLength": len(cookie),
                    "phase": "idle",
                    "error": "",
                }
            )
            return {"ok": True, "id": out["id"]}
        if name == "login_cancel":
            self.login_phase = "cancelled"
            self.mod.handle_engine_event(
                {
                    "type": "login",
                    "id": out["id"],
                    "phase": "cancelled",
                    "mode": "silent",
                    "cookieLength": 0,
                    "message": "",
                }
            )
            return {"ok": True, "id": out["id"]}
        return {"ok": True, "id": out["id"]}


class CookieRefreshStartupTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_main_module()

    def _run(self, engine, cfg):
        supervisor = LiveSupervisor(
            interval_seconds=cfg.live_probe_interval_seconds,
            auto_refresh=cfg.cookie_auto_refresh,
            now=lambda: 0.0,
        )
        with mock.patch.object(self.mod.config, "get_config", return_value=cfg), mock.patch.object(
            self.mod.config, "write_douyin_cookie_atomic", return_value=True
        ) as write_mock:
            asyncio.run(self.mod.bootstrap_live(engine, supervisor))
        return supervisor, write_mock

    def test_auto_refresh_starts_silent_even_without_cookie(self):
        engine = _ScriptEngine(self.mod, terminal_phase="need_login")
        _supervisor, write_mock = self._run(engine, _cfg(cookie_auto_refresh=True, douyin_cookie="", douyin_room_id="9527"))
        self.assertEqual(engine.sent[0]["cmd"], "login_start")
        self.assertEqual(engine.sent[0]["mode"], "silent")
        write_mock.assert_not_called()

    def test_silent_done_writes_long_cookie_then_probes(self):
        cookie = "sessionid=abc;" + ("x" * 200)
        engine = _ScriptEngine(self.mod, terminal_phase="done", consume_cookie=cookie)
        _supervisor, write_mock = self._run(engine, _cfg(douyin_cookie="", douyin_room_id="9527"))
        write_mock.assert_called_once()
        self.assertGreaterEqual(len(write_mock.call_args[0][0]), 200)
        self.assertEqual([item["cmd"] for item in engine.sent], ["login_start", "login_consume", "probe_live"])
        self.assertEqual(engine.sent[-1]["roomNum"], "9527")
        self.assertNotIn(cookie, json.dumps(engine.sent))

    def test_silent_need_login_with_disk_cookie_probes_without_write(self):
        disk = "d" * 200
        engine = _ScriptEngine(self.mod, terminal_phase="need_login")
        _supervisor, write_mock = self._run(engine, _cfg(douyin_cookie=disk, douyin_room_id="9527"))
        write_mock.assert_not_called()
        self.assertEqual([item["cmd"] for item in engine.sent], ["login_start", "probe_live"])
        self.assertNotIn("connect", [item["cmd"] for item in engine.sent])

    def test_empty_room_can_silent_but_does_not_probe_or_connect(self):
        engine = _ScriptEngine(self.mod, terminal_phase="need_login")
        _supervisor, write_mock = self._run(
            engine,
            _cfg(cookie_auto_refresh=True, douyin_room_id="", douyin_cookie="e" * 200),
        )
        cmds = [item["cmd"] for item in engine.sent]
        self.assertEqual(engine.sent[0]["cmd"], "login_start")
        self.assertEqual(engine.sent[0]["mode"], "silent")
        self.assertNotIn("probe_live", cmds)
        self.assertNotIn("connect", cmds)
        write_mock.assert_not_called()

    def test_auto_refresh_off_with_cookie_probes_without_login(self):
        engine = _ScriptEngine(self.mod)
        _supervisor, _write_mock = self._run(
            engine,
            _cfg(cookie_auto_refresh=False, douyin_cookie="c" * 200, douyin_room_id="9527"),
        )
        self.assertEqual([item["cmd"] for item in engine.sent], ["probe_live"])

    def test_login_start_error_falls_back_to_probe_with_disk_cookie(self):
        engine = _ScriptEngine(self.mod, fail_start=True)
        _supervisor, write_mock = self._run(engine, _cfg(douyin_cookie="f" * 200, douyin_room_id="9527"))
        write_mock.assert_not_called()
        self.assertEqual([item["cmd"] for item in engine.sent], ["probe_live"])
        self.assertNotIn("connect", [item["cmd"] for item in engine.sent])

    def test_short_cookie_is_not_written(self):
        engine = _ScriptEngine(self.mod, terminal_phase="done", consume_cookie="short")
        _supervisor, write_mock = self._run(engine, _cfg(douyin_cookie="old_cookie=1", douyin_room_id="9527"))
        write_mock.assert_not_called()
        self.assertIn("login_consume", [item["cmd"] for item in engine.sent])

    def test_silent_timeout_cancels_then_hands_cancelled_to_supervisor(self):
        engine = _ScriptEngine(self.mod, hang=True)
        cfg = _cfg(cookie_silent_timeout_seconds=0, douyin_cookie="z" * 200, douyin_room_id="9527")
        supervisor = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        seen = []
        original = supervisor.on_login

        def _on_login(phase, cookie=""):
            seen.append(phase)
            return original(phase, cookie)

        supervisor.on_login = _on_login
        with mock.patch.object(self.mod.config, "get_config", return_value=cfg), mock.patch.object(
            self.mod.config, "write_douyin_cookie_atomic", return_value=True
        ) as write_mock:
            asyncio.run(self.mod.bootstrap_live(engine, supervisor))
        self.assertEqual([item["cmd"] for item in engine.sent], ["login_start", "login_cancel", "probe_live"])
        self.assertEqual(seen, ["cancelled"])
        self.assertNotIn("connect", [item["cmd"] for item in engine.sent])
        write_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
