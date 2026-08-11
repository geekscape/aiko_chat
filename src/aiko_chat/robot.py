#!/usr/bin/env python3
#
# Aiko Chat: minimal Robot interface (a TEMPORARY seam)
#
# Declaring the one method the ChatServer calls avoids importing xgo_robot,
# whose vision dependencies are absent from a stock aiko_services install
# (Discussion #14). Delete this file when a framework-level Robot interface
# lands, and change chat_server.py's import.

from abc import abstractmethod

__all__ = ["Robot"]


class Robot:
    """The robot contract the ChatServer discovers against.

    Discovery-only: get_service_proxy() builds an MQTT proxy from these method
    NAMES, so nothing here is instantiated locally (hence no Interface.default
    or Actor base) and only the name must match a replacement -- `value`
    mirrors XGORobot.action(self, value).
    """

    @abstractmethod
    def action(self, value):
        ...
