# NexusOps Current State

## Implementation Status

NexusOps is currently a modular monolith with a FastAPI backend, a React/Vite frontend, PostgreSQL persistence, and a validated first workflow for server inventory. The platform also includes Proxmox infrastructure visibility and controlled VM lifecycle actions.

The implemented system is focused on foundations, visibility, and narrowly scoped VM lifecycle control. It does not yet perform VM creation, VM deletion, provisioning, SSH execution, Docker deployment, monitoring collection, or authentication.

## Working Functionality

- Backend API startup through FastAPI.
- Versioned API routing under `/api/v1`.
- Health endpoint.
- Server inventory CRUD:
  - list servers
  - get server
  - create server
  - update server
  - delete server
  - filter/search server inventory
- PostgreSQL-backed persistence through async SQLAlchemy.
- Alembic migration for the `servers` table.
- React inventory dashboard with create form, responsive server list, loading states, and error handling.
- Shared Axios API client using `VITE_API_BASE_URL`.
- Proxmox integration:
  - node discovery
  - VM/container discovery
  - VM status lookup
  - cluster summary
  - frontend infrastructure dashboard
  - controlled VM start, stop, reboot, and shutdown actions
- ESLint 9 flat configuration, TypeScript build, TailwindCSS, and Prettier configuration.

## Completed Phases

### Foundation

The project scaffold established the backend/frontend split, modular monolith layout, local development infrastructure, shared configuration, structured logging, and adapter boundaries.

### Inventory Workflow

Inventory became the first complete frontend-to-backend workflow. It validated the main architecture path:

```text
React page -> feature API client -> FastAPI router -> service -> repository -> async SQLAlchemy -> PostgreSQL
```

### Stabilization

Tooling and architecture cleanup normalized frontend linting, removed duplicate placeholder route files, consolidated adapter interfaces, cleaned generated artifacts, and documented development commands.

### Proxmox Visibility

The Proxmox integration validates the adapter architecture against a real infrastructure provider. It retrieves infrastructure state from Proxmox and renders nodes, VMs, and summary metrics in the frontend.

### Controlled VM Lifecycle Actions

The infrastructure dashboard now exposes guarded VM lifecycle controls for start, stop, reboot, and shutdown. The backend validates VM existence and current state before dispatching Proxmox actions, and the frontend provides confirmation prompts, per-VM action loading state, and success/error feedback.

## Architecture Status

- Backend remains organized as a modular monolith.
- Module routers are the canonical API source.
- Inventory uses repository-service separation.
- Proxmox uses service-adapter separation because it talks to an external API rather than local persistence.
- Adapter packages are canonicalized under `backend/app/adapters/`.
- Frontend is feature-based under `frontend/src/features/`.
- Shared shell, routing, API client, and layout code remain outside feature folders.

## Current Technical Debt

- Non-inventory backend modules are still placeholders.
- Authentication and authorization are not implemented.
- No frontend test framework is configured yet.
- No CI pipeline is defined in the repo.
- Inventory tests use SQLite fixtures; PostgreSQL migration behavior is validated manually, not in automated CI.
- Proxmox live validation depends on local environment variables and a reachable Proxmox host.
- Proxmox credentials are intentionally not persisted in source-controlled files.
- Proxmox lifecycle actions currently return accepted task IDs but do not poll task completion.
- Infrastructure action audit persistence is not implemented yet.
- Existing `docs/architecture.md` is older and less precise than the newer files in `docs/architecture/`.

## Current Safety Boundary

The platform can mutate NexusOps-owned inventory data and can request controlled Proxmox VM lifecycle actions. It does not expose VM creation, deletion, provisioning, SSH execution, Docker deployment, or arbitrary infrastructure mutation.
