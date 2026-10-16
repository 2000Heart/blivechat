import json
import signal
import subprocess
import types
import unittest
from unittest import mock

from engine_process import EngineProcess


class _Stdin:
    def __init__(self):
        self.chunks = []

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.chunks.append(data)

    def flush(self):
        return None


class _AliveProc:
    def __init__(self, stdin):
        self.stdin = stdin
        self.pid = 77
        self._poll = None

    def poll(self):
        return self._poll

    def wait(self, timeout=None):
        self._poll = 0
        return 0

    def kill(self):
        self._poll = -9

    def terminate(self):
        self._poll = -15


class _WaitProc:
    def __init__(self):
        self.pid = 77
        self.stdin = _Stdin()
        self.waits = []
        self.killed = False
        self._poll = None

    def poll(self):
        return self._poll

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if len(self.waits) == 1:
            raise subprocess.TimeoutExpired(cmd="node", timeout=timeout)
        self._poll = -9
        return -9

    def kill(self):
        self.killed = True

    def terminate(self):
        return None


class EngineProcessTests(unittest.TestCase):
    def test_stdout_events_dispatch_once(self):
        events = []
        delivered = []
        proc = EngineProcess(on_messages=delivered.append, on_event=events.append, node_exe="node", dycast_path=".")
        proc.feed_stdout('{"type":"messages","payload":[{"method":"WebcastChatMessage"}]}\n')
        proc.feed_stdout("not-json\n")
        proc.feed_stderr("stack\n")
        proc.feed_stdout('{"type":"probe","id":"p","ok":false,"living":false,"roomStatus":"unknown","error":"auth"}\n')
        proc.feed_stdout('{"type":"status","id":"c","state":"closed","error":"empty_signature"}\n')
        self.assertEqual(delivered, [[{"method": "WebcastChatMessage"}]])
        self.assertEqual([item["type"] for item in events], ["probe", "status"])
        self.assertIn("not-json", proc.log_lines)
        self.assertIn("stack", proc.log_lines)
        self.assertNotIn("sessionid", "".join(proc.log_lines))

    def test_command_argv_runs_tsx_headless(self):
        proc = EngineProcess(
            on_messages=None,
            on_event=None,
            node_exe="/usr/bin/node",
            dycast_path="/dycast",
            env={
                "DYCAST_LOGIN_PROFILE_DIR": "/tmp/profile",
                "DYCAST_LOGIN_TIMEOUT_SECONDS": "300",
                "DYCAST_SILENT_TIMEOUT_SECONDS": "30",
            },
        )
        self.assertEqual(
            proc.command_argv(),
            [
                "/usr/bin/node",
                "./node_modules/tsx/dist/cli.mjs",
                "--tsconfig",
                "tsconfig.sidecar.json",
                "src/sidecar/headless.ts",
            ],
        )
        env = proc.subprocess_env()
        self.assertEqual(env["DYCAST_LOGIN_PROFILE_DIR"], "/tmp/profile")
        self.assertEqual(env["DYCAST_LOGIN_TIMEOUT_SECONDS"], "300")
        self.assertEqual(env["DYCAST_SILENT_TIMEOUT_SECONDS"], "30")

    def test_send_adds_raw_headers_without_logging_cookie(self):
        import config

        cookie = "sessionid=secretvalue"
        old = config._config
        config._config = types.SimpleNamespace(douyin_cookie=cookie)
        stdin = _Stdin()
        proc = EngineProcess(on_messages=None, on_event=None, node_exe="node", dycast_path=".")
        proc._proc = _AliveProc(stdin)
        proc._running = True
        try:
            with self.assertLogs("douyin-relay.engine_process", level="INFO") as captured:
                ret = proc.send({"cmd": "probe_live", "roomNum": "1"})
            body = json.loads(stdin.chunks[0].decode())
            self.assertTrue(ret.get("ok"))
            self.assertTrue(body.get("id"))
            self.assertEqual(body["rawHeaders"], cookie)
            self.assertEqual(body["cmd"], "probe_live")
            logged = "\n".join(captured.output)
            self.assertIn("cookieLength", logged)
            self.assertNotIn("sessionid", logged)
            self.assertNotIn("secretvalue", logged)
            self.assertNotIn("sessionid", json.dumps(proc.snapshot()))
            self.assertNotIn("cookie", proc.snapshot())
            self.assertNotIn("rawHeaders", proc.snapshot())
        finally:
            config._config = old

    def test_send_when_stopped_does_not_write_stdin(self):
        proc = EngineProcess(on_messages=None, on_event=None, node_exe="node", dycast_path=".")
        stdin = _Stdin()
        proc._proc = _AliveProc(stdin)
        proc._running = False
        ret = proc.send({"cmd": "disconnect"})
        self.assertEqual(ret, {"ok": False, "error": "engine_not_ready"})
        self.assertEqual(stdin.chunks, [])

    def test_result_cookie_stays_out_of_logs_and_snapshot(self):
        proc = EngineProcess(on_messages=lambda _payload: None, on_event=lambda _event: None, node_exe="node", dycast_path=".")
        proc.feed_stdout('{"type":"result","id":"1","ok":true,"cookie":"sessionid=secret"}\n')
        self.assertNotIn("sessionid", "".join(proc.log_lines))
        self.assertNotIn("sessionid", json.dumps(proc.snapshot()))
        self.assertNotIn("cookie", proc.snapshot())
        self.assertFalse(proc.snapshot()["running"])

    def test_exited_process_snapshot_is_not_running(self):
        proc = EngineProcess(on_messages=None, on_event=None, node_exe="node", dycast_path=".")

        class _Dead:
            pid = 9

            def poll(self):
                return 1

        proc._proc = _Dead()
        proc._running = True
        self.assertFalse(proc.snapshot()["running"])

    def test_stop_sigterm_process_group_then_sigkill(self):
        proc = EngineProcess(on_messages=None, on_event=None, node_exe="node", dycast_path=".")
        fake = _WaitProc()
        proc._proc = fake
        proc._running = True
        with mock.patch("engine_process.os.name", "posix"), mock.patch(
            "engine_process.os.getpgid", return_value=77
        ), mock.patch("engine_process.os.killpg") as killpg:
            proc.stop()
        self.assertEqual(fake.waits, [8, 8])
        self.assertEqual(killpg.call_args_list[0], mock.call(77, signal.SIGTERM))
        self.assertEqual(killpg.call_args_list[1], mock.call(77, signal.SIGKILL))
        self.assertFalse(fake.killed)

    def test_stop_uses_taskkill_on_windows(self):
        proc = EngineProcess(on_messages=None, on_event=None, node_exe="node", dycast_path=".")
        fake = _AliveProc(_Stdin())
        proc._proc = fake
        proc._running = True
        with mock.patch("engine_process.os.name", "nt"), mock.patch("engine_process.subprocess.run") as run:
            proc.stop()
        self.assertEqual(run.call_args.args[0], ["taskkill", "/F", "/T", "/PID", "77"])


if __name__ == "__main__":
    unittest.main()
