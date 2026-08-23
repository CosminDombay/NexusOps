# Development Notes

## Workspace Path

This checkout is expected to live in WSL at:

```bash
/home/cerberus/Projects/NexusOps-project
```

From PowerShell or other Windows tooling, prefer WSL-aware commands such as:

```powershell
wsl.exe sh -lc 'cd /home/cerberus/Projects/NexusOps-project && ./scripts/start-dev.sh'
```

Do not assume the equivalent Windows path is `C:\home\cerberus\Projects\NexusOps-project`; that path may not exist because the repository is inside the WSL filesystem.

## Local Services

- Frontend dev server: `cd frontend && npm run dev`
- Backend API on Windows: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- Backend API on Linux/LXC: `.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- PostgreSQL: `docker compose -f infra/docker-compose.dev.yml up -d postgres`

Typical local startup after schema changes:

```powershell
docker compose -f infra/docker-compose.dev.yml up -d postgres
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Linux/LXC setup and startup:

```bash
./scripts/setup-env.sh
docker compose -f infra/docker-compose.dev.yml up -d postgres
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

The Bash helper can run migrations and start both dev servers in one foreground session:

```bash
./scripts/start-dev.sh
```

If the browser reports a CORS/API failure but `/api/v1/health` works, check PostgreSQL first. Database connection failures surface as `500` responses from data-backed endpoints and can look like CORS failures in the browser.

## Validation

- Frontend build and TypeScript: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Backend tests on Windows: `.venv\Scripts\python.exe -m pytest backend\tests`
- Backend tests on Linux/LXC: `.venv/bin/python -m pytest backend/tests`
- Migrations on Windows: set `DATABASE_URL`, then run `.venv\Scripts\python.exe -m alembic upgrade head`
- Migrations on Linux/LXC: set `DATABASE_URL`, then run `.venv/bin/python -m alembic upgrade head`

Use `DEBUG=false` for backend test and Alembic commands when the shell environment may contain a non-empty `DEBUG` value:

```bash
DEBUG=false .venv/bin/python -m pytest backend/tests -q
DEBUG=false .venv/bin/alembic heads
```

CI runner entrypoints:

```bash
./scripts/ci-backend.sh
./scripts/ci-frontend.sh
docker compose config --quiet
docker compose build
```

Self-hosted deployment entrypoints:

```bash
./scripts/deploy.sh
./scripts/healthcheck.sh
```

### 2026-06-21 Documentation Readiness Status

Latest documentation/readiness review from the current checkout:

- confirmed the active workspace path is `/home/cerberus/Projects/NexusOps-project`
- checked the registered backend router tree, frontend route tree, backend module surface, migrations, tests, and local demo planning files
- refreshed README pointers, API overview date/surface, development path notes, current-state review notes, architecture route notes, next-step priorities, and the local demo-use-case narrative
- no Word `.doc` or `.docx` files were present in the repository at review time
- validation after the documentation refresh:
  - `cd frontend && npm run lint`: passed
  - `cd frontend && npm run build`: passed
  - `DEBUG=false .venv/bin/python -m pytest backend/tests -q`: passed with 175 tests and one `passlib` `crypt` deprecation warning
  - `DEBUG=false .venv/bin/python -m alembic heads`: passed with single head `20260620_0042`

Because the main changes were documentation and local planning files, application behavior did not change. Repeat the validation commands before using a later code-bearing tree as a release candidate.

### 2026-06-06 Documentation Audit Status

Latest documentation/code audit from the project root:

- compared durable docs against `backend/app/api/v1/router.py`, module route decorators, runtime snapshot models, and `frontend/src/app/router.tsx`
- updated API route documentation, frontend route authorization notes, backend routing notes, runtime snapshot notes, and project review logs
- no application code changed in this pass

Because this pass changed Markdown documentation only, frontend/backend runtime tests were not rerun. Run the validation commands above before merging this with application-code changes.

### 2026-06-13 Documentation Refresh Status

Latest documentation refresh from the WSL checkout:

- refreshed the then-current workspace-path guidance, superseded by the 2026-06-21 path note above
- checked durable docs against the versioned backend router and frontend route map
- refreshed README setup notes, the API overview timestamp/context, and development workspace-path guidance
- no application code changed in this pass

Because this pass changed Markdown documentation only, frontend/backend runtime tests were not rerun. Run the validation commands above before merging this with application-code changes.

### 2026-06-04 Validation Status

Latest local validation from the project root:

- `cd frontend && npm run lint`: passed
- `cd frontend && npm run build`: passed
- `DEBUG=false .venv/bin/python -m pytest backend/tests/test_packages_profiles.py backend/tests/test_inventory.py -q`: passed with 38 focused deployment/inventory tests
- `DEBUG=false .venv/bin/python -m pytest backend/tests/test_automations.py backend/tests/test_jobs.py -q`: passed during execution credential stabilization
- `DEBUG=false .venv/bin/alembic heads`: single head `20260604_0035`

Notes:

- Use `DEBUG=false` in local validation if your shell has an unrelated `DEBUG` value.
- Full backend validation is intentionally slower than focused smoke checks; use focused suites while stabilizing a single feature, then run the full suite before broad release candidates.
- Staging validation currently runs backend, frontend, and deployment scripts from GitHub Actions/self-hosted runner workflows.

## Architecture

- Backend module routers are the canonical API surface under `backend/app/modules/*/router.py`.
- Shared API wiring belongs in `backend/app/api/v1/router.py`.
- Infrastructure boundaries live under `backend/app/adapters/` as base contracts plus provider-specific implementations.

## Security-Aware Startup

NexusOps remains local-development friendly by default, but startup now validates production configuration before the API is served.

- `ENVIRONMENT=development` allows local defaults and emits structured warnings for insecure settings.
- `ENVIRONMENT=staging` keeps the same code paths as production without forcing every production-only guardrail.
- `ENVIRONMENT=production` fails startup if `SECRET_KEY` is still `change-me`, `DEBUG=true`, `NEXUSOPS_MASTER_KEY` is missing, Proxmox TLS verification is disabled, or the bootstrap admin password looks like a default.
- `CORS_ORIGINS` accepts either comma-separated origins or JSON array syntax.
- `ENABLE_OPENAPI=false` hides Swagger/OpenAPI in production.

`SSH_TRUST_ON_FIRST_USE=true` accepts an unknown host key on first contact and pins it to the inventory record; every later connection to that host must present the same key. Set it to `false` to require an operator to approve each fingerprint before any SSH work runs.
