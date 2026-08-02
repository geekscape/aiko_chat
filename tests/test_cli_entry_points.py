#!/usr/bin/env python3
#
# Regression tests for aiko_chat's CLI entry points (src/aiko_chat/chat.py).
#
# chat.py is reachable three ways, and all three must keep working:
#
#   1. ./chat.py repl            -- direct script execution. Documented in
#                                   chat.py's own header ("./chat.py run",
#                                   "./chat.py repl [username] [channel]") and
#                                   relied on by its low-level MQTT recipe
#                                   (`pgrep -f './chat.py'`). The file carries a
#                                   shebang and the executable bit on purpose.
#   2. python -m aiko_chat.chat  -- package-relative execution.
#   3. aiko_chat                 -- the console script declared in
#                                   pyproject.toml (aiko_chat.chat:main).
#
# Case (1) regressed in 26d83bc, which split chat.py into protocol /
# chat_server / chat_repl / CLI and converted chat.py's imports from absolute
# to relative. A file run directly becomes __main__, whose __package__ is empty,
# so a relative import has no parent to resolve against and CPython raises
# ImportError before any path lookup. Cases (2) and (3) were unaffected, which
# is why the regression was invisible -- hence all three are pinned here.
#
# These tests drive `<subcommand> --help`: it exercises every module-level
# import in chat.py (where the failure is) and then exits through click,
# without composing an Actor, opening a broker connection or sending anything.
# No MQTT broker, Registrar or ChatServer is required -- Tier 1 (Unit).
#
# Import note: unlike test_protocol.py, these tests cannot stay framework-free.
# chat.py imports aiko_services, and chat_server.py imports an aiko_services
# robot *example* that is not part of a stock install -- the pre-existing
# packaging issue documented in test_protocol.py. The importorskip below names
# that exact requirement, so a stock environment skips rather than errors.
#
# Subprocesses get this checkout's src/ at the front of PYTHONPATH so they test
# THIS tree, not whichever aiko_chat a development venv has installed editable.

import os
import subprocess
import sys
from pathlib import Path


_SRC = Path(__file__).resolve().parent.parent / "src"
_CHAT_PY = _SRC / "aiko_chat" / "chat.py"

# --------------------------------------------------------------------------- #

def _run(*arguments, cwd=None):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(_SRC), environment.get("PYTHONPATH")]))
    return subprocess.run(
        [sys.executable, *arguments], cwd=cwd, env=environment,
        capture_output=True, text=True, timeout=60)

def _assert_cli_help(result, entry_point):
    assert "ImportError" not in result.stderr, \
        f"{entry_point} failed at import time:\n{result.stderr}"
    assert result.returncode == 0, \
        f"{entry_point} exited {result.returncode}:\n{result.stderr}"
    assert "Usage:" in result.stdout, \
        f"{entry_point} printed no click help:\n{result.stdout}"

# --------------------------------------------------------------------------- #
# The three entry points

def test_direct_script_execution():
    # "./chat.py repl" from within src/aiko_chat -- the documented invocation.
    result = _run(str(_CHAT_PY), "repl", "--help", cwd=str(_CHAT_PY.parent))
    _assert_cli_help(result, "./chat.py repl --help")

def test_module_execution():
    # Guards the fix for direct execution against breaking the package path.
    result = _run("-m", "aiko_chat.chat", "repl", "--help")
    _assert_cli_help(result, "python -m aiko_chat.chat repl --help")

def test_console_entry_point_target_imports():
    # pyproject.toml: aiko_chat = "aiko_chat.chat:main"
    result = _run(
        "-c", "import aiko_chat.chat as chat; chat.main(['repl', '--help'])")
    _assert_cli_help(result, "aiko_chat.chat:main")

# --------------------------------------------------------------------------- #
