import os
import shutil
import tempfile
import unittest
from unittest import mock

import config as plugin_config


class CookieConfigLoadTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_temp_ini(self, content: str) -> str:
        path = os.path.join(self._tmpdir, 'config.ini')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_new_admin_keys_load_while_legacy_keys_remain(self):
        path = self._write_temp_ini(
            '[relay]\nmode = direct\nrelay_backend = legacy\nlisten_port = 1\n'
            'admin_port = 18771\nlive_probe_interval_seconds = 180\n'
        )
        cfg = plugin_config.AppConfig()
        self.assertTrue(cfg.load(path))
        self.assertEqual(cfg.relay_backend, 'legacy')
        self.assertEqual(cfg.listen_port, 1)
        self.assertEqual(cfg.admin_port, 18771)
        self.assertEqual(cfg.live_probe_interval_seconds, 180)
        self.assertEqual(cfg.admin_host, '127.0.0.1')


class WriteDouyinCookieTests(unittest.TestCase):
    def test_atomic_write_replaces_only_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'config.ini')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('[relay]\ndouyin_room_id = 9527\ndouyin_cookie = old\n')
            ok = plugin_config.write_douyin_cookie_atomic(
                'sessionid=abc; ttwid=' + ('x' * 220),
                path=path,
            )
            self.assertTrue(ok)
            with open(path, encoding='utf-8') as f:
                text = f.read()
            self.assertIn('douyin_room_id = 9527', text)
            self.assertIn('sessionid=abc', text)
            self.assertNotIn('douyin_cookie = old', text)

    def test_default_path_bootstraps_ini_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'config.ini')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(
                    '[relay]\n'
                    'relay_backend = sidecar\n'
                    'douyin_room_id = 9527\n'
                    'douyin_cookie = old\n'
                )
            with mock.patch.object(
                plugin_config, 'ensure_config_ini_exists', return_value=path
            ) as ensure_mock, mock.patch.object(
                plugin_config, '_preferred_config_path', return_value=path
            ), mock.patch.object(plugin_config, 'reload', return_value=True) as reload_mock:
                ok = plugin_config.write_douyin_cookie_atomic(
                    'sessionid=abc; ttwid=' + ('x' * 220),
                )
            self.assertTrue(ok)
            ensure_mock.assert_called_once()
            reload_mock.assert_called_once()
            with open(path, encoding='utf-8') as f:
                text = f.read()
            self.assertIn('relay_backend = sidecar', text)
            self.assertIn('douyin_room_id = 9527', text)
            self.assertIn('sessionid=abc', text)


if __name__ == '__main__':
    unittest.main()
