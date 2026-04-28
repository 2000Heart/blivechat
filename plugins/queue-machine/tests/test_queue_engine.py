from queue_engine import QueueConfig, QueueEngine


def _join(engine: QueueEngine, uid: str, medal: int = 10):
    assert engine.join_queue(uid=uid, name=uid, avatar_url="", medal_level=medal)


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
