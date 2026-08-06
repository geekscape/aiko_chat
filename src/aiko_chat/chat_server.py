#!/usr/bin/env python3
#
# Aiko ChatServer: backend Actor (Interface and Implementation)
#
# The ChatServer is the hub: it receives send_message() calls and republishes
# each message to "{topic_path}/{channel}" over MQTT, so every subscriber on
# that channel receives it. Special recipients "llm", "robot" and "yolo" route
# to the LLM (ollama) and XGO robot integrations.
#
# NOTE: the LLM + robot handling still lives inside send_message(). Extracting
# it into chat_agent.py behind the composable <agent>/<robot> Interfaces is a
# separate, collaborative step (Andy) and is intentionally left in place here.

from abc import abstractmethod

import aiko_services as aiko

from .protocol import generate_payload, _VERSION
from .robot import Robot

__all__ = ["ChatServer", "ChatServerImpl", "get_server_service_filter"]

_HYPERSPACE_NAME = "chat_space"
_ROBOT_NAMES = ["laika", "oscar"]
_ADMIN = "andyg"

_ACTOR_SERVER = "chat_server"
_PROTOCOL_SERVER = f"{aiko.SERVICE_PROTOCOL_AIKO}/{_ACTOR_SERVER}:{_VERSION}"

# --------------------------------------------------------------------------- #

def get_server_service_filter():
    return aiko.ServiceFilter(
        "*", _ACTOR_SERVER, _PROTOCOL_SERVER, "*", "*", "*")

# --------------------------------------------------------------------------- #
# Aiko ChatServer: Interface and Implementation

class ChatServer(aiko.Actor):
    aiko.Interface.default("ChatServer", "aiko_chat.chat_server.ChatServerImpl")

    @abstractmethod
    def exit(self):
        pass

    @abstractmethod
    def send_message(self, username, recipients, message):
        pass

