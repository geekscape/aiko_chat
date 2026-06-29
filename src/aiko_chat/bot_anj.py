#!/usr/bin/env python3
print("Hello, running Anjbot")
#import sys
#sys.exit()

from bot import ChatBot
import click
import aiko_services as aiko

# To distinguish bots from humans, we use @@name for bots and @name for humans
_BOT_NAME = "@@anjbot"   # default bot name, can be overridden in subclasses
_CHANNEL_NAME = "general" # default channel, can be changed using change_channel()
_VERSION = 0
_ACTOR_BOT = "chat_bot"
_PROTOCOL_BOT = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_BOT}:{_VERSION}"

def get_chatbot_service_filter():
    return aiko.ServiceFilter(
        "*", _ACTOR_BOT, _PROTOCOL_BOT, "*", "*", "*")


class AnjChatBot(ChatBot):
    def __init__(self, context: ChatBot, botname: str):
        context.call_init(self, "ChatBot", context)
        self.botname = botname

    def process_message(self, payload_in, **kwargs):
        self.print(f"Payload      {payload_in}")
        if f"{self.botname}" in payload_in:
            if not payload_in.endswith(" !!!!"):  # TODO: Fix this hack ! (prevent's processing bot's own response)
                if "join" in payload_in:
                    # Treat as instruction for bot to join a different channel
                    channel = payload_in.split("join")[-1].strip()
                    self.change_channel(channel)

                if self.chat_server:
                    recipients = [self.current_channel]
                    # More sophisticated bots can use AI to respond to payload_in here
                    self.chat_server.send_message(self.botname, recipients, f"Hello, I am {self.botname} !!!!")

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
    chatbot = aiko.compose_instance(AnjChatBot, init_args)
    chatbot.print('Type Ctrl+C to exit')
    aiko.process.run()

@main.command(name="exit", help="Stop ChatBot")
@click.argument("botname", type=str, required=False, default="all")
def exit_command(botname):
    aiko.do_command(ChatBot, get_chatbot_service_filter(),
        lambda chat: chat.terminate(botname), terminate=True)
    aiko.process.run()

if __name__ == "__main__":
    main()