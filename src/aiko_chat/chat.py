#!/usr/bin/env python3
#
# Usage
# ~~~~~
# ./chat.py
#
# HOST_NAME="${HOSTNAME%%.*}"
# PID="$(pgrep -f './chat.py' | head -n1)"
# TOPIC="aiko/$HOST_NAME/$PID/1/in"
#
# mosquitto_pub -t $TOPIC -m "(test payload_example)"
#
# To Do
# ~~~~~
# - None, yet !

from abc import abstractmethod

import aiko_services as aiko

_VERSION = 0

_ACTOR_TYPE = "chat"
_PROTOCOL = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_TYPE}:{_VERSION}"

# --------------------------------------------------------------------------- #

class Chat(aiko.Actor):
    aiko.Interface.default("Chat", "aiko_chat.chat.ChatImpl")

    @abstractmethod
    def test(self, payload):
        pass

class ChatImpl(aiko.Actor):
    def __init__(self, context):
        context.call_init(self, "Actor", context)
        self.share["source_file"] = f"v{_VERSION}⇒ {__file__}"

    def test(self, payload):
        self.logger.info(f"test({payload})")

# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tags = ["ec=true"]
    init_args = aiko.actor_args(_ACTOR_TYPE, protocol=_PROTOCOL, tags=tags)
    chat = aiko.compose_instance(ChatImpl, init_args)
    aiko.process.run()

# --------------------------------------------------------------------------- #
