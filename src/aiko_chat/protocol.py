#!/usr/bin/env python3
#
# Aiko Chat: wire protocol helpers (payload + recipient formatting)
#
# This module owns aiko_chat's application-level protocol POLICY -- the message
# schema (the "message" verb + its fields), the decode fallback ordering
# (framework S-expression -> legacy JSON -> bare string), field validation, and
# the "username: message" rendering. It does NOT own the wire codec itself:
# marshalling goes through the aiko_services framework serializer (generate /
# parse), which is the framework's code, tested by the framework. Swapping the
# codec (S-expression/JSON/AVRO) is a framework concern, not ours.
#
# `generate` / `parse` are imported lazily (inside the two functions that call
# them) rather than at module load, so `import aiko_chat.protocol` stays cheap
# and stdlib-only. The framework is loaded only when a payload is actually
# marshalled -- which lets the policy above be exercised in isolation. (A true
# framework-free import also needs the package __init__ to stop eagerly pulling
# in chat_server's robot example; tracked separately with the maintainers.)
#
# Leaf module within the package: everything else in the package may import
# this; it imports nothing from the package.
#
# Protocol
# ~~~~~~~~
# V1: 2026-06-08: Messages include username and timestamp (backward compatible)
# V0: 2025-12-23: Initial version

import json
import time
from typing import Iterable, List

__all__ = [
    "generate_recipients", "parse_recipients",
    "message_record", "encode_record",
    "generate_payload", "format_incoming",
]

_VERSION = 1
_MESSAGE_COMMAND = "message"  # Aiko function-call verb for a broadcast chat message

# --------------------------------------------------------------------------- #

def generate_recipients(recipients: Iterable[str] | None) -> str:
    if not recipients:
        return ""
    return ",".join(recipient.strip() for recipient in recipients)

def parse_recipients(recipients: str | None) -> List[str]:
    if not recipients:
        return []
    return list(filter(None, map(str.strip, recipients.split(","))))

def message_record(username, channel, message, timestamp=None):
    # The single definition of a chat message's field set (the "message"
    # function-call arguments). Both the wire encoder and any store (e.g. the
    # ChatServer's recent-message history) build from this one shape, so the
    # published bytes and the stored record can't drift apart. `timestamp`
    # defaults to now; pass it explicitly to store and publish one identical
    # record.
    return {
        "username": username,
        "channel": channel,
        "timestamp": time.time() if timestamp is None else timestamp,
        "message": message,
    }

def encode_record(record):
    # Marshal a message record (from message_record) to the wire. Expressing the
    # message as an Aiko function call ("message") lets the framework's pluggable
    # serializer own the wire format -- `generate()` emits an S-expression today
    # and can be swapped to JSON/AVRO without touching this code.
    from aiko_services.main.utilities import generate  # lazy: keep import cheap
    return generate(_MESSAGE_COMMAND, record)

def generate_payload(username, channel, message):
    # Convenience: build a fresh record and encode it in one step (unchanged
    # public behaviour). Callers that also need to STORE the record should use
    # message_record() + encode_record() so the stored and published record are
    # the same object.
    return encode_record(message_record(username, channel, message))

def format_incoming(payload_in):
    # Render a structured payload as "username: message". Decodes the framework
    # S-expression first, then falls back to the legacy JSON payload, then to a
    # bare string -- so older publishers keep working (forward/backward compat).
    fields = _decode_message(payload_in)
    if fields is None:
        return payload_in
    prefix = fields.get("username") or fields.get("channel", "")
    message = fields.get("message", "")
    return f"{prefix}: {message}" if prefix else message

def _decode_message(payload_in):
    from aiko_services.main.utilities import parse  # lazy: keep import cheap
    # 1) Framework S-expression: (message username: ... message: ...)
    #    Require the "message" field (mirroring the JSON branch) so a malformed
    #    call like (message username: nick) falls through instead of rendering
    #    as an empty "nick: ". Catch only the parser's decode failures, not
    #    every Exception, so real bugs surface instead of silently degrading.
    try:
        command, fields = parse(payload_in)
        if command == _MESSAGE_COMMAND and isinstance(fields, dict) \
                and "message" in fields:
            return fields
    except (ValueError, IndexError, TypeError):
        pass
    # 2) Legacy JSON payload from the previous wire format.
    try:
        data = json.loads(payload_in)
        if isinstance(data, dict) and "message" in data:
            return data
    except (TypeError, ValueError):
        pass
    return None

# --------------------------------------------------------------------------- #
