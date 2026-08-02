#!/usr/bin/env python3
#
# Unit tests for the per-channel recent-message buffer (src/aiko_chat/history.py).
#
# Like test_protocol.py, history.py is a pure leaf (no package imports), so it is
# loaded directly from its file rather than via `from aiko_chat.history import ...`
# -- the package __init__ eagerly imports chat_server, which imports an
# aiko_services robot example absent from a stock install (tracked separately).

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "src" / "aiko_chat" / "history.py"
_spec = importlib.util.spec_from_file_location("aiko_chat_history_under_test", _MODULE_PATH)
history = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(history)


def _rec(msg, channel="general", user="nick", ts=0.0):
    return {"username": user, "channel": channel, "timestamp": ts, "message": msg}


def test_append_then_recent_returns_records_oldest_first():
    h = history.ChannelHistory()
    h.append("general", _rec("first"))
    h.append("general", _rec("second"))
    got = [r["message"] for r in h.recent("general", 10)]
    assert got == ["first", "second"]  # oldest-first for top-to-bottom render


def test_recent_limit_returns_the_newest_n_still_oldest_first():
    h = history.ChannelHistory()
    for i in range(5):
        h.append("general", _rec(f"m{i}"))
    got = [r["message"] for r in h.recent("general", 3)]
    assert got == ["m2", "m3", "m4"]  # newest 3, but ordered oldest->newest


def test_capacity_evicts_oldest():
    h = history.ChannelHistory(capacity=3)
    for i in range(5):
        h.append("general", _rec(f"m{i}"))
    got = [r["message"] for r in h.recent("general", 100)]
    assert got == ["m2", "m3", "m4"]  # m0, m1 evicted


def test_channels_are_isolated():
    h = history.ChannelHistory()
    h.append("general", _rec("g", channel="general"))
    h.append("random", _rec("r", channel="random"))
    assert [r["message"] for r in h.recent("general", 10)] == ["g"]
    assert [r["message"] for r in h.recent("random", 10)] == ["r"]


def test_unknown_channel_returns_empty():
    h = history.ChannelHistory()
    assert h.recent("nope", 10) == []


def test_nonpositive_limit_returns_empty():
    h = history.ChannelHistory()
    h.append("general", _rec("x"))
    assert h.recent("general", 0) == []
    assert h.recent("general", -1) == []


def test_limit_larger_than_history_returns_all():
    h = history.ChannelHistory()
    h.append("general", _rec("only"))
    assert [r["message"] for r in h.recent("general", 50)] == ["only"]


def test_capacity_must_be_positive():
    import pytest
    with pytest.raises(ValueError):
        history.ChannelHistory(capacity=0)


# --------------------------------------------------------------------------- #
# Durable (file-backed) mode

def test_durable_survives_a_restart(tmp_path):
    h1 = history.ChannelHistory(path=str(tmp_path))
    h1.append("general", _rec("persisted"))
    h1.append("general", _rec("also"))
    # A fresh instance on the same dir == a process restart.
    h2 = history.ChannelHistory(path=str(tmp_path))
    assert [r["message"] for r in h2.recent("general", 10)] == ["persisted", "also"]


def test_durable_file_is_capped_on_disk(tmp_path):
    h1 = history.ChannelHistory(capacity=3, path=str(tmp_path))
    for i in range(5):
        h1.append("general", _rec(f"m{i}"))
    h2 = history.ChannelHistory(capacity=3, path=str(tmp_path))
    assert [r["message"] for r in h2.recent("general", 100)] == ["m2", "m3", "m4"]


def test_durable_channels_reload_independently(tmp_path):
    h1 = history.ChannelHistory(path=str(tmp_path))
    h1.append("general", _rec("g", channel="general"))
    h1.append("random", _rec("r", channel="random"))
    h2 = history.ChannelHistory(path=str(tmp_path))
    assert [r["message"] for r in h2.recent("general", 10)] == ["g"]
    assert [r["message"] for r in h2.recent("random", 10)] == ["r"]


def test_durable_handles_filesystem_unsafe_channel_names(tmp_path):
    # A channel name with a slash must not create nested dirs or collide.
    weird = "team/ops #1"
    h1 = history.ChannelHistory(path=str(tmp_path))
    h1.append(weird, _rec("hi", channel=weird))
    h2 = history.ChannelHistory(path=str(tmp_path))
    assert [r["message"] for r in h2.recent(weird, 10)] == ["hi"]


def test_records_roundtrip_through_json_unchanged(tmp_path):
    rec = _rec("hello", channel="general", user="nick", ts=42.5)
    history.ChannelHistory(path=str(tmp_path)).append("general", rec)
    reloaded = history.ChannelHistory(path=str(tmp_path)).recent("general", 1)[0]
    assert reloaded == rec


def test_durable_load_skips_a_corrupt_line_and_keeps_the_rest(tmp_path):
    # A single torn/corrupt JSONL line (e.g. a half-written last append) must not
    # wipe the whole channel on restart -- the surviving records still load.
    h1 = history.ChannelHistory(path=str(tmp_path))
    h1.append("general", _rec("before"))
    h1.append("general", _rec("after"))
    channel_file = h1._channel_file("general")
    with open(channel_file, "a", encoding="utf-8") as f:
        f.write("{ this is not valid json\n")  # torn trailing line
    h2 = history.ChannelHistory(path=str(tmp_path))
    assert [r["message"] for r in h2.recent("general", 10)] == ["before", "after"]


def test_durable_one_corrupt_channel_does_not_block_others(tmp_path):
    # Corrupt data in one channel file must not abort loading a sibling channel.
    h1 = history.ChannelHistory(path=str(tmp_path))
    h1.append("general", _rec("g", channel="general"))
    h1.append("random", _rec("r", channel="random"))
    with open(h1._channel_file("general"), "w", encoding="utf-8") as f:
        f.write("totally broken\n")  # general is now unparseable
    h2 = history.ChannelHistory(path=str(tmp_path))
    assert h2.recent("general", 10) == []            # corrupt channel -> empty
    assert [r["message"] for r in h2.recent("random", 10)] == ["r"]  # sibling intact
