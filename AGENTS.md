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
  docker/
  proxmox/
```

## Current Implemented Scope

- inventory CRUD
- frontend/backend inventory integration
- PostgreSQL inventory persistence
- Proxmox infrastructure visibility
- Proxmox VM listing and status retrieval
- controlled Proxmox VM lifecycle actions:
  - start
  - stop
  - reboot
  - shutdown
- Infrastructure dashboard in the frontend
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
- SSH execution
- Docker deployment execution
- monitoring collection
- realtime updates
- background workers
- infrastructure action audit persistence
- Proxmox task polling

## Operational Safety

- Proxmox lifecycle actions are intentionally limited to start, stop, reboot, and shutdown.
- The backend resolves VM node/type server-side before dispatching lifecycle actions.
- The backend validates VM existence and status before action dispatch.
- The frontend requires confirmation for stop, reboot, and shutdown.
- Secrets must not be committed. Proxmox token values belong in local environment variables or ignored `.env` files.

## Validation Requirements

Before finalizing substantial changes:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `.venv\Scripts\python.exe -m pytest backend\tests`
- verify Alembic migrations when database models change
- smoke-test inventory after backend changes
- smoke-test `/api/v1/proxmox/dashboard` after Proxmox changes
