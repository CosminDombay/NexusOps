#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8000/api/v1/health}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
SLEEP_SECONDS="${SLEEP_SECONDS:-3}"

deadline=$((SECONDS + TIMEOUT_SECONDS))

wait_for_http() {
  local name="$1"
  local url="$2"

  echo "Waiting for $name at $url"
  while (( SECONDS < deadline )); do
    if curl -fsS "$url" >/dev/null; then
      echo "$name is healthy."
      return 0
    fi
    sleep "$SLEEP_SECONDS"
  done

  echo "$name did not become healthy within ${TIMEOUT_SECONDS}s: $url" >&2
  return 1
}

wait_for_http "backend" "$BACKEND_URL"
wait_for_http "frontend" "$FRONTEND_URL"

if command -v docker >/dev/null 2>&1 && docker compose ps >/dev/null 2>&1; then
  docker compose ps
fi
