#!/usr/bin/env python3
#
# Aiko Chat: per-channel recent message history
#
# A bounded, per-channel, time-ordered record store so a client joining a
# channel can be shown recent messages instead of a blank screen. Two
# operations: append(channel, record) and recent(channel, limit).
#
# SCOPE (deliberate): this is a RECENT-CONTEXT BUFFER, not an authoritative
# message store. It keeps the last `capacity` records per channel so joiners
# "don't start from nothing"; it makes no source-of-truth claim, so it can
# coexist with a richer downstream store (e.g. an island gateway's database)
# without a two-sources-of-truth conflict.
#
# DURABILITY: pass `path` (a directory) to persist across restarts -- one
# JSONL file per channel, rewritten from the (capped) in-memory buffer on each
# append, so the file stays naturally bounded. Omit `path` for in-memory only.
# The aiko-native durable backing (a real aiko_services Storage backend) is a
# framework question raised with the maintainers; this file-backed store is the
# swappable seam a framework backend would replace without changing callers.
#
# Pure leaf module: NO aiko_services dependency (stdlib only), so the store's
# behaviour can be unit-tested without the framework. It imports nothing from
# the package.

import json
import os
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Mapping, Optional
from urllib.parse import quote, unquote

__all__ = ["ChannelHistory"]

_DEFAULT_CAPACITY = 100  # recent records kept per channel
_SUFFIX = ".jsonl"


class ChannelHistory:
    """Bounded per-channel recent-message buffer, optionally file-durable.

    A record is a mapping of the four wire-protocol fields
    ``{username, channel, timestamp, message}`` (see protocol.message_record).
    The store neither validates nor interprets the record's keys, so the
    protocol can evolve without touching this module.

    In-memory when `path` is None; durable (survives restart) when `path` is a
    directory -- each channel is a `<path>/<quoted-channel>.jsonl` file.
    """

    def __init__(self, capacity: int = _DEFAULT_CAPACITY, path: Optional[str] = None):
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._channels: Dict[str, Deque[Mapping]] = {}
        self._dir: Optional[Path] = None
        if path is not None:
            self._dir = Path(path)
            self._dir.mkdir(parents=True, exist_ok=True)
            self._load()

    # -- public API -------------------------------------------------------- #

    def append(self, channel: str, record: Mapping) -> None:
        """Append one record, evicting the oldest past capacity; persist if durable."""
        buffer = self._buffer(channel)
        buffer.append(record)
        if self._dir is not None:
            self._persist(channel, buffer)

    def recent(self, channel: str, limit: int) -> List[Mapping]:
        """Return up to `limit` most-recent records for `channel`, oldest-first.

        Oldest-first so a client renders them top-to-bottom in send order.
        Unknown channel or limit <= 0 returns an empty list.
        """
        if limit <= 0:
            return []
        buffer = self._channels.get(channel)
        if not buffer:
            return []
        n = len(buffer)
        start = max(0, n - limit)
        return [buffer[i] for i in range(start, n)]

    # -- internals --------------------------------------------------------- #

    def _buffer(self, channel: str) -> Deque[Mapping]:
        buffer = self._channels.get(channel)
        if buffer is None:
            buffer = deque(maxlen=self._capacity)
            self._channels[channel] = buffer
        return buffer

    def _channel_file(self, channel: str) -> Path:
        # quote(safe="") makes the channel name filesystem-safe AND reversible
        # (unquote on load), so no '/' or other special chars leak into a name.
        assert self._dir is not None
        return self._dir / (quote(channel, safe="") + _SUFFIX)

    def _persist(self, channel: str, buffer: Deque[Mapping]) -> None:
        # Atomic rewrite: the file always equals the current (capped) buffer, so
        # it needs no separate compaction. tmp + os.replace = no torn file on crash.
        # The tmp name ends in ".jsonl.tmp", so the "*.jsonl" load glob skips it.
        target = self._channel_file(channel)
        tmp = target.parent / (target.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for record in buffer:
                f.write(json.dumps(record) + "\n")
        os.replace(tmp, target)

    def _load(self) -> None:
        assert self._dir is not None
        for entry in self._dir.glob("*" + _SUFFIX):
            channel = unquote(entry.stem)
            buffer: Deque[Mapping] = deque(maxlen=self._capacity)
            with open(entry, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        buffer.append(json.loads(line))
            self._channels[channel] = buffer
