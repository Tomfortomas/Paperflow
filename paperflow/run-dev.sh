#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
INSTALL_DEPS=0

usage() {
  cat <<EOF
PaperFlow unified dev runner

Usage:
  ./run-dev.sh [--install]

Environment:
  BACKEND_HOST     default: 127.0.0.1
  BACKEND_PORT     default: 8000
  FRONTEND_HOST    default: 127.0.0.1
  FRONTEND_PORT    default: 5173
  PAPERFLOW_DATA_DIR optional override; default is ../data

Examples:
  ./run-dev.sh
  ./run-dev.sh --install
  BACKEND_PORT=8010 FRONTEND_PORT=5174 ./run-dev.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      INSTALL_DEPS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log() {
  printf '\033[1;34m[paperflow]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[paperflow]\033[0m %s\n' "$*" >&2
  exit 1
}

ensure_backend() {
  if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
    if [[ "$INSTALL_DEPS" -ne 1 ]]; then
      fail "Backend venv missing. Run './run-dev.sh --install' first."
    fi
    log "Creating backend virtualenv"
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.venv/bin/activate"
  if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    log "Installing backend dependencies"
    python -m pip install -e "$BACKEND_DIR[dev]"
  fi
  if ! command -v uvicorn >/dev/null 2>&1; then
    fail "uvicorn is not installed in backend venv. Run './run-dev.sh --install'."
  fi
  deactivate || true
}

ensure_frontend() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    if [[ "$INSTALL_DEPS" -ne 1 ]]; then
      fail "Frontend node_modules missing. Run './run-dev.sh --install' first."
    fi
    log "Installing frontend dependencies"
    (cd "$FRONTEND_DIR" && npm install)
  elif [[ "$INSTALL_DEPS" -eq 1 ]]; then
    log "Refreshing frontend dependencies"
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

backend_pid=""
frontend_pid=""

cleanup() {
  local exit_code=$?
  trap - INT TERM EXIT
  if [[ -n "${frontend_pid:-}" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" 2>/dev/null || true
  fi
  if [[ -n "${backend_pid:-}" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
  fi
  wait "$frontend_pid" "$backend_pid" 2>/dev/null || true
  exit "$exit_code"
}

trap cleanup INT TERM EXIT

ensure_backend
ensure_frontend

log "Starting backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export PAPERFLOW_DATA_DIR="${PAPERFLOW_DATA_DIR:-$ROOT_DIR/../data}"
  exec uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
) &
backend_pid=$!

log "Starting frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$FRONTEND_DIR"
  export VITE_PAPERFLOW_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
  exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
frontend_pid=$!

cat <<EOF

PaperFlow is starting.
  Backend:  http://${BACKEND_HOST}:${BACKEND_PORT}
  Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}

Press Ctrl+C to stop both processes.
EOF

while true; do
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    fail "Backend process exited. Stopping frontend."
  fi
  if ! kill -0 "$frontend_pid" 2>/dev/null; then
    fail "Frontend process exited. Stopping backend."
  fi
  sleep 1
done
