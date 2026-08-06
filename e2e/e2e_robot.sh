#!/usr/bin/env bash
#
# End-to-end robot-dispatch test: prove the ChatServer's robot proxy -- built
# from the minimal `Robot` interface (src/aiko_chat/robot.py), NOT the concrete
# xgo_robot example -- actually discovers a robot Actor and dispatches action()
# to it over MQTT. Closes the "live robot path unverified" gap from decoupling
# the robot integration, without any real hardware.
#
# Flow: broker + registrar + ChatServer (chat_start.sh) + a fake robot Actor
# named "laika". The ChatServer discovers "laika"; we send a non-S-expression
# message to recipient "robot" (which routes to robot_server.action()); the fake
# robot echoes the value to a probe topic; we assert it arrived.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AIKO_MQTT_HOST:-localhost}"
export AIKO_MQTT_HOST="$HOST"
export PYTHONUNBUFFERED=1   # so the server's + robot's print()s flush to their logs
MARKER="ROBOT_$$_${RANDOM}"
PROBE_TOPIC="e2e/robot_probe"
export FAKE_ROBOT_NAME="laika" FAKE_ROBOT_PROBE_TOPIC="$PROBE_TOPIC"
WORKDIR="$(mktemp -d)"
CAPTURE="$WORKDIR/capture.txt"
declare -a PIDS=()

cleanup() {
  aiko_chat exit >/dev/null 2>&1 || true
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] || continue
    pkill -P "$p" 2>/dev/null
    kill "$p" 2>/dev/null
  done
}
trap cleanup EXIT

fail() {
  echo "FAIL: $1"
  echo "--- server.log ---"; tail -n 25 "$WORKDIR/server.log" 2>/dev/null
  echo "--- robot.log ---";  tail -n 15 "$WORKDIR/robot.log"  2>/dev/null
  echo "--- send.log ---";   tail -n 15 "$WORKDIR/send.log"   2>/dev/null
  echo "--- capture ---";    tail -n 25 "$CAPTURE"            2>/dev/null
  exit 1
}

echo "### robot-e2e: broker reachable on $HOST:1883?"
mosquitto_sub -h "$HOST" -t '$SYS/broker/version' -C 1 -W 5 >/dev/null 2>&1 \
  || fail "no MQTT broker on $HOST:1883"

echo "### robot-e2e: start registrar"
aiko_registrar > "$WORKDIR/registrar.log" 2>&1 &
PIDS+=($!)
sleep 2

echo "### robot-e2e: capture all traffic"
mosquitto_sub -h "$HOST" -t '#' -v > "$CAPTURE" 2>/dev/null &
PIDS+=($!)

echo "### robot-e2e: start ChatServer via chat_start.sh"
( cd "$WORKDIR" && exec bash "$REPO_ROOT/src/aiko_chat/chat_start.sh" ) \
  > "$WORKDIR/server.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 40); do
  grep -q "Running Chat Server" "$WORKDIR/server.log" 2>/dev/null && break
  sleep 1
done
grep -q "Running Chat Server" "$WORKDIR/server.log" 2>/dev/null \
  || fail "ChatServer never reached 'Running Chat Server'"

echo "### robot-e2e: start fake robot 'laika'"
python "$REPO_ROOT/e2e/fake_robot.py" > "$WORKDIR/robot.log" 2>&1 &
PIDS+=($!)

echo "### robot-e2e: wait for the ChatServer to DISCOVER the robot"
for _ in $(seq 1 40); do
  grep -q "Connected" "$WORKDIR/server.log" 2>/dev/null && break
  sleep 1
done
grep -q "Connected" "$WORKDIR/server.log" 2>/dev/null \
  || fail "ChatServer never discovered the robot (Robot ServiceFilter match failed)"
sleep 2  # settle the proxy

echo "### robot-e2e: send non-S-expr '$MARKER' to recipient 'robot' (-> action())"
timeout 45 aiko_chat send robot "$MARKER" > "$WORKDIR/send.log" 2>&1
echo "### robot-e2e: send exit $? (124 = timeout after publish is expected)"

echo "### robot-e2e: assert the fake robot's action() actually fired"
for _ in $(seq 1 20); do
  # The fake robot echoes 'ROBOT_ACTION <value>' to PROBE_TOPIC only when its
  # action() is invoked -- so a match proves the ChatServer's Robot-interface
  # proxy dispatched action() over MQTT to a real discovered Actor.
  if awk -v t="$PROBE_TOPIC" -v m="$MARKER" \
       '$1 == t && index($0, "ROBOT_ACTION") && index($0, m) {f=1} END {exit !f}' \
       "$CAPTURE"; then
    echo "PASS: Robot proxy dispatched action('$MARKER') to a real actor -- decoupling verified"
    exit 0
  fi
  sleep 1
done

fail "fake robot action() never fired for '$MARKER' -- the Robot-interface proxy did not dispatch"
