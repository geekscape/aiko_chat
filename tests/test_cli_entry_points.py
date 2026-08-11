#!/usr/bin/env python3
#
# Regression tests for chat.py's three entry points: ./chat.py, python -m
# aiko_chat.chat, and the aiko_chat console script.
#
# Only direct execution can break this way, which is why it broke unnoticed in
# 26d83bc: a file run directly is __main__ with an empty __package__, so its
# relative imports raise ImportError before any path lookup.
#
# `<subcommand> --help` exercises every module-level import, then exits through
# click without composing an Actor -- Tier 1, no broker.
#
# Do NOT add a pytest.importorskip here. The previous one named an
# aiko_services example, which a stock install (i.e. CI) lacks, so it silently
# skipped this whole file on every run.
#
# Subprocesses get this checkout's src/ first on PYTHONPATH, so they test THIS
# tree rather than an editable install.

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
