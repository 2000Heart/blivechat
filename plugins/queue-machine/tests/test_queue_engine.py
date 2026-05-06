from queue_engine import QueueConfig, QueueEngine


def _join(engine: QueueEngine, uid: str, medal: int = 10, privilege_type: int = 0):
    assert engine.join_queue(uid=uid, name=uid, avatar_url="", medal_level=medal, privilege_type=privilege_type)


def test_passed_users_always_on_top():
    engine = QueueEngine(QueueConfig())
    _join(engine, "u1")
    _join(engine, "u2")
    engine.add_gift_value_coin("u2", 5000)
    assert [u.uid for u in engine.ordered_users()] == ["u2", "u1"]
    engine.mark_passed("u1")
    assert [u.uid for u in engine.ordered_users()] == ["u1", "u2"]


def test_normal_users_sorted_by_gift_then_time():
    engine = QueueEngine(QueueConfig())
    _join(engine, "u1")
    _join(engine, "u2")
    _join(engine, "u3")
    engine.add_gift_value_coin("u1", 1000)
    engine.add_gift_value_coin("u3", 3000)
    assert [u.uid for u in engine.ordered_users()] == ["u3", "u1", "u2"]


def test_unpass_resets_queue_time():
    engine = QueueEngine(QueueConfig(reset_queue_time_on_unpass=True))
    _join(engine, "u1")
    first = engine._users["u1"].queued_at
    engine.mark_passed("u1")
    engine.unmark_passed("u1")
    assert engine._users["u1"].queued_at >= first


def test_min_medal_level_filter():
    engine = QueueEngine(QueueConfig(min_medal_level=5))
    assert not engine.join_queue(uid="u1", name="u1", avatar_url="", medal_level=4)
    assert engine.join_queue(uid="u1", name="u1", avatar_url="", medal_level=5)


def test_manual_calling_overrides_default_rank():
    engine = QueueEngine(QueueConfig())
    _join(engine, "u1")
    _join(engine, "u2")
    engine.add_gift_value_coin("u2", 1000)
    assert engine.calling_user_id() == "u2"
    engine.mark_called("u1")
    assert engine.calling_user_id() == "u1"


def test_captain_priority_enabled_default_true():
    engine = QueueEngine(QueueConfig())
    assert engine.cfg.captain_priority_enabled is True


def test_passed_users_still_before_captains():
    engine = QueueEngine(QueueConfig(captain_priority_enabled=True))
    _join(engine, "passed_user", privilege_type=0)
    _join(engine, "captain_user", privilege_type=1)
    engine.mark_passed("passed_user")
    assert [u.uid for u in engine.ordered_users()] == ["passed_user", "captain_user"]


def test_captain_group_sorted_by_guard_then_gift_then_time():
    engine = QueueEngine(QueueConfig(captain_priority_enabled=True))
    _join(engine, "captain", privilege_type=3)
    _join(engine, "governor", privilege_type=1)
    _join(engine, "admiral", privilege_type=2)
    engine.add_gift_value_coin("captain", 99999)
    assert [u.uid for u in engine.ordered_users()] == ["governor", "admiral", "captain"]


def test_disable_captain_priority_fallback_to_gift_then_time():
    engine = QueueEngine(QueueConfig(captain_priority_enabled=False))
    _join(engine, "normal", privilege_type=0)
    _join(engine, "governor", privilege_type=1)
    engine.add_gift_value_coin("normal", 2000)
    assert [u.uid for u in engine.ordered_users()] == ["normal", "governor"]


def test_state_backward_compat_without_captain_fields():
    engine = QueueEngine()
    engine.load_state(
        {
            "config": {"min_medal_level": 0},
            "users": [
                {
                    "uid": "u1",
                    "name": "u1",
                    "avatar_url": "",
                    "medal_level": 1,
                    "queued_at": 1,
                }
            ],
        }
    )
    users = engine.ordered_users()
    assert users[0].uid == "u1"
    assert users[0].privilege_type == 0
    assert users[0].is_captain is False
    assert engine.cfg.captain_priority_enabled is True


def test_invalid_privilege_type_fallback_none():
    engine = QueueEngine(QueueConfig())
    _join(engine, "u1", privilege_type=99)
    assert engine._users["u1"].privilege_type == 0
    engine.load_state(
        {
            "config": {"captain_priority_enabled": True},
            "users": [
                {
                    "uid": "u2",
                    "name": "u2",
                    "avatar_url": "",
                    "medal_level": 1,
                    "queued_at": 1,
                    "privilege_type": "bad-value",
                }
            ],
        }
    )
    assert engine._users["u2"].privilege_type == 0
