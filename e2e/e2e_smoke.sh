#!/usr/bin/env bash
#
# End-to-end smoke test: boot the REAL stack and prove a message round-trips.
#
# Starts a broker-backed ChatServer the way it is actually run (mosquitto +
# aiko_registrar + chat_start.sh, which bootstraps the channels Category), sends
# a message through the `aiko_chat send` CLI, and asserts the server republished
# it onto the channel topic. This exercises what unit tests structurally cannot:
# the stock-env import (#14), the cold-start channel bootstrap (#12), the CLI
# entry point, and the wire encode -> MQTT publish path end to end. It is the
# gate that would have caught the #10 direct-execution regression.
#
# Assumes an anonymous MQTT broker on ${AIKO_MQTT_HOST:-localhost}:1883 and that
# the aiko_chat + aiko_services console scripts are on PATH (pip install -e .).
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AIKO_MQTT_HOST:-localhost}"
export AIKO_MQTT_HOST="$HOST"
MARKER="E2E_MARKER_$$_${RANDOM}"
WORKDIR="$(mktemp -d)"
CAPTURE="$WORKDIR/capture.txt"
declare -a PIDS=()

cleanup() {
  aiko_chat exit >/dev/null 2>&1 || true
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done
}
trap cleanup EXIT

fail() {
  echo "FAIL: $1"
  echo "--- server.log ---";    tail -n 25 "$WORKDIR/server.log"    2>/dev/null
  echo "--- registrar.log ---"; tail -n 10 "$WORKDIR/registrar.log" 2>/dev/null
  echo "--- send.log ---";      tail -n 15 "$WORKDIR/send.log"      2>/dev/null
  echo "--- capture (tail) ---"; tail -n 25 "$CAPTURE"              2>/dev/null
  exit 1
}

echo "### e2e: broker reachable on $HOST:1883?"
mosquitto_sub -h "$HOST" -t '$SYS/broker/version' -C 1 -W 5 >/dev/null 2>&1 \
  || fail "no MQTT broker on $HOST:1883"

echo "### e2e: start registrar"
aiko_registrar > "$WORKDIR/registrar.log" 2>&1 &
PIDS+=($!)
sleep 2

echo "### e2e: capture all traffic"
mosquitto_sub -h "$HOST" -t '#' -v > "$CAPTURE" 2>/dev/null &
PIDS+=($!)

echo "### e2e: start ChatServer via chat_start.sh (bootstraps channels, then runs)"
( cd "$WORKDIR" && exec bash "$REPO_ROOT/src/aiko_chat/chat_start.sh" ) \
  > "$WORKDIR/server.log" 2>&1 &
PIDS+=($!)

echo "### e2e: wait for the server to be running"
for _ in $(seq 1 40); do
  grep -q "Running Chat Server" "$WORKDIR/server.log" 2>/dev/null && break
  sleep 1
done
grep -q "Running Chat Server" "$WORKDIR/server.log" 2>/dev/null \
  || fail "ChatServer never reached 'Running Chat Server'"
sleep 4  # let registration + discovery settle

echo "### e2e: send '$MARKER' to channel 'general'"
timeout 45 aiko_chat send general "$MARKER" > "$WORKDIR/send.log" 2>&1 || true

echo "### e2e: assert the marker was republished onto a channel topic"
for _ in $(seq 1 20); do
  # A republished chat message lands on a topic ending in '/general' and carries
  # the marker in its payload. The inbound send_message() lands on the server's
  # '/in' topic, so anchoring on the '/general' topic asserts the SERVER
  # republished it, not just that we published the request.
  if awk -v m="$MARKER" '$1 ~ /\/general$/ && index($0, m) {f=1} END {exit !f}' "$CAPTURE"; then
    echo "PASS: '$MARKER' republished on a /general topic -- full round-trip works"
    exit 0
  fi
  sleep 1
done

fail "marker '$MARKER' never appeared on a /general topic"
