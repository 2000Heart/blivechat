import asyncio
import importlib.util
import json
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
        "douyin_relay_main_runtime",
        plugin_dir / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _StoppedEngine:
    def __init__(self):
        self.sent = []

    def snapshot(self):
        return {"running": False, "login_phase": "", "logs": []}

    def send(self, cmd):
        self.sent.append(cmd)
        return {"ok": True, "id": "x"}


class RuntimeConfigApplyTests(unittest.TestCase):
    def test_redact_secrets_strips_raw_headers_and_cookie_keys(self):
        mod = _load_main_module()
        out = mod.redact_secrets(
            {
                "ok": True,
                "rawHeaders": "secret=1",
                "connect_ret": {"ok": True, "cookie": "abc", "phase": "done"},
                "nested": {"douyin_cookie": "old", "room": "9527"},
            }
        )
        self.assertEqual(
            out,
            {
                "ok": True,
                "connect_ret": {"ok": True, "phase": "done"},
                "nested": {"room": "9527"},
            },
        )

    def test_engine_not_ready_omits_cookie_and_does_not_send(self):
        mod = _load_main_module()
        engine = _StoppedEngine()
        mod._engine = engine
        mod.config.get_config = lambda: types.SimpleNamespace(douyin_cookie="sessionid=secret" + ("x" * 200))
        ret = mod.handle_admin_action("connect", {"cookie": "sessionid=secret", "rawHeaders": "sessionid=secret"})
        self.assertEqual(ret, {"ok": False, "error": "engine_not_ready"})
        self.assertEqual(engine.sent, [])
        self.assertNotIn("sessionid", json.dumps(ret))
        self.assertNotIn("secret", json.dumps(ret))

    def test_missing_engine_is_not_ready(self):
        mod = _load_main_module()
        mod._engine = None
        ret = mod.handle_admin_action("login_start", {"cookie": "sessionid=secret"})
        self.assertEqual(ret, {"ok": False, "error": "engine_not_ready"})
        self.assertNotIn("sessionid", json.dumps(ret))

    def test_probe_status_and_login_hit_supervisor_once(self):
        mod = _load_main_module()
        supervisor = mock.Mock()
        supervisor.on_probe.return_value = []
        supervisor.on_cast_status.return_value = []
        supervisor.on_login.return_value = []
        mod._supervisor = supervisor
        mod._engine = _StoppedEngine()
        mod._engine.snapshot = lambda: {"running": True, "login_phase": "", "logs": []}
        mod._login_settled = False
        mod._consume_id = None
        mod.config.get_config = lambda: types.SimpleNamespace(douyin_room_id="1", douyin_cookie="")
        with self.assertLogs("douyin-relay", level="INFO") as captured:
            mod.handle_engine_event({"type": "probe", "id": "p", "ok": False, "living": False, "error": "auth"})
            mod.handle_engine_event({"type": "result", "id": "p", "ok": True, "cookie": "sessionid=secret"})
            mod.handle_engine_event({"type": "status", "id": "c", "state": "closed", "error": "empty_signature"})
            mod.handle_engine_event({"type": "login", "id": "l", "phase": "need_login", "cookieLength": 0})
        self.assertEqual(supervisor.on_probe.call_count, 1)
        self.assertEqual(supervisor.on_cast_status.call_count, 1)
        self.assertEqual(supervisor.on_login.call_count, 1)
        self.assertNotIn("sessionid", "\n".join(captured.output))

    def test_mapped_messages_keep_recent_fields(self):
        mod = _load_main_module()
        mod._dedup = {}

        class _Injector:
            async def enqueue(self, _item):
                return None

            def get_metrics(self):
                return {}

        mod._injector = _Injector()
        mod._recent_messages.clear()
        mod.mapper.map_dy_payload = lambda *_args, **_kwargs: {
            "kind": "gift",
            "author_name": "a",
            "gift_name": "玫瑰",
            "num": 2,
        }
        mod.config.get_config = lambda: types.SimpleNamespace(
            content_prefix="",
            include_gift=True,
            native_gift=True,
            include_like=False,
            include_member=True,
            include_social=True,
            douyin_room_id="1",
            douyin_cookie="",
        )
        asyncio.run(mod._handle_messages([{"method": "WebcastGiftMessage", "id": "g1"}]))
        item = mod._recent_messages[0]
        self.assertEqual(item["author_name"], "a")
        self.assertEqual(item["kind"], "gift")
        self.assertIn("text", item)
        self.assertEqual(item["gift_name"], "玫瑰")
        self.assertEqual(item["num"], 2)
        self.assertIn("time", item)

        def _text(_item, **_kwargs):
            return {"kind": "text", "author_name": "b", "content": "hi"}

        mod.mapper.map_dy_payload = _text
        mod._recent_messages.clear()

        async def _fill():
            for i in range(101):
                await mod._handle_messages([{"method": "WebcastChatMessage", "id": str(i)}])

        asyncio.run(_fill())
        self.assertEqual(len(mod._recent_messages), 100)
        self.assertEqual(mod._recent_messages[-1]["text"], "hi")


if __name__ == "__main__":
    unittest.main()
