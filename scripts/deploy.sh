#!/usr/bin/env bash
set -euo pipefail

BUILD=true
PULL=false
CREATE_ENV=false
RUN_HEALTHCHECK=true
EXPOSE_DATABASE=false
CONFIG_ONLY=false

usage() {
  cat <<'USAGE'
Usage: scripts/deploy.sh [options]

Options:
  --no-build          Start existing images without rebuilding
  --pull              Pull newer base images before building/starting
  --create-env        Create .env from .env.example when missing
  --expose-database   Expose PostgreSQL on the host using docker-compose.db-port.yml
  --config-only       Validate the Docker Compose config and exit
  --skip-healthcheck  Do not run scripts/healthcheck.sh after deployment
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build)
      BUILD=false
      shift
      ;;
    --pull)
      PULL=true
      shift
      ;;
    --create-env)
      CREATE_ENV=true
      shift
      ;;
    --expose-database)
      EXPOSE_DATABASE=true
      shift
      ;;
    --config-only)
      CONFIG_ONLY=true
      shift
      ;;
    --skip-healthcheck)
      RUN_HEALTHCHECK=false
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

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for deployment." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$CREATE_ENV" != "true" ]]; then
    echo ".env is required for deployment. Create it first, or rerun with --create-env for local/dev stacks." >&2
    exit 1
  fi
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example. Review secrets before using this beyond local/dev."
fi

compose_env_keys=(
  COMPOSE_PROJECT_NAME
  BACKEND_PORT
  FRONTEND_PORT
  ENVIRONMENT
  DEBUG
  LOG_LEVEL
  LOG_FORMAT
  ENABLE_OPENAPI
  RATE_LIMIT_ENABLED
  API_RATE_LIMIT_PER_MINUTE
  LOGIN_RATE_LIMIT_PER_MINUTE
  WEBSOCKET_RATE_LIMIT_PER_MINUTE
  REMOTE_ACCESS_TOKEN_EXPIRE_SECONDS
  TRUSTED_PROXY_HOPS
  SECRET_KEY
  NEXUSOPS_MASTER_KEY
  NEXUSOPS_ADMIN_USER
  NEXUSOPS_ADMIN_EMAIL
  NEXUSOPS_ADMIN_PASSWORD
  ACCESS_TOKEN_EXPIRE_MINUTES
  REFRESH_TOKEN_EXPIRE_DAYS
  SESSION_INACTIVITY_TIMEOUT_MINUTES
  API_V1_PREFIX
  CORS_ORIGINS
  VITE_API_BASE_URL
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  PROXMOX_API_URL
  PROXMOX_VERIFY_SSL
  PROXMOX_TOKEN_ID
  PROXMOX_TOKEN_SECRET
  PROXMOX_TIMEOUT_SECONDS
  SSH_DEFAULT_PORT
  SSH_CONNECT_TIMEOUT_SECONDS
  SSH_COMMAND_TIMEOUT_SECONDS
  SSH_PRIVATE_KEY_PATH
  SSH_TRUST_ON_FIRST_USE
  PROMETHEUS_API_URL
  GRAFANA_BASE_URL
  LOKI_BASE_URL
  MONITORING_TIMEOUT_SECONDS
  MONITORING_VALIDATION_INTERVAL_SECONDS
  RUNTIME_REFRESH_ENABLED
  RUNTIME_REFRESH_INTERVAL_SECONDS
  RUNTIME_REFRESH_MIN_INTERVAL_SECONDS
  RUNTIME_REFRESH_CONCURRENCY
  RUNTIME_REFRESH_TIMEOUT_SECONDS
)

compose_args=(compose --env-file "$ENV_FILE")
if [[ "$EXPOSE_DATABASE" == true ]]; then
  compose_args+=(-f docker-compose.yml -f docker-compose.db-port.yml)
fi

run_compose() {
  local clean_env=(env)
  local key
  for key in "${compose_env_keys[@]}"; do
    clean_env+=("-u" "$key")
  done
  "${clean_env[@]}" docker "${compose_args[@]}" "$@"
}

run_compose config --quiet

if [[ "$CONFIG_ONLY" == true ]]; then
  exit 0
fi

if [[ "$PULL" == true ]]; then
  run_compose pull --ignore-buildable
fi

up_args=(up -d)
if [[ "$BUILD" == true ]]; then
  up_args+=(--build)
fi

run_compose "${up_args[@]}"

if [[ "$RUN_HEALTHCHECK" == true ]]; then
  "$REPO_ROOT/scripts/healthcheck.sh"
fi
