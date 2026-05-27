#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT=8000
FRONTEND_PORT=5173
SKIP_MIGRATIONS=false
RESET_BOOTSTRAP_ADMIN=false
NO_PROMPT=false

usage() {
  cat <<'USAGE'
Usage: scripts/start-dev.sh [options]

Options:
  --backend-port PORT       Backend port (default: 8000)
  --frontend-port PORT      Frontend port (default: 5173)
  --skip-migrations         Do not run Alembic migrations before startup
  --reset-bootstrap-admin   Reset bootstrap admin from local .env before startup
  --no-prompt               Fail instead of prompting for missing bootstrap admin values
  -h, --help                Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-port)
      BACKEND_PORT="${2:?Missing value for --backend-port}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:?Missing value for --frontend-port}"
      shift 2
      ;;
    --skip-migrations)
      SKIP_MIGRATIONS=true
      shift
      ;;
    --reset-bootstrap-admin)
      RESET_BOOTSTRAP_ADMIN=true
      shift
      ;;
    --no-prompt)
      NO_PROMPT=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
FRONTEND_DIR="$REPO_ROOT/frontend"
PYTHON="$REPO_ROOT/.venv/bin/python"

dotenv_escape() {
  local value="$1"
  value="${value//\'/\'\\\'\'}"
  printf "'%s'" "$value"
}

get_dotenv_value() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  local line value
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 0
  value="${line#*=}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

set_dotenv_value() {
  local key="$1"
  local value="$2"
  local entry
  entry="$key=$(dotenv_escape "$value")"
  touch "$ENV_FILE"
  if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE"; then
    local temp_file
    temp_file="$(mktemp)"
    awk -v key="$key" -v entry="$entry" '
      BEGIN { updated = 0 }
      $0 ~ "^[[:space:]]*" key "[[:space:]]*=" { print entry; updated = 1; next }
      { print }
      END { if (!updated) print entry }
    ' "$ENV_FILE" > "$temp_file"
    mv "$temp_file" "$ENV_FILE"
  else
    printf '%s\n' "$entry" >> "$ENV_FILE"
  fi
}

create_local_env_file() {
  cat > "$ENV_FILE" <<'ENV'
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=change-me-local-dev
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
DATABASE_URL=postgresql+asyncpg://nexusops:nexusops@localhost:5432/nexusops
NEXUSOPS_MASTER_KEY=
VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV
}

generate_fernet_key() {
  "$PYTHON" - <<'PY'
from base64 import urlsafe_b64encode
from os import urandom
print(urlsafe_b64encode(urandom(32)).decode("ascii"))
PY
}

import_dotenv() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

cd "$REPO_ROOT"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python virtual environment not found at $PYTHON. Run scripts/setup-env.sh first." >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Frontend directory not found at $FRONTEND_DIR." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating local .env file..."
  create_local_env_file
fi

if [[ -z "$(get_dotenv_value NEXUSOPS_MASTER_KEY)" ]]; then
  set_dotenv_value NEXUSOPS_MASTER_KEY "$(generate_fernet_key)"
  echo "Generated local NEXUSOPS_MASTER_KEY in .env."
fi

admin_user="$(get_dotenv_value NEXUSOPS_ADMIN_USER)"
admin_email="$(get_dotenv_value NEXUSOPS_ADMIN_EMAIL)"
admin_password="$(get_dotenv_value NEXUSOPS_ADMIN_PASSWORD)"

if [[ -z "$admin_user" || -z "$admin_email" || -z "$admin_password" ]]; then
  if [[ "$NO_PROMPT" == true ]]; then
    echo "Missing bootstrap admin settings in .env. Add NEXUSOPS_ADMIN_USER, NEXUSOPS_ADMIN_EMAIL, and NEXUSOPS_ADMIN_PASSWORD." >&2
    exit 1
  fi

  echo "Bootstrap admin settings are missing. These will be saved only in your ignored local .env file."
  if [[ -z "$admin_user" ]]; then
    read -r -p "Admin username: " admin_user
    set_dotenv_value NEXUSOPS_ADMIN_USER "$admin_user"
  fi
  if [[ -z "$admin_email" ]]; then
    read -r -p "Admin email: " admin_email
    set_dotenv_value NEXUSOPS_ADMIN_EMAIL "$admin_email"
  fi
  if [[ -z "$admin_password" ]]; then
    read -r -s -p "Admin password: " admin_password
    printf '\n'
    set_dotenv_value NEXUSOPS_ADMIN_PASSWORD "$admin_password"
  fi
fi

set_dotenv_value CORS_ORIGINS "[\"http://localhost:$FRONTEND_PORT\",\"http://127.0.0.1:$FRONTEND_PORT\"]"
set_dotenv_value VITE_API_BASE_URL "http://localhost:$BACKEND_PORT/api/v1"
import_dotenv
export VITE_API_BASE_URL="http://localhost:$BACKEND_PORT/api/v1"
export BACKEND_PORT="$BACKEND_PORT"

if [[ "$SKIP_MIGRATIONS" != true ]]; then
  echo "Running Alembic migrations..."
  "$PYTHON" -m alembic upgrade head
fi

if [[ "$RESET_BOOTSTRAP_ADMIN" == true ]]; then
  echo "Resetting bootstrap admin from local .env..."
  "$PYTHON" "$REPO_ROOT/scripts/reset_bootstrap_admin.py"
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Native Linux node/npm is required for the frontend dev server. Install Node.js/npm in the LXC container." >&2
  exit 1
fi

cleanup() {
  trap - INT TERM EXIT
  [[ -n "${backend_pid:-}" ]] && kill "$backend_pid" 2>/dev/null || true
  [[ -n "${frontend_pid:-}" ]] && kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Starting backend on http://localhost:$BACKEND_PORT"
"$PYTHON" -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
backend_pid=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT"
(cd "$FRONTEND_DIR" && VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT") &
frontend_pid=$!

echo
echo "NexusOps is starting."
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Backend:  http://localhost:$BACKEND_PORT/api/v1"
echo "Login with username '$admin_user' or email '$admin_email'."
echo "Press Ctrl+C to stop both dev servers."

wait -n "$backend_pid" "$frontend_pid"
