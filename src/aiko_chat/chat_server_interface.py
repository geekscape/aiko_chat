#!/usr/bin/env python3
#
# Aiko ChatServer: the interface, and how to discover one.
#
# This is everything a CLIENT of the chat server needs: the ChatServer contract
# and the ServiceFilter that finds a running one. It deliberately holds no
# implementation -- see chat_server.py for ChatServerImpl.
#
# WHY THE SPLIT (Angie, 2026-08-08): a bot needs to FIND a chat server, not RUN
# one. With the contract and the implementation in one module, `from aiko_chat
# import ChatServer` executed the entire server: HyperSpace wiring, robot
# discovery, the LLM system prompt, and -- until the Robot seam landed (see
# robot.py) -- an aiko_services robot *example* absent from a stock install.
# That was concrete pain: bot.py could not be imported in Google Colab without
# hand-commenting the dependency out first.
#
# WHY IT WORKS: aiko.Interface.default() binds an implementation by dotted
# STRING path, resolved at compose time, not by import. So the interface can
# name ChatServerImpl without loading it, and a client pays only for the
# contract. tests/test_import_decoupling.py pins this -- it is an invariant,
# not an accident, and an eager import anywhere in the package undoes it.
#
# Mirrors the same move one layer down: robot.py declares only what the
# ChatServer calls on a robot, so no robot example is imported either.

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