class ChatServerImpl(aiko.Actor):
    def __init__(self, context, llm_enabled=False):
        context.call_init(self, "Actor", context)
        self.share["llm_enabled"] = llm_enabled
        self.share["source_file"] = f"v{_VERSION}⇒ {__file__}"
        self.share["user"] = _ADMIN

        self.hyperspace = aiko.HyperSpaceImpl.create_hyperspace(
            _HYPERSPACE_NAME)
        self.channels = self.hyperspace.share["entries"]["channels"]
        self.channels_list = self.channels.share["entries"]
        self.share["channel_list"] = self.channels_list

        self.llm = None

        # Discover a robot service by the minimal `Robot` contract (see robot.py)
        # rather than importing the concrete xgo_robot example -- so `import
        # aiko_chat` needs no examples package or its heavy vision deps (Discussion
        # #14), and the chat server no longer depends on a specific robot. If no
        # robot is present, discovery simply never fires its add-handler and the
        # server runs robot-less.
        self.robot_server = None
        for name in _ROBOT_NAMES:
            service_discovery, service_discovery_handler = aiko.do_discovery(
                Robot, aiko.ServiceFilter("*", name, "*", "*", "*", "*"),
                self.discovery_add_handler, self.discovery_remove_handler)

    def discovery_add_handler(self, service_details, service):
        print(f"Connected    {service_details[1]}: {service_details[0]}")
        self.robot_server = service
        self.robot_server_topic = f"{service_details[0]}/in"

    def discovery_remove_handler(self, service_details):
        print(f"Disconnected {service_details[1]}: {service_details[0]}")
        self.robot_server = None

    def exit(self):
        aiko.process.terminate()

    def send_message(self, username, recipients, message):
        self.logger.info(f"send_message({username} > {recipients}: {message})")

        command_line = message.strip()
        if command_line:
            tokens = command_line.split(" ")
            command = tokens[0]
            if command == "/admin":
                if len(tokens) > 1:
                    self.logger.info(f"Change admin: {tokens[1]}")
                    self.share["admin"] = tokens[1]  # TODO: add EC update
                return

        for recipient in recipients:
            recipient_topic_out = f"{self.topic_path}/{recipient}"
            payload_out = generate_payload(username, recipient, message)
            aiko.process.message.publish(recipient_topic_out, payload_out)

            if recipient == "llm":
                response = "LLM is not enabled"
                if self.share["llm_enabled"]:
                    from httpx import ConnectError
                    from langchain_core.output_parsers import StrOutputParser
                    from langchain_core.prompts import ChatPromptTemplate
                    from aiko_services.examples.llm.elements import llm_load

                    message_lower = message.lower()
                    is_robot_command =  any(
                      name in message_lower for name in _ROBOT_NAMES)

                    """
  "fall":         1, "stand":           2, "crawl":      3, "circle":       4,
  "step":         5, "squat":           6, "roll":       7, "pitch":        8,
  "yaw":          9, "roll_pitch_yaw": 10, "pee":       11, "sit":         12,
  "beckon":      13, "stretch":        14, "wave":      15, "wiggle_body": 16,
  "wiggle_tail": 17, "sniff":          18, "shake_paw": 19, "arm":         20
}
                    """

                    SYSTEM_PROMPT = "Be terse"
                    if is_robot_command:
                        SYSTEM_PROMPT = """
You only output correctly formatted S-Expressions.
Never provide explanations or examples.
Think carefully about the input and choose an appropriate valid S-Expression
from the following lists ...
If the user input is in the form of a command, then valid S-Expressions are
- (action arm lower)     ;; when finished playing
- (action arm raise)     ;; when getting ready to catch a ball
- (action backwards)
- (action crawl)         ;; when herding a sheep
- (action forwards)
- (action hand close)
- (action hand open)
- (action pee)           ;; when your bladder is full
- (action pitch down)    ;; lower head downwards when things make you sad
- (action pitch up)      ;; raise head upwards when happy or excited
- (action reset)
- (action sit)           ;; sit down
- (action sniff)         ;; when food is mentioned or detected
- (action stop)          ;; stop moving
- (action stretch)       ;; stretch your muscles when you wake up
- (action turn left)
- (action turn right)
- (action wiggle_tail)   ;; shows when you are happy
If the user input query closely matches these S-Expressions function names
- (get_temperature location)  ;; location = Melbourne
For all other user input, then valid S-Expressions are
- (response YOUR REPLY) ;; YOUR REPLY maximum length is 12 words
If you don't know what to do then reply using this valid S-Expression
- (error diagnostic_message)
Never say the word"xgomini2", instead say "robot dog".
Your state information when relevant may be used in your response messages
- name: Oscar
- type: xgomini2
- goals: being happy
- interests: fetching balls
- best friend: octopus
"""
                    #   SYSTEM_PROMPT += f"- see: {detections}"

                    chat_prompt = ChatPromptTemplate.from_messages([
                        ("system", SYSTEM_PROMPT), ("user", "{input}")])
                    llm = llm_load("ollama")
                    output_parser = StrOutputParser()

                    chain = chat_prompt | llm | output_parser
                    response = chain.invoke({"input": message})  # --> str

                    if is_robot_command:
                        self.send_robot(username, "robot", response)

                aiko.process.message.publish(recipient_topic_out, response)

            if recipient == "robot":
                self.send_robot(username, recipient, message)

            if recipient == "yolo":
                pass

    def send_robot(self, username, recipient, message):
        self.logger.info(f"DEBUG({username} > {recipient}: {message})")
    #   if self.robot_server and username == self.share["user"]:
        if self.robot_server:
            sexp = message.strip()
            is_sexp = len(sexp) >= 2 and sexp[0] == "(" and sexp[-1] == ")"

            self.logger.info(f"ROBOT({username} > {recipient}: {message})")
            if is_sexp:
                aiko.process.message.publish(self.robot_server_topic, sexp)
            else:
                self.robot_server.action(message)

# --------------------------------------------------------------------------- #
