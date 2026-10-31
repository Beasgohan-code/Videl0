from videl.utils.raid import clear, normalize, record, status


def test_defaults_are_off_and_limits_are_bounded():
    assert normalize(None)["enabled"] is False
    assert normalize({"enabled": True, "window_seconds": 9999, "join_threshold": 0}) == {
        "enabled": True, "window_seconds": 300, "join_threshold": 2,
        "message_threshold": 20, "duration_minutes": 15,
    }


def test_join_burst_starts_once_and_expires():
    clear(123)
    config = {"enabled": True, "window_seconds": 10, "join_threshold": 3,
              "duration_minutes": 1}
    assert not record(123, "joins", config, now=100)["active"]
    assert not record(123, "joins", config, now=101)["started"]
    assert record(123, "joins", config, now=102)["started"]
    assert record(123, "joins", config, now=103)["started"] is False
    assert status(123, now=150)["active"]
    assert status(123, now=163)["active"] is False


def test_message_burst_and_sliding_window_are_separate_from_joins():
    clear(456)
    config = {"enabled": True, "window_seconds": 5, "message_threshold": 2}
    assert record(456, "messages", config, now=10)["active"] is False
    assert record(456, "messages", config, now=16)["active"] is False
    assert record(456, "joins", config, now=16)["active"] is False
