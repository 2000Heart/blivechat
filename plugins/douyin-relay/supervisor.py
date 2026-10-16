# -*- coding: utf-8 -*-
"""Decide when to probe, connect, or silently refresh a Douyin live room."""
import time

_BACKOFF_SECONDS = (2, 5, 10, 30, 60)
_COOKIE_MIN_LEN = 200
_STARTUP_SILENT_FAILURES = frozenset(('need_login', 'error', 'cancelled'))


def _login_silent():
    return {'cmd': 'login_start', 'mode': 'silent'}


def _disconnect():
    return {'cmd': 'disconnect'}


class LiveSupervisor:
    def __init__(self, interval_seconds=180, auto_refresh=False, now=None):
        self._interval_seconds = interval_seconds
        self._auto_refresh = bool(auto_refresh)
        self._now = time.monotonic if now is None else now
        self._phase = 'idle'
        self._room_id = ''
        self._held = False
        self._due_at = None
        self._due_kind = None
        self._backoff_index = 0
        self._silent_used = False
        self._startup_silent_failed = False
        self._awaiting_startup_login = False
        self._startup_login_epoch = 0
        self._progress_epoch = 0
        self._stale_startup_login_results = 0

    @property
    def phase(self):
        return self._phase

    def start(self, room_id='', has_cookie=False):
        self._phase = 'idle'
        self._room_id = ''
        self._held = False
        self._clear_due()
        self._backoff_index = 0
        self._silent_used = False
        self._startup_silent_failed = False
        if self._awaiting_startup_login:
            self._stale_startup_login_results += 1
        self._awaiting_startup_login = False
        self._startup_login_epoch = 0
        self._progress_epoch = 0
        self._room_id = '' if room_id is None else str(room_id).strip()
        if self._room_id == '':
            self._phase = 'idle'
            return []
        if self._auto_refresh:
            self._startup_login_epoch += 1
            self._awaiting_startup_login = True
            self._phase = 'refreshing'
            return [_login_silent()]
        if not has_cookie:
            self._phase = 'need_login'
            return []
        return [self._probe_cmd()]

    def on_login(self, phase, cookie=''):
        if self._stale_startup_login_results > 0:
            self._stale_startup_login_results -= 1
            return []
        startup = self._awaiting_startup_login
        if startup:
            self._awaiting_startup_login = False
            if phase in _STARTUP_SILENT_FAILURES:
                self._startup_silent_failed = True
            suppress = self._held or self._progress_epoch >= self._startup_login_epoch
            if suppress:
                return []
            if phase == 'done' and isinstance(cookie, str) and len(cookie) >= _COOKIE_MIN_LEN:
                self._clear_due()
                return [self._probe_cmd()]
            self._phase = 'need_login'
            self._clear_due()
            return []
        if self._held:
            return []
        if self._phase == 'connected':
            self._phase = 'refreshing'
        if phase == 'done' and isinstance(cookie, str) and len(cookie) >= _COOKIE_MIN_LEN:
            self._clear_due()
            return [self._probe_cmd()]
        self._phase = 'need_login'
        self._clear_due()
        return []

    def on_probe(self, ok, living, error=''):
        del ok
        if self._held:
            return []
        if error == 'auth':
            return self._begin_auth_recovery()
        if living:
            self._clear_due()
            self._phase = 'connecting'
            return [self._connect_cmd()]
        self._arm_probe()
        return []

    def on_cast_status(self, state, error=''):
        del error
        if state == 'connected':
            if self._held:
                return []
            self._phase = 'connected'
            self._silent_used = False
            self._backoff_index = 0
            self._clear_due()
            return []
        if state == 'live_end':
            if self._held:
                return []
            self._arm_probe()
            return []
        if state == 'closed':
            if self._held:
                return []
            self._schedule_connect('reconnecting')
            self._advance_backoff()
            return []
        if state == 'auth_failed':
            if self._held:
                return []
            return self._begin_auth_recovery()
        return []

    def tick(self):
        if self._held or self._due_at is None or self._now() < self._due_at:
            return []
        kind = self._due_kind
        self._clear_due()
        if kind == 'probe_live':
            return [self._probe_cmd()]
        if kind == 'connect':
            self._phase = 'connecting'
            return [self._connect_cmd()]
        return []

    def user_disconnect(self):
        self._held = True
        self._clear_due()
        self._phase = 'disconnected'
        return [_disconnect()]

    def user_connect(self):
        self._held = False
        self._progress_epoch += 1
        self._clear_due()
        self._backoff_index = 0
        return [_disconnect(), self._probe_cmd()]

    def change_room(self, room_id):
        self._held = False
        self._clear_due()
        self._backoff_index = 0
        self._room_id = '' if room_id is None else str(room_id).strip()
        if self._room_id == '':
            self._phase = 'idle'
            return [_disconnect()]
        return [_disconnect(), self._probe_cmd()]

    def _probe_cmd(self):
        return {'cmd': 'probe_live', 'roomNum': self._room_id}

    def _connect_cmd(self):
        return {'cmd': 'connect', 'roomNum': self._room_id}

    def _clear_due(self):
        self._due_at = None
        self._due_kind = None

    def _arm_probe(self):
        if self._held:
            self._clear_due()
            return
        self._phase = 'waiting_live'
        self._due_at = self._now() + self._interval_seconds
        self._due_kind = 'probe_live'

    def _schedule_connect(self, phase):
        if self._held:
            self._clear_due()
            return
        self._phase = phase
        index = min(self._backoff_index, len(_BACKOFF_SECONDS) - 1)
        self._due_at = self._now() + _BACKOFF_SECONDS[index]
        self._due_kind = 'connect'

    def _advance_backoff(self):
        if self._backoff_index < len(_BACKOFF_SECONDS) - 1:
            self._backoff_index += 1

    def _begin_auth_recovery(self):
        self._clear_due()
        if self._auto_refresh and not self._silent_used and not self._startup_silent_failed:
            self._silent_used = True
            self._phase = 'refreshing'
            return [_login_silent()]
        self._phase = 'need_login'
        return []
