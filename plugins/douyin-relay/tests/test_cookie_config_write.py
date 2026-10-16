import os
import tempfile
import unittest

import config as plugin_config


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
            text = open(path, encoding='utf-8').read()
            self.assertIn('douyin_room_id = 9527', text)
            self.assertIn('sessionid=abc', text)
            self.assertNotIn('douyin_cookie = old', text)


if __name__ == '__main__':
    unittest.main()
