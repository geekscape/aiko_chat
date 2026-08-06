#!/usr/bin/env python3
#
# Fake robot Actor for the e2e robot-dispatch test (e2e/e2e_robot.sh).
#
# Registers as an Aiko service named in the ChatServer's _ROBOT_NAMES (default
# "laika") so the ChatServer discovers it, and on action(value) republishes the
# value to a probe topic. That lets the test assert the ChatServer's proxy --
# built from the minimal `Robot` interface, NOT the concrete XGORobot -- actually
# dispatches action() over MQTT to a real Aiko actor. This closes the "live robot
# path unverified" gap in the robot-decoupling change (no hardware required).

import os

import aiko_services as aiko

_NAME = os.environ.get("FAKE_ROBOT_NAME", "laika")
_PROBE_TOPIC = os.environ.get("FAKE_ROBOT_PROBE_TOPIC", "e2e/robot_probe")


class FakeRobot(aiko.Actor):
    def __init__(self, context):
        context.call_init(self, "Actor", context)
        print(f"FakeRobot '{_NAME}' ready; topic_in {self.topic_in}")

    def action(self, value):
        # Observable proof that the ChatServer's Robot proxy reached us: echo the
        # received value to a fixed topic the test subscribes to.
        aiko.process.message.publish(_PROBE_TOPIC, f"ROBOT_ACTION {value}")


if __name__ == "__main__":
    aiko.compose_instance(FakeRobot, aiko.actor_args(_NAME))
    aiko.process.run()
