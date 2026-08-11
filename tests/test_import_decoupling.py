#!/usr/bin/env python3
#
# A bot needs to FIND a chat server, not RUN one. These pin that: importing the
# ChatServer interface must not execute the implementation, and neither may
# reach outside a stock aiko_services install (bot.py could not be imported in
# Colab until it did).
#
# Each case runs in a subprocess because sys.modules is process-global -- an
# in-process assertion would measure the pytest session, not the import.
#
# Tier 1 (Unit) -- no broker.

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

# Every aiko_chat module a bot is allowed to load. An exact set rather than a
# denylist of heavy imports: a denylist only catches dependencies someone
# thought to list, and every heavy one arrives THROUGH a module named here.
_CLIENT_SIDE = {
    "aiko_chat",
    "aiko_chat.bot",
    "aiko_chat.chat_server_interface",
    "aiko_chat.protocol",
}

# --------------------------------------------------------------------------- #

def _loaded_modules(statement):
    """Run `statement` in a clean interpreter; return its sys.modules names."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(_SRC), environment.get("PYTHONPATH")]))
    program = (
        f"{statement}\n"
        "import sys, json\n"
        "print(json.dumps(sorted(sys.modules)))\n")
    result = subprocess.run(
        [sys.executable, "-c", program],
        env=environment, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, \
        f"`{statement}` failed:\n{result.stderr}"
    return set(json.loads(result.stdout.splitlines()[-1]))

def _aiko_chat_modules(statement):
    return {name for name in _loaded_modules(statement)
            if name == "aiko_chat" or name.startswith("aiko_chat.")}

# --------------------------------------------------------------------------- #
# The interface is importable without the implementation

def test_bot_loads_only_the_client_side_of_the_package():
    assert _aiko_chat_modules("import aiko_chat.bot") == _CLIENT_SIDE

def test_package_import_loads_neither_the_server_nor_the_repl():
    # Importing ANY submodule runs __init__ first, so what it re-exports is
    # what every importer pays for.
    assert _aiko_chat_modules("import aiko_chat") == _CLIENT_SIDE - {
        "aiko_chat.bot"}

def test_interface_import_does_not_execute_the_implementation():
    # Interface.default binds ChatServerImpl by string path, so naming it in
    # the interface must not import it.
    modules = _aiko_chat_modules(
        "from aiko_chat.chat_server_interface import "
        "ChatServer, get_server_service_filter")
    assert "aiko_chat.chat_server" not in modules

def test_no_client_import_reaches_the_examples_package():
    # The stock-install failure (Discussion #14): aiko_services ships without
    # examples, so a bot that touches them cannot be imported at all.
    for statement in ("import aiko_chat", "import aiko_chat.bot"):
        examples = sorted(name for name in _loaded_modules(statement)
                          if name.startswith("aiko_services.examples"))
        assert not examples, f"`{statement}` loaded {examples}"

# --------------------------------------------------------------------------- #
# ...and the client-side names the package does re-export still work

def test_package_re_exports_the_client_api():
    _loaded_modules(
        "from aiko_chat import ("
        "ChatServer, get_server_service_filter, generate_recipients, "
        "parse_recipients, generate_payload, format_incoming)")

def test_server_and_repl_import_from_their_own_modules():
    # Deliberately not re-exported by __init__; callers name the module.
    _loaded_modules(
        "from aiko_chat.chat_server import ChatServerImpl\n"
        "from aiko_chat.chat_repl import ChatREPL, ChatREPLImpl\n"
        "from aiko_chat.repl_session import FileHistoryStore, ReplSession\n")

# --------------------------------------------------------------------------- #
