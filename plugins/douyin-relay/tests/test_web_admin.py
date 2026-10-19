import asyncio
import json
import pathlib
import unittest

from aiohttp.test_utils import TestClient, TestServer

from web_admin import build_app, open_admin_browser, start_admin


class WebAdminTest(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_contains_cookie_and_sse_does_not(self):
        seen = []
        app = build_app(
            status_provider=lambda: {
                "running": True,
                "phase": "waiting_live",
                "sent": 1,
                "dropped": 0,
                "queue_size": 0,
                "login_phase": "idle",
                "cookie": "sessionid=secret",
                "logs": ["ready"],
                "messages": [{"time": 1, "author_name": "a", "kind": "text", "text": "hi"}],
            },
            action_handler=lambda action, payload: seen.append((action, payload)) or {"ok": True},
        )
        async with TestClient(TestServer(app)) as client:
            snapshot = await client.get("/admin/snapshot")
            body = await snapshot.json()
            self.assertEqual(body["cookie"], "sessionid=secret")
            self.assertEqual(body["messages"][0]["text"], "hi")
            self.assertEqual(body["sent"], 1)
            ws = await client.get("/admin/events")
            chunk = await ws.content.read(400)
            self.assertNotIn(b"sessionid=secret", chunk)
            posted = await client.post("/admin/action", json={"action": "login_start"})
            self.assertEqual(posted.status, 200)
            self.assertEqual(seen, [("login_start", {})])
            await client.post("/admin/action", json={"action": "login_cancel"})
            self.assertEqual(seen[-1][0], "login_cancel")

    def test_non_loopback_host_is_refused(self):
        result = asyncio.run(start_admin("0.0.0.0", 18771, status_provider=lambda: {}, action_handler=lambda a, p: {}))
        self.assertIsNone(result)

    def test_save_filters_does_not_change_room(self):
        seen = []
        app = build_app(
            status_provider=lambda: {"running": True, "cookie": "", "logs": [], "messages": [], "room_id": "1"},
            action_handler=lambda action, payload: seen.append((action, payload)) or {"ok": True, "room_changed": payload.get("room_changed", False)},
        )

        async def run():
            async with TestClient(TestServer(app)) as client:
                await client.post("/admin/action", json={"action": "save_config", "room_id": "1", "include_like": False})
                await client.post("/admin/action", json={"action": "save_config", "room_id": "2"})

        asyncio.run(run())
        self.assertFalse(seen[0][1]["room_changed"])
        self.assertTrue(seen[1][1]["room_changed"])

    def test_second_open_uses_existing_server(self):
        opened = []
        open_admin_browser(already_running=True, port=18771, opener=opened.append)
        self.assertEqual(opened, ["http://127.0.0.1:18771/admin"])

    def test_engine_not_ready(self):
        app = build_app(
            status_provider=lambda: {"running": False, "cookie": "sessionid=secret", "logs": [], "messages": []},
            action_handler=lambda action, payload: {"ok": False, "error": "engine_not_ready"},
        )

        async def run():
            async with TestClient(TestServer(app)) as client:
                resp = await client.post("/admin/action", json={"action": "connect"})
                body = await resp.json()
                self.assertEqual(body["error"], "engine_not_ready")
                self.assertNotIn("sessionid=secret", json.dumps(body))

        asyncio.run(run())


class PluginSurfaceTest(unittest.TestCase):
    def test_plugin_package_has_no_relay_or_bookmark(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
        self.assertNotIn("relay_server", text)
        self.assertNotIn("bookmarklet", text)
        self.assertNotIn("admin_ui", text)
        self.assertTrue((root / "web" / "admin.html").is_file())
