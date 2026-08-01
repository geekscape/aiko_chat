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
