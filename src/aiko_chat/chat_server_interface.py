#!/usr/bin/env python3
#
# Aiko ChatServer: the interface, and how to discover one.
# The implementation is in chat_server.py.
#
# Interface.default() binds the implementation by dotted STRING path, resolved
# at compose time, so naming ChatServerImpl here does not import it.

from abc import abstractmethod

import aiko_services as aiko

from .protocol import _VERSION

__all__ = ["ChatServer", "get_server_service_filter"]

_ACTOR_SERVER = "chat_server"
_PROTOCOL_SERVER = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_SERVER}:{_VERSION}"

# --------------------------------------------------------------------------- #

def get_server_service_filter():
    return aiko.ServiceFilter(
        "*", _ACTOR_SERVER, _PROTOCOL_SERVER, "*", "*", "*")

# --------------------------------------------------------------------------- #

class ChatServer(aiko.Actor):
    aiko.Interface.default("ChatServer", "aiko_chat.chat_server.ChatServerImpl")

    @abstractmethod
    def exit(self):
        pass

    @abstractmethod
    def send_message(self, username, recipients, message):
        pass

# --------------------------------------------------------------------------- #
