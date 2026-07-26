import importlib.util
import pathlib
import sys
import unittest


def _load_mapper():
    root = pathlib.Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    contract_path = root / 'contract.py'
    if 'contract' not in sys.modules and contract_path.exists():
        spec = importlib.util.spec_from_file_location('contract', contract_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        sys.modules['contract'] = mod
    mapper_path = root / 'mapper.py'
    spec = importlib.util.spec_from_file_location('mapper_star_guard_test', mapper_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _chat_msg(*, membership_type=None, membership_name=None, on_user=True):
    user = {
        'id': 'u-star',
        'name': '星守护用户',
        'avatar': 'https://example.com/a.png',
        'medalLevel': 12,
        'medalName': '粉丝团名',
    }
    msg = {
        'method': 'WebcastChatMessage',
        'id': 'c1',
        'content': '排队',
        'user': user,
        'roomId': 'room1',
        'roomNum': '440818705456',
        'timestamp': 1700000000000,
    }
    if membership_type is not None or membership_name is not None:
        target = user if on_user else msg
        if membership_type is not None:
            target['membershipType'] = membership_type
        if membership_name is not None:
            target['membershipName'] = membership_name
    return msg


class StarGuardMappingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapper = _load_mapper()

    def _map(self, msg):
        return self.mapper.map_dy_payload(
            msg,
            content_prefix='',
            include_gift=True,
            native_gift=True,
            include_like=False,
            include_member=False,
            include_social=False,
        )

    def test_star_guard_sets_guard_level_captain(self):
        mapped = self._map(_chat_msg(membership_type='star_guard', membership_name='星守护'))
        self.assertIsNotNone(mapped)
        self.assertEqual(mapped['kind'], 'text')
        self.assertEqual(mapped['guard_level'], 3)
        meta = mapped['identity_ext']['platform_meta']
        self.assertEqual(meta['membership_type'], 'star_guard')
        self.assertEqual(meta['membership_name'], '星守护')

    def test_no_membership_guard_level_zero(self):
        mapped = self._map(_chat_msg())
        self.assertEqual(mapped['guard_level'], 0)

    def test_fans_club_only_not_priority(self):
        mapped = self._map(_chat_msg())
        self.assertEqual(mapped['guard_level'], 0)
        self.assertEqual(mapped['medal_level'], 12)

    def test_generic_member_not_priority(self):
        mapped = self._map(_chat_msg(membership_type='member', membership_name='会员'))
        self.assertEqual(mapped['guard_level'], 0)

    def test_membership_name_星守护_alone(self):
        mapped = self._map(_chat_msg(membership_name='星守护'))
        self.assertEqual(mapped['guard_level'], 3)


if __name__ == '__main__':
    unittest.main()
