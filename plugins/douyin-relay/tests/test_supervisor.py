import unittest
from supervisor import LiveSupervisor

class SupervisorTest(unittest.TestCase):
    def test_offline_probe_waits_180_seconds(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        self.assertEqual(sup.start(room_id='1', has_cookie=True), [{'cmd': 'probe_live', 'roomNum': '1'}])
        self.assertEqual(sup.on_probe(ok=True, living=False, error=''), [])
        self.assertEqual(sup.phase, 'waiting_live')
        now[0] = 179
        self.assertEqual(sup.tick(), [])
        now[0] = 180
        self.assertEqual(sup.tick(), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_auto_refresh_without_cookie_still_starts_silent(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        self.assertEqual(sup.start(room_id='1', has_cookie=False), [{'cmd': 'login_start', 'mode': 'silent'}])

    def test_living_probe_connects_once(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        self.assertEqual(sup.on_probe(ok=True, living=True, error=''), [{'cmd': 'connect', 'roomNum': '1'}])

    def test_unknown_probe_does_not_connect(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        self.assertEqual(sup.on_probe(ok=False, living=False, error='probe_fail'), [])
        self.assertEqual(sup.phase, 'waiting_live')

    def test_probe_auth_silents_once_and_login_then_probes(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        self.assertEqual(sup.start(room_id='1', has_cookie=True)[0]['cmd'], 'login_start')
        self.assertEqual(sup.on_login(phase='done', cookie='x' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_probe(ok=False, living=False, error='auth'), [{'cmd': 'login_start', 'mode': 'silent'}])
        self.assertNotEqual(sup.phase, 'connected')
        self.assertEqual(sup.on_login(phase='done', cookie='z' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_auth_failure_silent_once_then_need_login(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_login(phase='done', cookie='x' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [{'cmd': 'login_start', 'mode': 'silent'}])
        self.assertEqual(sup.on_login(phase='need_login', cookie=''), [])
        self.assertEqual(sup.phase, 'need_login')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [])

    def test_connected_resets_silent_budget(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_login(phase='done', cookie='x' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        sup.on_cast_status(state='auth_failed')
        sup.on_login(phase='need_login', cookie='')
        sup.on_login(phase='done', cookie='y' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [{'cmd': 'login_start', 'mode': 'silent'}])

    def test_auto_refresh_off_auth_does_not_silent(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [])
        self.assertEqual(sup.phase, 'need_login')

    def test_login_while_waiting_only_probes(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=False)
        self.assertEqual(sup.phase, 'need_login')
        self.assertEqual(sup.on_login(phase='done', cookie='y' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_disconnect_ignores_inflight_probe_connect_and_auth(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        self.assertEqual(sup.user_disconnect(), [{'cmd': 'disconnect'}])
        self.assertEqual(sup.on_probe(ok=True, living=True, error=''), [])
        self.assertNotEqual(sup.phase, 'connecting')
        self.assertEqual(sup.on_probe(ok=False, living=False, error='auth'), [])

        silent = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        silent.start(room_id='1', has_cookie=True)
        silent.on_login(phase='done', cookie='x' * 200)
        silent.user_disconnect()
        self.assertEqual(silent.on_probe(ok=False, living=False, error='auth'), [])
        self.assertEqual(silent.on_cast_status(state='auth_failed'), [])
        self.assertEqual(silent.on_cast_status(state='closed'), [])

    def test_tick_emits_due_connect_without_scheduling_next(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='closed'), [])
        now[0] = 2
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
        self.assertEqual(sup.tick(), [])
        now[0] = 7
        self.assertEqual(sup.tick(), [])
        self.assertEqual(sup.on_cast_status(state='closed'), [])
        now[0] = 11
        self.assertEqual(sup.tick(), [])
        now[0] = 12
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])

    def test_user_disconnect_stops_probe_until_connect(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=False, error='')
        self.assertEqual(sup.user_disconnect(), [{'cmd': 'disconnect'}])
        now[0] = 500
        self.assertEqual(sup.tick(), [])
        cmds = sup.user_connect()
        self.assertEqual([item['cmd'] for item in cmds], ['disconnect', 'probe_live'])

    def test_live_end_probes_later_and_abnormal_close_backs_off(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='live_end'), [])
        self.assertEqual(sup.phase, 'waiting_live')
        now[0] = 180
        self.assertEqual(sup.tick(), [{'cmd': 'probe_live', 'roomNum': '1'}])
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='closed', error='im_fetch_failed'), [])
        now[0] = 182
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='closed', error='empty_signature'), [])
        now[0] = 184
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
