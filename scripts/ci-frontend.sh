#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"

cd "$FRONTEND_DIR"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Native Linux node/npm is required for frontend CI." >&2
  exit 1
fi

if [[ "${SKIP_NPM_CI:-false}" != "true" ]]; then
  npm ci
fi

npm run lint
npm run build
