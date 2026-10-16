import asyncio
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


def _load_main_module():
    fake_blcsdk = types.SimpleNamespace(
        init=lambda: None,
        is_sdk_version_compatible=lambda: True,
        log=lambda *_args, **_kwargs: None,
        shut_down=lambda: None,
    )
    sys.modules["blcsdk"] = fake_blcsdk
    fake_cachetools = types.SimpleNamespace(TTLCache=dict)
    sys.modules["cachetools"] = fake_cachetools
    sys.modules["listener"] = types.SimpleNamespace(init=lambda: None, shut_down=lambda: None)
    sys.modules["mapper"] = types.SimpleNamespace(
        GIFT="gift",
        map_dy_payload=lambda *_args, **_kwargs: None,
    )
    sys.modules["admin_ui"] = types.SimpleNamespace(
        notify_status_changed=lambda: None,
        bind_plugin_event_loop=lambda _loop: None,
        set_status_provider=lambda _provider: None,
        set_action_handler=lambda _handler: None,
        run_on_plugin_loop=lambda fn: fn(),
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

    class _ProtocolStub:
        def parse_raw_payload(self, _raw):
            return "unknown", None

    class _RelayStub:
        def __init__(self, *_args, **_kwargs):
            pass

        async def start(self):
            return None

        async def stop(self):
            return None

    class _RuntimeManagerStub:
        def __init__(self, *_args, **_kwargs):
            pass

    class _RuntimeConfigStub:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    sys.modules["injector"] = types.SimpleNamespace(Injector=_InjectorStub)
    sys.modules["douyin_protocol"] = types.SimpleNamespace(DouyinProtocol=_ProtocolStub)
    sys.modules["relay_server"] = types.SimpleNamespace(DouyinRelayServer=_RelayStub)
    sys.modules["runtime_manager"] = types.SimpleNamespace(
        DycastRuntimeManager=_RuntimeManagerStub,
        SidecarRuntimeConfig=_RuntimeConfigStub,
    )
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


class _FakeBridgeClient:
    def __init__(self, status_payload, cookie="sessionid=abc; ttwid=" + ("x" * 220)):
        self.calls = []
        self._status_payload = status_payload
        self._consume_cookie = cookie

    def login_start(self, mode):
        self.calls.append(("start", mode))
        return {"phase": "running", "mode": mode, "message": ""}

    def login_status(self):
        return dict(self._status_payload)

    def login_consume(self):
        self.calls.append("consume")
        cookie = self._consume_cookie
        return {"ok": True, "cookie": cookie, "cookieLength": len(cookie)}

    def login_cancel(self):
        self.calls.append("cancel")
        return {"ok": True}

    def disconnect(self):
        self.calls.append("disconnect")
        return {"ok": True}

    def connect(self, room_num, relay_ws_url, raw_headers=""):
        self.calls.append(("connect", room_num, relay_ws_url, raw_headers))
        return {"ok": True}


def _cfg(**kwargs):
    values = dict(
        cookie_auto_refresh=True,
        douyin_room_id="9527",
        douyin_cookie="old_cookie=1",
        cookie_silent_timeout_seconds=30,
    )
    values.update(kwargs)
    return types.SimpleNamespace(**values)


class CookieRefreshStartupTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_main_module()
        self.relay_ws = "ws://127.0.0.1:18765/"

    def test_done_status_consumes_writes_then_connects_with_new_cookie(self):
        client = _FakeBridgeClient({"phase": "done", "cookieLength": 300, "mode": "silent", "message": ""})
        cfg = _cfg()

        with mock.patch.object(self.mod.config, "write_douyin_cookie_atomic", return_value=True) as write_mock:
            asyncio.run(self.mod.refresh_cookie_then_connect(client, cfg, self.relay_ws))

        write_mock.assert_called_once()
        written = write_mock.call_args[0][0]
        self.assertTrue(str(written).startswith("sessionid=abc"))
        self.assertEqual(client.calls[0], ("start", "silent"))
        self.assertEqual(client.calls[1], "consume")
        self.assertEqual(client.calls[2], "disconnect")
        self.assertEqual(client.calls[3][0], "connect")
        self.assertEqual(client.calls[3][1], "9527")
        self.assertEqual(client.calls[3][2], self.relay_ws)
        self.assertTrue(str(client.calls[3][3]).startswith("sessionid=abc"))
        self.assertEqual(len(client.calls), 4)

    def test_need_login_skips_consume_and_uses_old_cookie(self):
        client = _FakeBridgeClient({"phase": "need_login", "cookieLength": 0, "mode": "silent", "message": ""})
        cfg = _cfg(douyin_cookie="old_cookie=1")

        with mock.patch.object(self.mod.config, "write_douyin_cookie_atomic", return_value=True) as write_mock:
            asyncio.run(self.mod.refresh_cookie_then_connect(client, cfg, self.relay_ws))

        ops = [c[0] if isinstance(c, tuple) else c for c in client.calls]
        self.assertEqual(ops[0], "start")
        self.assertNotIn("consume", ops)
        write_mock.assert_not_called()
        connect = next(c for c in client.calls if isinstance(c, tuple) and c[0] == "connect")
        self.assertEqual(connect[3], cfg.douyin_cookie)

    def test_empty_room_runs_silent_but_does_not_connect(self):
        client = _FakeBridgeClient({"phase": "need_login", "cookieLength": 0, "mode": "silent", "message": ""})
        cfg = _cfg(douyin_room_id="")

        asyncio.run(self.mod.refresh_cookie_then_connect(client, cfg, self.relay_ws))

        self.assertEqual(client.calls[0], ("start", "silent"))
        ops = [c[0] if isinstance(c, tuple) else c for c in client.calls]
        self.assertNotIn("connect", ops)

    def test_auto_refresh_off_connects_without_login_start(self):
        client = _FakeBridgeClient({"phase": "idle"})
        cfg = _cfg(cookie_auto_refresh=False, douyin_cookie="old_cookie=1")

        asyncio.run(self.mod.refresh_cookie_then_connect(client, cfg, self.relay_ws))

        self.assertNotIn(("start", "silent"), client.calls)
        self.assertEqual(
            client.calls,
            [("connect", "9527", self.relay_ws, "old_cookie=1")],
        )


if __name__ == "__main__":
    unittest.main()
