#!/usr/bin/env python3
#
# Unit tests for aiko_chat's wire protocol POLICY (src/aiko_chat/protocol.py).
#
# What these tests DO cover: the policy aiko_chat owns -- recipient addressing,
# the message schema, the decode fallback ORDERING (framework S-expression ->
# legacy JSON -> bare string), field validation, and rendering.
#
# What they deliberately DON'T cover: the S-expression codec itself
# (aiko_services `generate`/`parse`). That is the framework's code, tested by
# the framework against its own vectors -- re-testing it here would be testing
# someone else's library. We assert that generate_payload PRODUCES an
# S-expression and that the fallback ladder decodes each historical shape; we do
# not re-verify the parser's internals.
#
# Import note: protocol.py is a genuine leaf (imports nothing from the package),
# so it is loaded directly from its file rather than via `from aiko_chat.protocol
# import ...`. The package __init__ eagerly imports chat_server, which imports an
# aiko_services robot *example* that is not part of a stock `aiko_services`
# install -- so a plain package import fails in a clean environment. That is a
# pre-existing packaging issue tracked separately with the maintainers; loading
# the leaf directly keeps these tests honest and independent of it.

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "src" / "aiko_chat" / "protocol.py"
_spec = importlib.util.spec_from_file_location("aiko_chat_protocol_under_test", _MODULE_PATH)
protocol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protocol)


# --------------------------------------------------------------------------- #
# Recipient addressing (pure, no framework)

def test_parse_recipients_splits_and_trims():
    assert protocol.parse_recipients("general, llm ,robot") == ["general", "llm", "robot"]

def test_parse_recipients_drops_empty_segments():
    assert protocol.parse_recipients("general,,robot,") == ["general", "robot"]

def test_parse_recipients_empty_and_none():
    assert protocol.parse_recipients("") == []
    assert protocol.parse_recipients(None) == []

def test_generate_recipients_roundtrips():
    assert protocol.generate_recipients(["general", "llm"]) == "general,llm"
    assert protocol.generate_recipients([]) == ""
    assert protocol.generate_recipients(None) == ""


# --------------------------------------------------------------------------- #
# Payload schema + encoding

def test_generate_payload_emits_sexpression_not_json():
    # Regression guard: the wire format is the framework S-expression, NOT the
    # legacy hand-rolled JSON. If a future change (e.g. a bad rebase) reverts
    # generate_payload to json.dumps, this assertion goes red -- which is exactly
    # the silent revert that motivated these tests.
    wire = protocol.generate_payload("nick", "general", "hello")
    assert wire.startswith("(message"), f"expected an S-expression, got: {wire!r}"
    assert not wire.lstrip().startswith("{"), "wire regressed to JSON"

def test_generate_payload_carries_identity_fields():
    wire = protocol.generate_payload("nick", "general", "hello")
    for token in ("username:", "channel:", "timestamp:", "message:"):
        assert token in wire, f"missing {token} in {wire!r}"


# --------------------------------------------------------------------------- #
# Decode fallback ladder + rendering (the policy this module exists to own)

def test_roundtrip_sexpression_renders_prefixed():
    wire = protocol.generate_payload("nick", "general", "hello")
    assert protocol.format_incoming(wire) == "nick: hello"

def test_legacy_json_payload_still_decodes():
    # THE rebase-regression case: an older publisher on the previous JSON wire
    # format must still render. This is the backward-compat rung of the ladder.
    legacy = '{"username": "deanna", "channel": "general", "message": "yo"}'
    assert protocol.format_incoming(legacy) == "deanna: yo"

def test_bare_string_passes_through_unchanged():
    assert protocol.format_incoming("just some text") == "just some text"

def test_malformed_sexpression_falls_through_not_empty_prefix():
    # (message username: nick) has no `message` field. It must NOT render as an
    # empty "nick: " -- it should fail the schema check and fall through to
    # passthrough. This pins the "require message field" validation.
    malformed = "(message username: nick)"
    assert protocol.format_incoming(malformed) == malformed

def test_prefix_falls_back_to_channel_when_no_username():
    payload = '{"channel": "general", "message": "hi"}'
    assert protocol.format_incoming(payload) == "general: hi"

def test_no_prefix_returns_bare_message():
    payload = '{"message": "hi"}'
    assert protocol.format_incoming(payload) == "hi"


# --------------------------------------------------------------------------- #
# message_record / encode_record — the single record-schema definition

def test_message_record_has_the_four_protocol_fields():
    r = protocol.message_record("nick", "general", "hi")
    assert set(r) == {"username", "channel", "timestamp", "message"}
    assert r["username"] == "nick" and r["channel"] == "general" and r["message"] == "hi"
    assert isinstance(r["timestamp"], float)

def test_message_record_timestamp_is_overridable():
    r = protocol.message_record("nick", "general", "hi", timestamp=123.5)
    assert r["timestamp"] == 123.5

def test_generate_payload_equals_encode_of_message_record():
    # generate_payload is just encode_record(message_record(...)) -- pin that
    # they agree, so storing the record and publishing the payload can't drift.
    r = protocol.message_record("nick", "general", "hi", timestamp=42.0)
    assert protocol.encode_record(r) == protocol.encode_record(
        protocol.message_record("nick", "general", "hi", timestamp=42.0))

def test_stored_record_roundtrips_through_the_wire():
    # A record stored in history, once encoded, decodes back to the same fields.
    r = protocol.message_record("nick", "general", "hello", timestamp=42.0)
    assert protocol.format_incoming(protocol.encode_record(r)) == "nick: hello"
