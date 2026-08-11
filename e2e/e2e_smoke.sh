#!/usr/bin/env bash
#
# End-to-end smoke test: boot the REAL stack and prove a message round-trips.
#
# Requires an anonymous MQTT broker on ${AIKO_MQTT_HOST:-localhost}:1883, and
# the aiko_chat + aiko_services console scripts on PATH (pip install -e .).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AIKO_MQTT_HOST:-localhost}"
export AIKO_MQTT_HOST="$HOST"
MARKER="E2E_MARKER_$$_${RANDOM}"
WORKDIR="$(mktemp -d)"
CAPTURE="$WORKDIR/capture.txt"
declare -a PIDS=()

cleanup() {
  aiko_chat exit >/dev/null 2>&1 || true
  # chat_start.sh runs `aiko_chat run` as a child, so killing the script alone
  # orphans the server. `pkill -P` targets that child; a process-GROUP kill is
  # unsafe here because without job control these jobs share this script's group.
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] || continue
    pkill -P "$p" 2>/dev/null
    kill "$p" 2>/dev/null
  done
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
timeout 45 aiko_chat send general "$MARKER" > "$WORKDIR/send.log" 2>&1
SEND_RC=$?
# Do NOT gate on this: `aiko_chat send` can publish and then not self-terminate,
# so a fully successful send is reaped with rc=124. The assertion below is the
# authoritative signal.
echo "### e2e: send exit code $SEND_RC (124 = timeout after publish is expected)"

echo "### e2e: assert ChatServer republished a valid chat envelope onto /general"
for _ in $(seq 1 20); do
  # All three clauses matter: '/general$' proves the SERVER republished (our own
  # send lands on '/in'), '(message' proves a well-formed envelope, and the
  # per-run marker stops a stray message false-passing.
  if awk -v m="$MARKER" \
       '$1 ~ /\/general$/ && index($0, "(message") && index($0, m) {f=1} END {exit !f}' \
       "$CAPTURE"; then
    echo "PASS: '$MARKER' republished as a (message ...) envelope on /general -- full round-trip works"
    exit 0
  fi
  sleep 1
done

fail "marker '$MARKER' never appeared on a /general topic"
