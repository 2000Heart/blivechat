import importlib.util
import pathlib
import sys
import types
import unittest


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
        "douyin_relay_main",
        plugin_dir / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeBridgeClient:
    def __init__(self):
        self.calls = []

    def disconnect(self):
        self.calls.append(("disconnect",))
        return {"ok": True}

    def connect(self, room_num, relay_ws_url, raw_headers=""):
        self.calls.append(("connect", room_num, relay_ws_url, raw_headers))
        return {"ok": True}


class _FakeSidecar:
    def __init__(self, client):
        self._client = client

    def bridge_client(self):
        return self._client


class RuntimeConfigApplyTests(unittest.TestCase):
    def test_apply_config_should_reconnect_with_latest_cookie_and_room(self):
        mod = _load_main_module()
        client = _FakeBridgeClient()
        mod._sidecar = _FakeSidecar(client)
        mod.config.get_config = lambda: types.SimpleNamespace(
            relay_backend="sidecar",
            douyin_room_id="9527",
            douyin_cookie="cookie=v2",
        )
        mod.config.get_dycast_relay_ws_url = lambda: "ws://127.0.0.1:18765/"

        ret = mod.handle_admin_action("sidecar", {"op": "apply_config"})

        self.assertTrue(ret.get("ok"))
        self.assertEqual(
            client.calls,
            [
                ("disconnect",),
                ("connect", "9527", "ws://127.0.0.1:18765/", "cookie=v2"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
