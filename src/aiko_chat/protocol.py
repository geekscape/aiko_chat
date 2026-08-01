#!/usr/bin/env python3
#
# Aiko Chat: wire protocol helpers (payload + recipient formatting)
#
# Marshalling goes through the aiko_services framework serializer
# (generate/parse), so the wire format can be swapped (S-expression/JSON/AVRO)
# without touching this module. Leaf module within the package: everything else
# in the package may import this; it imports nothing from the package.
#
# Protocol
# ~~~~~~~~
# V1: 2026-06-08: Messages include username and timestamp (backward compatible)
# V0: 2025-12-23: Initial version

import json
import time
from typing import Iterable, List

from aiko_services.main.utilities import generate, parse

__all__ = [
    "generate_recipients", "parse_recipients",
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

def generate_payload(username, channel, message):
    # Express the outgoing message as an Aiko function call ("message") and let
    # the framework's pluggable serializer marshal it, instead of hand-rolling
    # the wire format here. `generate()` emits an S-expression today and can be
    # swapped to JSON/AVRO without touching this code -- so a developer deals in
    # function calls and their arguments, not wire protocols. Sender identity
    # (username, channel, timestamp) rides along as the call's arguments.
    return generate(_MESSAGE_COMMAND, {
        "username": username,
        "channel": channel,
        "timestamp": time.time(),
        "message": message,
    })

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
