#!/usr/bin/env python3
#
# Aiko ChatREPL: interactive CLI client Actor (Interface and Implementation)
#
# The ChatREPL discovers a ChatServer, subscribes to a channel's MQTT topic and
# drives the terminal via ReplSession. ":" commands (:cc, :help, :exit, :lc)
# are handled locally; anything else is sent to the server as a message.

import os
import signal

import aiko_services as aiko

from .protocol import format_incoming, _VERSION
from .chat_server import ChatServer, get_server_service_filter
from .repl_session import FileHistoryStore, ReplSession

__all__ = ["ChatREPL", "ChatREPLImpl"]

_CHANNEL_NAME = "general"  # TODO: Support multiple channels (CRUD)
_HISTORY_PATHNAME = None
_HISTORY_LIMIT = 50  # recent messages to request when joining a channel

_ACTOR_REPL = "chat_repl"
_PROTOCOL_REPL = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_REPL}:{_VERSION}"

# --------------------------------------------------------------------------- #
# Aiko ChatREPL: Interface and Implementation

class ChatREPL(aiko.Actor):
    aiko.Interface.default("ChatREPL", "aiko_chat.chat_repl.ChatREPLImpl")

class ChatREPLImpl(aiko.Actor):
    def __init__(self, context, username=None):
        context.call_init(self, "Actor", context)
        self.share["source_file"] = f"v{_VERSION}⇒ {__file__}"

        self.chat_server = None

        self.username = username or os.environ.get("USER")
        self.current_channel = _CHANNEL_NAME
        self.history_store = None
        if _HISTORY_PATHNAME:
            self.history_store = FileHistoryStore(_HISTORY_PATHNAME)
        self.repl_session = ReplSession(
            self.command_handler, history_store=self.history_store)
        signal.signal(signal.SIGINT, self.on_sigint)
        signal.signal(signal.SIGWINCH, self.on_sigwinch)
        self.repl_session.start(daemon=True)

        self.chat_server_share = {}

        service_discovery, service_discovery_handler = aiko.do_discovery(
            ChatServer, get_server_service_filter(),
            self.discovery_add_handler, self.discovery_remove_handler)

        self.print('Type ":exit" or ":x" to exit')
        self.print('Type ":help" or ":?" for instructions')
        self.print(f"Channel: {self.current_channel}")

    def command_handler(self, command_line, _repl_session):
        command_line = command_line.strip()
        if not command_line:
            return

        tokens = command_line.split(" ")
        command = tokens[0]
        if command in [":change_channel", ":cc"]:
            if len(tokens) > 1:
                self.current_channel = tokens[1]
                self.remove_message_handler(
                    self.server_message_handler, self.chat_server_topic)
                self.chat_server_topic =  \
                    f"{self.chat_server_topic_path}/{self.current_channel}"
                self.add_message_handler(
                    self.server_message_handler, self.chat_server_topic)
                self._request_history(self.current_channel)
        elif command in [":exit", ":x"]:
            self.repl_session.stop()
            aiko.process.terminate()
        elif command in [":help", ":?"]:
            self.print(":change_channel, :cc  Change chat channel")
            self.print(":exit,           :x   Exit Chat")
            self.print(":help,           :?   Show instructions")
            self.print(":list_channels,  :lc  List chat channels")
        elif command in [":list_channels", ":lc"]:
            self.print("general, llm, random, robot, yolo")
        else:
            if self.chat_server:
            #   username = ""  #TODO #PR-2: admin = "" ?
                recipients = [self.current_channel]
                self.chat_server.send_message(
                    self.username, recipients, command_line)

    def discovery_add_handler(self, service_details, service):
        self.print(f"Connected {service_details[1]}: {service_details[0]}")
        self.chat_server = service
        self.chat_server_topic_path = service_details[0]
        self.chat_server_topic =  \
            f"{self.chat_server_topic_path}/{self.current_channel}"
        self.add_message_handler(
            self.server_message_handler, self.chat_server_topic)
        self._request_history(self.current_channel)

        self.chat_server_topic_control =  \
            f"{self.chat_server_topic_path}/control"
        self.ec_consumer = aiko.ECConsumer(
            self, 0, self.chat_server_share, self.chat_server_topic_control)
        #   filter="channel_list")
        self.ec_consumer.add_handler(self._ec_consumer_change_handler)

    def _ec_consumer_change_handler(
        self, client_id, command, item_name, item_value):

    #   self.logger.info(
    #       f"ECConsumer: {client_id}: {command} {item_name} {item_value}\n")
        pass

    def discovery_remove_handler(self, service_details):
        self.print(f"Disconnected {service_details[1]}: {service_details[0]}")
        if self.ec_consumer:
            self.ec_consumer.terminate()
        self.ec_consumer = None
        self.chat_server = None
        self.chat_server_share = {}

    def join(self):
        self.repl_session.join()  # wait until background thread has cleaned-up

    def _request_history(self, channel):
        # On joining `channel`, ask the server for recent messages and render
        # them before live messages arrive. We pass our OWN inbox (self.topic_in)
        # as the reply topic, so the server replies point-to-point to us. The
        # response payloads are the same wire encoding as live messages, so
        # format_incoming renders them identically. Records arrive oldest-first.
        def response_handler(response):
            for item in response:
                self.print(format_incoming(item[0]))
        aiko.do_request(
            ChatServer, get_server_service_filter(),
            lambda server: server.request_history(
                self.topic_in, channel, _HISTORY_LIMIT),
            response_handler, self.topic_in)

    def server_message_handler(self, _aiko, topic, payload_in):
        self.print(format_incoming(payload_in))

    def on_sigint(self, signum, frame):
        self.repl_session.stop()
        aiko.process.terminate()

    def on_sigwinch(self, signum, frame):
        self.repl_session.request_resize()

    def print(self, output):
        self.repl_session.post_message(output)

# --------------------------------------------------------------------------- #
