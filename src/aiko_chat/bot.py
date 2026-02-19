#!/usr/bin/env python3
#
# Usage
# ~~~~~
# ./bot.py run botname
# ./bot.py exit botname
#
# Or if aiko_chat module is not installed:
# aiko_chat/src$ python -m aiko_chat.bot run
#
# Notes
# ~~~~~
# Simple bot that connects to ChatServer and responds
# to messages mentioning @@botname.

from abc import abstractmethod
import click
import signal

import aiko_services as aiko
from aiko_chat import ChatServer, get_server_service_filter

__all__ = ["ChatBot", "ChatBotImpl"]

# To distinguish bots from humans, we use @@name for bots and @name for humans
_BOT_NAME = "@@bot"
_CHANNEL_NAME = "general"
_VERSION = 0

_ACTOR_BOT = "chat_bot"
_PROTOCOL_BOT = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_BOT}:{_VERSION}"


def get_chatbot_service_filter():
    return aiko.ServiceFilter(
        "*", _ACTOR_BOT, _PROTOCOL_BOT, "*", "*", "*")


class ChatBot(aiko.Actor):
    aiko.Interface.default("ChatBot", "aiko_chat.chat.ChatBotImpl")

    @abstractmethod
    def exit(self):
        pass


class ChatBotImpl(aiko.Actor):
    def __init__(self, context, botname):
        context.call_init(self, "Actor", context)
        self.share["source_file"] = f"v{_VERSION}⇒ {__file__}"
 
        self.chat_server = None
        self.botname = botname
 
        signal.signal(signal.SIGINT, self.on_sigint)

        service_discovery, service_discovery_handler = aiko.do_discovery(
            ChatServer, get_server_service_filter(),
            self.discovery_add_handler, self.discovery_remove_handler)

    def discovery_add_handler(self, service_details, service):
        self.print(f"Connected    {service_details[1]}: {service_details[0]}")
        self.chat_server = service
        server_topic_out = f"{service_details[0]}/{_CHANNEL_NAME}"
        self.add_message_handler(self.server_message_handler, server_topic_out)

    def discovery_remove_handler(self, service_details):
        self.print(f"Disconnected {service_details[1]}: {service_details[0]}")
        self.chat_server = None

    def server_message_handler(self, _aiko, topic, payload_in):
        self.print(f"Payload      {payload_in}")
        if f"{self.botname}" in payload_in:
            if not payload_in.endswith(" !!!!"):  # TODO: Fix this hack !
                if self.chat_server:
                    recipients = [_CHANNEL_NAME]
                    # More sophisticated bots can use AI to respond to payload_in here
                    self.chat_server.send_message(self.botname, recipients, f"Hello, I am {self.botname} !!!!")


    def on_sigint(self, signum, frame):
        aiko.process.terminate()

    def exit(self, botname):
        if botname in (self.botname, "all"):
            aiko.process.terminate()

    def print(self, output):
        print(f"BOT: {output}")


@click.group()

def main():
    """Run ChatBot"""
    pass

@main.command(name="run")
@click.argument("botname", type=str, required=False, default=_BOT_NAME)
def bot_command(botname):
    """Run ChatBot

    ./bot.py run BOTNAME
    """

    tags = ["ec=true"]
    init_args = aiko.actor_args(_ACTOR_BOT, protocol=_PROTOCOL_BOT, tags=tags)
    init_args["botname"] = botname
    chatbot = aiko.compose_instance(ChatBotImpl, init_args)
    chatbot.print('Type Ctrl+C to exit')
    aiko.process.run()

@main.command(name="exit", help="Stop ChatBot")
@click.argument("botname", type=str, required=False, default="all")
def exit_command(botname):
    aiko.do_command(ChatBot, get_chatbot_service_filter(),
        lambda chat: chat.exit(botname), terminate=True)
    aiko.process.run()

if __name__ == "__main__":
    main()
