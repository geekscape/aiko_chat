# Declaration order follows the dependency DAG (leaf first):
#   protocol <- chat_server_interface <- chat_server <- chat_repl <- chat (CLI)
# repl_session is an independent leaf.
#
# This file re-exports the CLIENT side only: the wire protocol and the
# ChatServer contract, both cheap and dependency-light. It deliberately does
# NOT re-export ChatServerImpl, ChatREPL or ReplSession.
#
# The reason is mechanical: importing any submodule runs this file first, so
# anything named here is paid for by every importer. While the server and the
# REPL were re-exported, `import aiko_chat.protocol` loaded the whole server --
# which is what made bot.py drag in the ChatServer implementation no matter how
# the modules were split.
#
# Server-side and REPL-side code imports from its own module:
#   from aiko_chat.chat_server import ChatServerImpl
#   from aiko_chat.chat_repl import ChatREPLImpl
#   from aiko_chat.repl_session import FileHistoryStore, ReplSession
#
# tests/test_import_decoupling.py pins this. Re-exporting a heavy module here
# undoes the split silently -- the modules stay separate and the imports do not.

from .protocol import (
    generate_recipients, parse_recipients,
    generate_payload, format_incoming)

from .chat_server_interface import ChatServer, get_server_service_filter

__all__ = [
    "generate_recipients", "parse_recipients",
    "generate_payload", "format_incoming",
    "ChatServer", "get_server_service_filter",
]
