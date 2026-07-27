#!/usr/bin/env python3
#
# Aiko Chat CLI: distributed Actor commands (run / repl / send / exit)
#
# This module is the `aiko_chat` console entry point (see pyproject.toml).
# It wires together the ChatServer (chat_server.py), the ChatREPL client
# (chat_repl.py) and the shared wire helpers (protocol.py).
#
# Usage
# ~~~~~
# ./chat.py run
# ./chat.py exit
#
# ./chat.py repl [username] [channel]
# ./chat.py send recipient[,recipient ...]  message
#
# Usage: Low-level MQTT messages
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# HOST_NAME="${HOSTNAME%%.*}"
# PID="$(pgrep -f './chat.py' | head -n1)"
# TOPIC="aiko/$HOST_NAME/$PID/1/in"
#
# mosquitto_pub -t $TOPIC -m "(send_message username @all hello)"
# Notes
# ~~~~~
# recipients: channel(s) or @username(s): @all, @here
#
# Protocol
# ~~~~~~~~
# V1: 2026-06-08: Messages include username and timestamp (backward compatible)
# V0: 2025-12-23: Initial version
#
# To Do
# ~~~~~
# *** Refactor LLM and Robot hacks
#     - Enable LLM, either ":llm_enable" or "#llm channel" message "enable" !
#     - Separate functions
#     - Provide simple conversational history
#     - Dynamically loaded "channel features" ?
#
# * Fix: Discover ChatServer via "owner" field ... support multiple concurrent
#   - Default search "owner" should be "*"
#   - Default "username" should be the "$USERNAME", override with REPL argument
#
# * Replace use of JSON with S-Expressions, i.e parser() and generator()
# * Replace hand-coded protocol messages with function calls (design principle)
#
# - Chat commands: MQTT pub/sub, do_command()/do_request to Service
#   - Connect Services/Actors via Dependencies and/or Categories ?
#
# - Support multiple channels via HyperSpace ?
#   * Create Category and Channels with the correct protocol type and owner
#   - What is stored in each Channel Dependency storage file ?
# - Support multiple users via HyperSpace ?
#   * Create Category and Users with the correct protocol type and owner
#   - What is stored in each User Dependency storage file ?
#
# - Implement "ChatServer.topic_out" Dependency link ...
#   - "ChatServer.topic_out" --[function_call]--> "ChatREPL.topic_in"
#
#
# - UI: CLI (REPL), TUI (Dashboard plug-in), Web
#   - Implement ":commands", e.g ":help" as dynamic plug-ins
#   - Refactor standard tty REPL ("scheme_tty.py") to use ReplSession ?
#
# - Incorporate A.I Agents and Robots (real and virtual TUI/GUI)
#   - LLM with RAG based on chat history, other information sources (tools)
#
# - Security: ACLs (roles, users), encryption (shared symmetric keys) ?

import click

import aiko_services as aiko

from .protocol import parse_recipients
from .chat_server import (
    ChatServer, ChatServerImpl, get_server_service_filter,
    _ACTOR_SERVER, _PROTOCOL_SERVER)
from .chat_repl import ChatREPLImpl, _ACTOR_REPL, _PROTOCOL_REPL

__all__ = ["main"]

# --------------------------------------------------------------------------- #
# Aiko Chat CLI: Distributed Actor commands

@click.group()

def main():
    """Run and exit ChatServer backend"""
    pass

@main.command(name="exit", help="Exit ChatServer backend")
def exit_command():
    aiko.do_command(ChatServer, get_server_service_filter(),
        lambda chat: chat.exit(), terminate=True)
    aiko.process.run()

@main.command(name="repl")
@click.argument("username", type=str, required=False, default=None)
def repl_command(username):
    """Run Chat CLI REPL frontend

    ./chat.py repl
    """

    tags = ["ec=true"]       # TODO: Add ECProducer tag before add to Registrar
    init_args = aiko.actor_args(_ACTOR_REPL, protocol=_PROTOCOL_REPL, tags=tags)
    init_args["username"] = username
    chat = aiko.compose_instance(ChatREPLImpl, init_args)
    aiko.process.run()
    chat.join()  # wait until Chat ReplSession has cleaned-up

@main.command(name="run")
@click.option("--llm", is_flag=True, help="Enable LLM (via ollama)")
def run_command(llm):
    """Run ChatServer backend

    ./chat.py run
    """

    tags = ["ec=true"]       # TODO: Add ECProducer tag before add to Registrar
    init_args = aiko.actor_args(
                    _ACTOR_SERVER, protocol=_PROTOCOL_SERVER, tags=tags)
    init_args["llm_enabled"] = llm
    chat = aiko.compose_instance(ChatServerImpl, init_args)
    aiko.process.run()

@main.command(name="send")
@click.argument("recipients", type=str, required=True, default=None)
@click.argument("message", type=str, required=True, default=None)

def send_command(recipients, message):
    """Send message to recipients (channels and/or users)

    ./chat.py send RECIPIENTS MESSAGE

    \b
    • RECIPIENTS: List of one or more (comma separated) #channels or @usernames
    • MESSAGE:    Data to be sent to the recipients
    """

    recipient_list = parse_recipients(recipients)
    username = ""
    aiko.do_command(ChatServer, get_server_service_filter(),
        lambda chat: chat.send_message(username, recipient_list, message),
        terminate=True)
    aiko.process.run()

if __name__ == "__main__":
    main()

# --------------------------------------------------------------------------- #
