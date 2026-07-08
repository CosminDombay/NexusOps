#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
POSTGRES_DB="${POSTGRES_DB:-nexusops}"
POSTGRES_USER="${POSTGRES_USER:-nexusops}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-nexusops}"
SKIP_TESTS=false
NO_START=false

usage() {
  cat <<'USAGE'
Usage: ./setup.sh [options]

Deploy NexusOps locally with a native PostgreSQL service.

Options:
  --backend-port PORT       Backend port (default: 8000)
  --frontend-port PORT      Frontend port (default: 5173)
  --db-name NAME            PostgreSQL database name (default: nexusops)
  --db-user USER            PostgreSQL user name (default: nexusops)
  --db-password PASSWORD    PostgreSQL user password (default: nexusops)
  --skip-tests              Skip backend/frontend tests before deployment
  --no-start                Prepare database, env, dependencies, and migrations without starting servers
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
    --db-name)
      POSTGRES_DB="${2:?Missing value for --db-name}"
      shift 2
      ;;
    --db-user)
      POSTGRES_USER="${2:?Missing value for --db-user}"
      shift 2
      ;;
    --db-password)
      POSTGRES_PASSWORD="${2:?Missing value for --db-password}"
      shift 2
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --no-start)
      NO_START=true
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
REPO_ROOT="$SCRIPT_DIR"
REPORT_DIR="$REPO_ROOT/deployment-reports"
REPORT_FILE="$REPORT_DIR/local-$(date +%Y%m%d-%H%M%S).log"
ENV_FILE="$REPO_ROOT/.env"
PYTHON="$REPO_ROOT/.venv/bin/python"

mkdir -p "$REPORT_DIR"
exec > >(tee -a "$REPORT_FILE") 2>&1

finish() {
  local status=$?
  if [[ $status -eq 0 ]]; then
    echo "Deployment script completed successfully."
  else
    echo "Deployment script failed with exit code $status."
  fi
  echo "Report: $REPORT_FILE"
}
trap finish EXIT

validate_identifier() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "$label must be a PostgreSQL-safe identifier: $value" >&2
    exit 1
  fi
}

dotenv_escape() {
  local value="$1"
  value="${value//\'/\'\\\'\'}"
  printf "'%s'" "$value"
}

set_dotenv_value() {
  local key="$1"
  local value="$2"
  local entry temp_file
  entry="$key=$(dotenv_escape "$value")"
  touch "$ENV_FILE"
  if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE"; then
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

sql_literal() {
  python3 - "$1" <<'PY'
from sys import argv

print("'" + argv[1].replace("'", "''") + "'")
PY
}

database_url() {
  python3 - "$POSTGRES_USER" "$POSTGRES_PASSWORD" "$POSTGRES_DB" <<'PY'
from sys import argv
from urllib.parse import quote

user, password, database = argv[1:]
print(
    "postgresql+asyncpg://"
    f"{quote(user, safe='')}:{quote(password, safe='')}@localhost:5432/{quote(database, safe='')}"
)
PY
}

postgres_psql() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -u postgres psql "$@"
  else
    psql -U postgres "$@"
  fi
}

postgres_createdb() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -u postgres createdb "$@"
  else
    createdb -U postgres "$@"
  fi
}

install_postgres_if_needed() {
  if command -v psql >/dev/null 2>&1 && command -v pg_isready >/dev/null 2>&1; then
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "PostgreSQL client/server tools not found. Installing PostgreSQL with apt-get..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-client
    return
  fi

  echo "PostgreSQL is required. Install PostgreSQL 16 or newer, then rerun this script." >&2
  exit 1
}

start_postgres_service() {
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable --now postgresql || true
  fi
  if command -v service >/dev/null 2>&1; then
    sudo service postgresql start || true
  fi
}

configure_database() {
  local escaped_password
  escaped_password="$(sql_literal "$POSTGRES_PASSWORD")"

  echo "Configuring PostgreSQL database '$POSTGRES_DB' and user '$POSTGRES_USER'..."
  if [[ "$(postgres_psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$POSTGRES_USER'" || true)" != "1" ]]; then
    postgres_psql -v ON_ERROR_STOP=1 -c "CREATE ROLE \"$POSTGRES_USER\" LOGIN PASSWORD $escaped_password"
  else
    postgres_psql -v ON_ERROR_STOP=1 -c "ALTER ROLE \"$POSTGRES_USER\" WITH LOGIN PASSWORD $escaped_password"
  fi

  if [[ "$(postgres_psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'" || true)" != "1" ]]; then
    postgres_createdb -O "$POSTGRES_USER" "$POSTGRES_DB"
  fi

  postgres_psql -v ON_ERROR_STOP=1 -d "$POSTGRES_DB" -c "GRANT ALL PRIVILEGES ON DATABASE \"$POSTGRES_DB\" TO \"$POSTGRES_USER\""
}

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
}

cd "$REPO_ROOT"

validate_identifier "Database name" "$POSTGRES_DB"
validate_identifier "Database user" "$POSTGRES_USER"

echo "NexusOps native local deployment"
echo "Started: $(date -Is)"
echo "Report: $REPORT_FILE"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.12 or newer, then rerun this script." >&2
  exit 1
fi

run_step "Install/verify PostgreSQL" install_postgres_if_needed
run_step "Start PostgreSQL service" start_postgres_service
run_step "Create/update PostgreSQL role and database" configure_database

run_step "Install backend/frontend dependencies and prepare .env" "$REPO_ROOT/scripts/setup-env.sh"
DATABASE_URL="$(database_url)"
set_dotenv_value POSTGRES_DB "$POSTGRES_DB"
set_dotenv_value POSTGRES_USER "$POSTGRES_USER"
set_dotenv_value POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
set_dotenv_value DATABASE_URL "$DATABASE_URL"
set_dotenv_value CORS_ORIGINS "[\"http://localhost:$FRONTEND_PORT\",\"http://127.0.0.1:$FRONTEND_PORT\"]"
set_dotenv_value VITE_API_BASE_URL "http://localhost:$BACKEND_PORT/api/v1"

if [[ "$SKIP_TESTS" != true ]]; then
  run_step "Run backend tests, Alembic head check, and artifact hygiene" "$REPO_ROOT/scripts/ci-backend.sh"
  run_step "Run frontend lint and production build" "$REPO_ROOT/scripts/ci-frontend.sh"
else
  echo "Skipping tests by request."
fi

run_step "Apply database migrations" env DEBUG=false DATABASE_URL="$DATABASE_URL" "$PYTHON" -m alembic upgrade head

if [[ "$NO_START" == true ]]; then
  echo "Preparation complete. Start later with: ./scripts/start-dev.sh --backend-port $BACKEND_PORT --frontend-port $FRONTEND_PORT"
  exit 0
fi

echo
echo "Starting NexusOps locally."
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Backend:  http://localhost:$BACKEND_PORT/api/v1"
exec "$REPO_ROOT/scripts/start-dev.sh" --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --no-prompt
