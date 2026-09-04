#!/usr/bin/env bash
# HelixDB dev server helper.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${HELIXDB_VENV:-$ROOT/.venv}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8123}"

if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "Creating virtualenv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi

case "${1:-serve}" in
  serve)
    exec "$VENV/bin/uvicorn" backend.main:app --host "$HOST" --port "$PORT" --reload
    ;;
  start)
    nohup "$VENV/bin/uvicorn" backend.main:app --host "$HOST" --port "$PORT" > "$ROOT/backend/data/server.log" 2>&1 &
    echo "started uvicorn on $HOST:$PORT (pid $!)"
    ;;
  stop)
    pkill -f "uvicorn backend.main:app" || echo "no server running"
    ;;
  test)
    "$VENV/bin/python" -m pytest "$ROOT/backend/tests" -q
    ;;
  *)
    echo "usage: $0 [serve|start|stop|test]"
    exit 1
    ;;
esac
