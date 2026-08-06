#!/usr/bin/env python3
#
# Aiko Chat: minimal Robot interface (a TEMPORARY seam)
#
# The ChatServer routes "robot"/"laika"/"oscar" messages to a discovered robot
# Actor, and needs exactly ONE thing from it: action(). Rather than import the
# concrete aiko_services.examples.xgo_robot.XGORobot -- which drags in the
# example's heavy cv2/numpy/Pillow dependencies and is excluded from a stock
# aiko_services install (Discussion #14) -- robot discovery goes through this
# minimal contract. get_service_proxy() builds the remote proxy from an
# interface's public method NAMES and marshals calls over MQTT, so declaring
# action() here is sufficient; the concrete example is never imported.
#
# This is a SEAM, NOT a parallel abstraction. It declares only what the
# ChatServer actually calls, and is meant to be SUBSUMED by a framework-level
# `Robot` interface in aiko_services -- Andy's flagged "composable <agent> /
# <robot> Interfaces" work. When that lands, this file is deleted and the import
# in chat_server.py becomes `from aiko_services import Robot`; because the proxy
# is name-based over the wire, only the method name has to match (the `value`
# parameter mirrors XGORobot.action(self, value) to minimise convergence).

from abc import abstractmethod

__all__ = ["Robot"]


class Robot:
    """The robot contract the ChatServer discovers against (see module doc).

    Discovery-only: aiko_services get_service_proxy() introspects this class's
    public method names to build an MQTT proxy for a remote robot Actor. It is
    never instantiated locally, so it needs no Interface.default / Actor base --
    only the method surface the ChatServer uses.
    """

    @abstractmethod
    def action(self, value):
        ...
