#!/usr/bin/env python3
#
# What a ChatBot author has to import in order to talk to a ChatServer.
#
# A bot needs to FIND a chat server, not RUN one. Before the chat_server
# interface was split out, `from aiko_chat import ChatServer` executed
# chat_server.py -- the whole implementation: HyperSpace wiring, robot
# discovery, the LLM system prompt and (historically) an aiko_services robot
# *example* that a stock install does not ship. That last one was concrete
# pain, not theory: bot.py could not be imported in Google Colab without
# hand-commenting the dependency out first.
#
# The example import is gone (see robot.py -- the ChatServer now discovers
# robots through a minimal Robot contract). These tests pin the remaining half
# so it cannot come back: importing the *interface* must not execute the
# *implementation*, and neither must reach outside a stock aiko_services.
#
# Why a subprocess for every case: sys.modules is process-global and pytest has
# already imported plenty by collection time, so an in-process assertion about
# "what got loaded" measures the test session, not the import. Each case gets a
# clean interpreter and reports its own sys.modules.
#
# Tier 1 (Unit) -- no broker, Registrar or ChatServer required.

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

# Modules that must never be pulled in by a bot's imports. The examples package
# is the packaging issue (Discussion #14); the rest are its heavy transitive
# deps and the optional LLM stack, which chat_server.py imports lazily inside
# send_message() and must keep importing lazily.
_FORBIDDEN = (
    "aiko_services.examples",
    "cv2",
    "numpy",
    "PIL",
    "langchain_core",
    "httpx",
)

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

def _assert_none_forbidden(modules, statement):
    for forbidden in _FORBIDDEN:
        offenders = sorted(
            name for name in modules
            if name == forbidden or name.startswith(f"{forbidden}."))
        assert not offenders, \
            f"`{statement}` pulled in {forbidden}: {offenders}"

# --------------------------------------------------------------------------- #
# The interface is importable without the implementation

def test_interface_import_does_not_execute_the_implementation():
    # The contract a bot depends on. ChatServerImpl is bound by string path
    # (aiko.Interface.default), so naming it must not import it.
    statement = (
        "from aiko_chat.chat_server_interface import "
        "ChatServer, get_server_service_filter")
    modules = _loaded_modules(statement)
    assert "aiko_chat.chat_server" not in modules, \
        ("importing the ChatServer interface executed the implementation "
         "module -- the split is not doing its job")

def test_interface_import_avoids_examples_and_heavy_dependencies():
    statement = "from aiko_chat.chat_server_interface import ChatServer"
    _assert_none_forbidden(_loaded_modules(statement), statement)

def test_package_import_avoids_examples_and_heavy_dependencies():
    # `import aiko_chat` runs __init__.py, so a lazy re-export there is what
    # keeps a submodule import cheap -- importing ANY submodule runs it first.
    statement = "import aiko_chat"
    _assert_none_forbidden(_loaded_modules(statement), statement)

def test_package_import_does_not_execute_the_repl_or_implementation():
    modules = _loaded_modules("import aiko_chat")
    for eager in ("aiko_chat.chat_server",
                  "aiko_chat.chat_repl",
                  "aiko_chat.repl_session"):
        assert eager not in modules, \
            (f"`import aiko_chat` eagerly executed {eager}; a bot that only "
             "needs the ChatServer interface should not pay for it")

# --------------------------------------------------------------------------- #
# ...and the client-side names the package does re-export still work

def test_package_re_exports_the_client_api():
    # What __init__ is allowed to cost an importer: the wire protocol and the
    # ChatServer contract. Cheap, and what a bot author actually reaches for.
    _loaded_modules(
        "from aiko_chat import ("
        "ChatServer, get_server_service_filter, generate_recipients, "
        "parse_recipients, generate_payload, format_incoming)")

def test_server_and_repl_import_from_their_own_modules():
    # Deliberately NOT re-exported by __init__ (that is what made the package
    # expensive). Server-side callers name the module they want.
    _loaded_modules(
        "from aiko_chat.chat_server import ChatServerImpl\n"
        "from aiko_chat.chat_repl import ChatREPL, ChatREPLImpl\n"
        "from aiko_chat.repl_session import FileHistoryStore, ReplSession\n")

# --------------------------------------------------------------------------- #
