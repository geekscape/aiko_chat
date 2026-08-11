# Declaration order follows the dependency DAG (leaf first):
#   protocol <- chat_server_interface <- chat_server <- chat_repl <- chat (CLI)
# repl_session is an independent leaf.
#
# Re-exports the CLIENT side only: the wire protocol and the ChatServer
# contract. Importing any submodule runs this file first, so whatever is named
# here is paid for by every importer -- while ChatServerImpl and ChatREPL were
# re-exported, `import aiko_chat.protocol` loaded the whole server and REPL.
#
# Server-side code imports from its own module, e.g.
#   from aiko_chat.chat_server import ChatServerImpl
#
# tests/test_import_decoupling.py pins this; re-exporting a heavy module here
# silently undoes the split.

from .protocol import (
    generate_recipients, parse_recipients,
    generate_payload, format_incoming)

from .chat_server_interface import ChatServer, get_server_service_filter

__all__ = [
    "generate_recipients", "parse_recipients",
    "generate_payload", "format_incoming",
    "ChatServer", "get_server_service_filter",
]
