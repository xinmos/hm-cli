#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOG_DIR="$PROJECT_ROOT/.hermes/logs"

BACKEND_HOST="${HERMES_WEB_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${HERMES_WEB_BACKEND_PORT:-8000}"
FRONTEND_HOST="${HERMES_WEB_FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${HERMES_WEB_FRONTEND_PORT:-3000}"

BACKEND_LOG="$LOG_DIR/web-backend.log"
FRONTEND_LOG="$LOG_DIR/web-frontend.log"

BACKEND_PID=""
FRONTEND_PID=""
STOPPING=0

usage() {
    cat <<EOF
Usage: web/start-dev.sh

Starts the Hermes Web backend and frontend together.
Press Ctrl+C in this terminal to stop both services.

Environment overrides:
  HERMES_WEB_BACKEND_HOST   default: 0.0.0.0
  HERMES_WEB_BACKEND_PORT   default: 8000
  HERMES_WEB_FRONTEND_HOST  default: 0.0.0.0
  HERMES_WEB_FRONTEND_PORT  default: 3000
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

mkdir -p "$LOG_DIR"

is_port_busy() {
    local port="$1"
    lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1
}

require_free_port() {
    local port="$1"
    local label="$2"

    if is_port_busy "$port"; then
        echo "ERROR: $label port $port is already in use."
        echo "Close the existing process or set a different port with HERMES_WEB_${label}_PORT."
        exit 1
    fi
}

terminate_tree() {
    local pid="$1"
    local children child

    if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
        return
    fi

    children="$(pgrep -P "$pid" 2>/dev/null || true)"
    for child in $children; do
        terminate_tree "$child"
    done

    kill -TERM "$pid" >/dev/null 2>&1 || true
}

kill_after_grace() {
    local pid="$1"
    local children child

    if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
        return
    fi

    children="$(pgrep -P "$pid" 2>/dev/null || true)"
    for child in $children; do
        kill_after_grace "$child"
    done

    kill -KILL "$pid" >/dev/null 2>&1 || true
}

cleanup() {
    local exit_code=$?

    if [[ "$STOPPING" -eq 1 ]]; then
        exit "$exit_code"
    fi

    STOPPING=1
    echo ""
    echo "Stopping Hermes Web services..."

    terminate_tree "$FRONTEND_PID"
    terminate_tree "$BACKEND_PID"

    sleep 2

    kill_after_grace "$FRONTEND_PID"
    kill_after_grace "$BACKEND_PID"

    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true

    echo "Stopped."
    exit "$exit_code"
}

wait_for_url() {
    local url="$1"
    local label="$2"
    local attempts="${3:-30}"

    for _ in $(seq 1 "$attempts"); do
        if command -v curl >/dev/null 2>&1 && curl -fsS "$url" >/dev/null 2>&1; then
            echo "$label is ready."
            return 0
        fi
        sleep 1
    done

    echo "ERROR: $label did not become ready in time."
    return 1
}

start_backend() {
    echo "Starting backend on http://localhost:$BACKEND_PORT ..."
    (
        cd "$PROJECT_ROOT"
        exec uv run python -m uvicorn web.backend.main:app \
            --reload \
            --host "$BACKEND_HOST" \
            --port "$BACKEND_PORT"
    ) >"$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
}

ensure_frontend_dependencies() {
    if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
        return
    fi

    echo "Installing frontend dependencies..."
    (
        cd "$FRONTEND_DIR"
        npm install
    )
}

start_frontend() {
    echo "Starting frontend on http://localhost:$FRONTEND_PORT ..."
    (
        cd "$FRONTEND_DIR"
        exec npm run dev -- \
            --hostname "$FRONTEND_HOST" \
            --port "$FRONTEND_PORT"
    ) >"$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
}

monitor_children() {
    while true; do
        if [[ -n "$BACKEND_PID" ]] && ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
            echo ""
            echo "ERROR: backend exited. Last log lines:"
            tail -n 30 "$BACKEND_LOG" || true
            exit 1
        fi

        if [[ -n "$FRONTEND_PID" ]] && ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
            echo ""
            echo "ERROR: frontend exited. Last log lines:"
            tail -n 30 "$FRONTEND_LOG" || true
            exit 1
        fi

        sleep 1
    done
}

trap cleanup EXIT INT TERM

echo "Starting Hermes Web development environment..."
echo ""

require_free_port "$BACKEND_PORT" "BACKEND"
require_free_port "$FRONTEND_PORT" "FRONTEND"

start_backend
wait_for_url "http://127.0.0.1:$BACKEND_PORT/health" "Backend" 30

ensure_frontend_dependencies
start_frontend
wait_for_url "http://127.0.0.1:$FRONTEND_PORT" "Frontend" 60

echo ""
echo "Hermes Web is running."
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  API docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Logs:"
echo "  Backend:  $BACKEND_LOG"
echo "  Frontend: $FRONTEND_LOG"
echo ""
echo "Press Ctrl+C to stop both services."

monitor_children
