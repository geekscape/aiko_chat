#!/usr/bin/env python3
#
# Fake robot Actor for e2e/e2e_robot.sh.
#
# Registers under a name in the ChatServer's _ROBOT_NAMES so discovery matches.

import os

import aiko_services as aiko

_NAME = os.environ.get("FAKE_ROBOT_NAME", "laika")
_PROBE_TOPIC = os.environ.get("FAKE_ROBOT_PROBE_TOPIC", "e2e/robot_probe")


class FakeRobot(aiko.Actor):
    def __init__(self, context):
        context.call_init(self, "Actor", context)
        print(f"FakeRobot '{_NAME}' ready; topic_in {self.topic_in}")

    def action(self, value):
        # Observable proof the proxy reached us; the test subscribes to this.
        aiko.process.message.publish(_PROBE_TOPIC, f"ROBOT_ACTION {value}")


if __name__ == "__main__":
    aiko.compose_instance(FakeRobot, aiko.actor_args(_NAME))
    aiko.process.run()
