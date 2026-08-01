#!/usr/bin/env python3
#
# Aiko Chat: per-channel recent message history
#
# A small, bounded, per-channel, time-ordered record store so a client joining
# a channel can be shown recent messages instead of a blank screen. Two
# operations: append(channel, record) and recent(channel, limit).
#
# SCOPE (v1, deliberate): this is a RECENT-CONTEXT BUFFER, not an authoritative
# message store. It keeps the last `capacity` records per channel so joiners
# "don't start from nothing"; it makes no source-of-truth claim, so it can
# coexist with a richer downstream store (e.g. an island gateway's database)
# without a two-sources-of-truth conflict.
#
# OPEN QUESTION (see Discussion): durability across restarts. This in-memory
# implementation is the seam, not the answer -- the aiko-native durable backing
# (StorageFile / HyperSpace vs a simple file) is exactly what the paired design
# Discussion is for. `ChannelHistory` is the interface a durable impl slots into.
#
# Pure leaf module: NO aiko_services dependency, so the store's behaviour can be
# unit-tested without the framework. It imports nothing from the package.

from collections import deque
from typing import Deque, Dict, List, Mapping

__all__ = ["ChannelHistory"]

_DEFAULT_CAPACITY = 100  # recent records kept per channel


class ChannelHistory:
    """Bounded per-channel recent-message buffer.

    A record is a mapping of the four wire-protocol fields
    ``{username, channel, timestamp, message}`` (see protocol.generate_payload).
    The store is agnostic to the record's exact keys -- it neither validates nor
    interprets them -- so the protocol can evolve without touching this module.
    """

    def __init__(self, capacity: int = _DEFAULT_CAPACITY):
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._channels: Dict[str, Deque[Mapping]] = {}

    def append(self, channel: str, record: Mapping) -> None:
        """Append one record to a channel's history, evicting the oldest past capacity."""
        buffer = self._channels.get(channel)
        if buffer is None:
            buffer = deque(maxlen=self._capacity)
            self._channels[channel] = buffer
        buffer.append(record)

    def recent(self, channel: str, limit: int) -> List[Mapping]:
        """Return up to `limit` most-recent records for `channel`, oldest-first.

        Oldest-first so a client can render them top-to-bottom in the order they
        were sent. Unknown channel or limit <= 0 returns an empty list.
        """
        if limit <= 0:
            return []
        buffer = self._channels.get(channel)
        if not buffer:
            return []
        # deque keeps insertion order (oldest left); take the last `limit`.
        n = len(buffer)
        start = max(0, n - limit)
        return [buffer[i] for i in range(start, n)]
