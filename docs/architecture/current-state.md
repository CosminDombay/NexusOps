# NexusOps Current State

## Implementation Status

NexusOps is currently a modular monolith with a FastAPI backend, a React/Vite frontend, PostgreSQL persistence, and a validated first workflow for server inventory. The platform also includes Proxmox infrastructure visibility, controlled VM lifecycle actions, Proxmox template provisioning, SSH-backed job execution, reusable operational actions, package definitions, and infrastructure profiles.

The implemented system is focused on foundations, visibility, narrowly scoped VM lifecycle control, and the first orchestration layer. It does not yet perform VM creation, VM deletion, provisioning, Docker deployment, monitoring collection, authentication, or workflow chaining.

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
- Alembic migrations for inventory, jobs, and SSH authentication metadata.
- React inventory dashboard with create form, responsive server list, loading states, and error handling.
- Inventory SSH authentication metadata:
  - key authentication
  - password authentication
  - optional private key path
- Shared Axios API client using `VITE_API_BASE_URL`.
- Proxmox integration:
  - node discovery
  - VM/container discovery
  - VM status lookup
  - cluster summary
  - frontend infrastructure dashboard
  - controlled VM start, stop, reboot, and shutdown actions
- Provisioning:
  - Proxmox template selection
  - full clone from cloud-init-capable templates
  - cloud-init username/password/SSH key configuration
  - static IP/CIDR, gateway, DNS configuration
  - Proxmox task polling
  - SSH readiness polling
  - inventory auto-registration
  - optional profile/package bootstrap through Jobs
  - provisioning lifecycle history
- Jobs and orchestration:
  - execute SSH commands against inventory-managed servers
  - persist command, status, stdout, stderr, exit code, and timestamps
  - support key-based and password-based SSH authentication
  - expose reusable operational actions backed by the jobs pipeline
  - frontend Jobs page with action runner, raw command runner, history, and result viewer
- Package definitions:
  - Docker Engine
  - Tailscale
  - Node Exporter
  - Promtail
  - Fail2Ban
  - UFW
  - custom create/update/delete support
  - direct package execution through Jobs
- Infrastructure profiles:
  - Base Linux Server
  - Docker Host
  - Monitoring Node
  - Development VM
  - sequential execution through Jobs
  - custom create/update/delete support
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

### Jobs, SSH Execution, and Operational Actions

Jobs established the first orchestration backbone:

```text
Inventory -> Jobs -> SSH adapter -> managed Linux host
```

Inventory remains the source of managed execution targets. Jobs persist every command execution and operational action result. Operational actions provide reusable workflows such as uptime checks, disk and memory diagnostics, Docker status/restart, and simple installation commands while reusing the Jobs execution path.

### Package Definitions and Profiles

Package definitions describe reusable install and validation commands. Built-in package definitions provide starter standards, and custom definitions can be created for local workflows. Profiles compose ordered package/action steps and apply them to inventory-managed hosts through the Jobs pipeline:

```text
Profile -> Package/Action step -> Job -> SSH adapter -> managed Linux host
```

Profile execution is synchronous and sequential for the MVP. Each step creates a persisted job. Profiles can be built from built-in actions, built-in packages, and custom package definitions.

### Proxmox Template Provisioning

Provisioning uses only Proxmox VM templates and cloud-init customization:

```text
Provisioning request -> Proxmox clone/config/start -> SSH readiness -> Inventory registration -> optional bootstrap Jobs
```

Provisioned VMs become Inventory records before any bootstrap profile/package execution. This preserves Inventory as the orchestration source of truth.

## Architecture Status

- Backend remains organized as a modular monolith.
- Module routers are the canonical API source.
- Inventory uses repository-service separation.
- Jobs use repository-service separation and reuse inventory targets for execution.
- Proxmox uses service-adapter separation because it talks to an external API rather than local persistence.
- Operational actions are a lightweight registry in the Jobs module and execute through the existing Jobs service.
- Package definitions and profiles combine built-in registries with persisted custom definitions and reuse Jobs for execution.
- Provisioning orchestrates Proxmox, Inventory, and bootstrap Jobs without creating a separate execution path.
- Adapter packages are canonicalized under `backend/app/adapters/`.
- SSH has a concrete Paramiko adapter for key/password command execution.
- Frontend is feature-based under `frontend/src/features/`.
- Shared shell, routing, API client, and layout code remain outside feature folders.

## Current Technical Debt

- Provisioning, deployments, monitoring, and execution modules are still placeholders.
- Authentication and authorization are not implemented.
- SSH passwords/private key paths are stored as a temporary local MVP, not encrypted or vault-backed.
- No frontend test framework is configured yet.
- No CI pipeline is defined in the repo.
- Inventory tests use SQLite fixtures; PostgreSQL migration behavior is validated manually, not in automated CI.
- Proxmox live validation depends on local environment variables and a reachable Proxmox host.
- Proxmox credentials are intentionally not persisted in source-controlled files.
- Proxmox lifecycle actions currently return accepted task IDs but do not poll task completion.
- Proxmox lifecycle action audit persistence is not implemented yet.
- Jobs run synchronously during the API request; no Celery/Redis/background worker exists yet.
- Profiles run synchronously and sequentially; no DAG engine, rollback, or workflow scheduler exists yet.
- Provisioning runs synchronously in the API request; no background worker or websocket status streaming exists yet.
- Existing `docs/architecture.md` is older and less precise than the newer files in `docs/architecture/`.

## Current Safety Boundary

The platform can mutate NexusOps-owned inventory data, request controlled Proxmox VM lifecycle actions, provision VMs from Proxmox templates, and execute commands/actions against inventory-managed Linux hosts over SSH. It does not expose VM deletion, ISO installation, Docker Compose deployment workflows, monitoring ingestion, or arbitrary provider-side infrastructure mutation.
