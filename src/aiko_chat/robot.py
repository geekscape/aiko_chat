#!/usr/bin/env python3
#
# Aiko Chat: minimal Robot interface (a TEMPORARY seam)
#
# The ChatServer needs exactly one thing from a discovered robot: action().
# Declaring it here avoids importing xgo_robot, whose vision dependencies are
# not in a stock aiko_services install (Discussion #14).
#
# A SEAM, not a parallel abstraction: delete this file when a framework-level
# Robot interface lands and change chat_server.py's import. The proxy is built
# from method NAMES over the wire, so only the name has to match -- `value`
# mirrors XGORobot.action(self, value) to keep convergence cheap.

from abc import abstractmethod

__all__ = ["Robot"]


class Robot:
    """The robot contract the ChatServer discovers against.

    Discovery-only: get_service_proxy() introspects these method names to build
    an MQTT proxy for a remote robot Actor. Never instantiated locally, so it
    needs no Interface.default or Actor base.
    """

    @abstractmethod
    def action(self, value):
        ...
