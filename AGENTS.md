# NexusOps Engineering Memory

## Project Type

NexusOps is a modular monolith infrastructure orchestration platform.

## Backend Stack

- FastAPI
- async SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic v2
- structlog
- httpx for provider API calls
- Paramiko for SSH execution

## Frontend Stack

- React
- TypeScript
- Vite
- TailwindCSS
- Axios
- React Router

## Architecture Rules

- Use module-level routers as the canonical API structure.
- Keep database logic out of routers.
- Use repository-service separation for database-backed modules.
- Use service-adapter separation for external infrastructure integrations.
- Preserve feature-based frontend architecture.
- Avoid duplicating adapter logic.
- Keep generated artifacts out of commits.

## Frontend Feature Structure

```text
src/features/<feature>/
  api/
  components/
  hooks/
  pages/
  types/
  utils/
```

## Adapter Structure

```text
backend/app/adapters/
  base.py
  ssh/
    base.py
    paramiko.py
  docker/
  proxmox/
```

## Current Implemented Scope

- inventory CRUD
- frontend/backend inventory integration
- PostgreSQL inventory persistence
- inventory SSH authentication metadata:
  - key authentication
  - password authentication
  - optional per-server private key path
- Proxmox infrastructure visibility
- Proxmox VM listing and status retrieval
- controlled Proxmox VM lifecycle actions:
  - start
  - stop
  - reboot
  - shutdown
- Infrastructure dashboard in the frontend
- Jobs domain:
  - persisted job history
  - SSH command execution against inventory-managed servers
  - stdout/stderr/exit code capture
  - job status lifecycle:
    - pending
    - running
    - success
    - failed
    - cancelled
- Operational actions framework:
  - predefined action registry
  - action execution through Jobs
  - diagnostics actions:
    - uptime
    - disk usage
    - memory usage
    - Docker containers
  - service actions:
    - Docker status
    - Docker restart
  - installation actions:
    - Docker Engine
    - Tailscale
    - Node Exporter
- Jobs page in the frontend:
  - inventory host selector
  - predefined action runner
  - raw command runner
  - job history
  - stdout/stderr result viewer
- ESLint, Prettier, Tailwind, and TypeScript tooling
- persistent docs under `docs/architecture/` and `docs/sprints/`

## Not Implemented Yet

- authentication
- authorization and RBAC
- VM creation
- VM deletion
- provisioning
- Terraform
- cloud-init
- Docker deployment execution
- monitoring collection
- realtime updates
- background workers
- infrastructure action audit persistence
- Proxmox task polling
- Proxmox-to-inventory sync/import
- Ansible integration
- credential vault/encrypted secret storage
- workflow chaining

## Operational Safety

- Proxmox lifecycle actions are intentionally limited to start, stop, reboot, and shutdown.
- The backend resolves VM node/type server-side before dispatching lifecycle actions.
- The backend validates VM existence and status before action dispatch.
- The frontend requires confirmation for stop, reboot, and shutdown.
- Inventory remains the orchestration abstraction layer. Jobs and operational actions execute only against inventory-managed servers, not raw Proxmox VM records.
- Operational actions must reuse the Jobs -> SSH -> persistence pipeline instead of creating standalone execution logic.
- Destructive operational actions should require frontend confirmation.
- SSH passwords and private key paths are temporary local MVP metadata; do not treat them as production-grade secret management.
- Secrets must not be committed. Proxmox token values belong in local environment variables or ignored `.env` files.
- Generated logs, screenshots, local SQLite files, and build artifacts must not be committed.

## Validation Requirements

Before finalizing substantial changes:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `.venv\Scripts\python.exe -m pytest backend\tests`
- verify Alembic migrations when database models change
- smoke-test inventory after backend changes
- smoke-test `/api/v1/proxmox/dashboard` after Proxmox changes
- smoke-test `/api/v1/jobs` and `/api/v1/jobs/actions` after Jobs/actions changes
