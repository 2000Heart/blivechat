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
    spec = importlib.util.spec_from_file_location('mapper_under_test', mapper_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _gift_msg(*, count='1', repeat_end=None, name='冰爽西瓜', gift_id='1', price=1):
    gift = {
        'id': gift_id,
        'name': name,
        'count': count,
        'price': price,
        'icon': 'https://example.com/gift.png',
    }
    if repeat_end is not None:
        gift['repeatEnd'] = repeat_end
    return {
        'method': 'WebcastGiftMessage',
        'id': f'msg-{count}-{repeat_end}',
        'user': {
            'id': 'u1',
            'name': '测试用户',
            'avatar': 'https://example.com/a.png',
        },
        'gift': gift,
        'roomId': 'room1',
        'roomNum': '123',
        'timestamp': 1700000000000,
    }


class GiftRepeatEndTest(unittest.TestCase):
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

    def test_skips_combo_in_progress_without_repeat_end(self):
        mapped = self._map(_gift_msg(count='1', repeat_end=None))
        self.assertIsNone(mapped)

    def test_skips_combo_in_progress_with_repeat_end_zero(self):
        mapped = self._map(_gift_msg(count='2', repeat_end=0))
        self.assertIsNone(mapped)

    def test_keeps_combo_finished_with_final_count(self):
        mapped = self._map(_gift_msg(count='3', repeat_end=1))
        self.assertIsNotNone(mapped)
        self.assertEqual(mapped['kind'], 'gift')
        self.assertEqual(mapped['gift_name'], '冰爽西瓜')
        self.assertEqual(mapped['num'], 3)

    def test_single_gift_process_then_end_only_end_emitted(self):
        """复现：送 1 个先推过程帧再推结束帧，只应注入结束帧一次。"""
        process = self._map(_gift_msg(count='1', repeat_end=None))
        ended = self._map(_gift_msg(count='1', repeat_end=1))
        self.assertIsNone(process)
        self.assertIsNotNone(ended)
        self.assertEqual(ended['num'], 1)


if __name__ == '__main__':
    unittest.main()
