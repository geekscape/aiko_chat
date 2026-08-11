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

# Never pulled in by a bot's imports: the examples package (Discussion #14),
# its vision deps, and the LLM stack that send_message() imports lazily.
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
    # Interface.default binds ChatServerImpl by string path, so naming it in
    # the interface must not import it.
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
    # Importing ANY submodule runs __init__ first, so what it re-exports is
    # what every importer pays for.
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
