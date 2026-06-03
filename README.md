# NexusOps

NexusOps is a centralized infrastructure orchestration and automation platform for Linux environments.

This repository is scaffolded as a modular monolith:

- `backend/` contains the FastAPI application, domain modules, repositories, services, adapters, jobs, and database setup.
- `frontend/` contains the React/Vite/TypeScript application organized by features.
- `infra/` contains local development infrastructure such as Docker Compose and database initialization scripts.

The current implementation includes the platform foundation, CMDB-style inventory CRUD,
Proxmox visibility/lifecycle control, template-based VM provisioning with NexusOps provisioning blueprints,
Proxmox-to-inventory synchronization, SSH-backed job execution, reusable operational actions, package definitions,
infrastructure profiles, editable operational templates, credential-backed secret injection, Docker Compose deployments,
Linux identity orchestration, remote shell/file access, runtime diagnostics, simple variable-driven execution, and
production-aware security guardrails.

The latest preparation review is documented in `docs/project-review-2026-05-27-prep.md`.

## MVP Domains

- VM provisioning through Proxmox API
- Proxmox template cloning with cloud-init configuration
- NexusOps provisioning blueprints for reusable VM defaults
- Static IP provisioning and inventory auto-registration
- Server inventory management
- Credential Manager for reusable SSH accounts, API tokens, and environment secrets
- Proxmox discovery-to-inventory import
- Managed/unmanaged/orphaned inventory reconciliation
- SSH-based remote execution
- Operational action execution through Jobs
- Package definition catalog
- Editable built-in package templates with clone and reset-to-default workflows
- Reusable infrastructure profiles
- Editable built-in profile templates with clone, step ordering, and reset-to-default workflows
- Simple `{{ variable_name }}` parameterization for package/profile execution
- Credential-backed sensitive package/profile variables with redacted job history
- Variable Manager foundations for reusable runtime values
- Integration records for provider and monitoring connection settings
- SSH-backed Docker Compose deployment workflows
- Credential-backed deployment environment variables
- Package installation automation
- Snapshot-backed monitoring validation with Prometheus/Grafana provider links
- Linux identity orchestration and replication
- guided access profiles for Linux identity operations
- distro-aware administrator group abstraction
- built-in operational group and permission presets
- User/group standardization profiles
- Job execution tracking and logging
- Runtime status/log diagnostics for Jobs, Deployments, Workflows, Identity, and scheduler-driven refreshes
- Local ignored `backlog.md` workflow for manual stabilization findings and test status tracking

## Quick Start With Docker

Copy the example environment file and set a local admin password:

```bash
cp .env.example .env
```

Then start the full stack:

```bash
docker compose up --build
```

On Windows PowerShell, you can use:

```powershell
.\scripts\start-docker.ps1 -Build
```

On Linux or a Proxmox LXC container, use the Bash wrapper:

```bash
./scripts/start-docker.sh --build
```

The full Docker stack includes:

- PostgreSQL
- FastAPI backend
- React frontend served by Nginx
- automatic Alembic migrations before backend startup
- frontend `/api` proxy to the backend

PostgreSQL is available only inside the Docker network by default, so it does not collide with a local Postgres service on port `5432`. If you need to expose the Docker database to your host machine, start with:

```bash
docker compose -f docker-compose.yml -f docker-compose.db-port.yml up --build
```

Frontend will be available at `http://localhost:5173`.
Backend API docs will be available at `http://localhost:8000/docs`.
In production, set `ENABLE_OPENAPI=false` if you do not want Swagger/OpenAPI exposed.

Stop the Docker stack with:

```bash
docker compose down
```

or:

```powershell
.\scripts\stop-docker.ps1
```

On Linux:

```bash
./scripts/stop-docker.sh
```

For a fuller deployment checklist, including Docker versus on-prem LXC guidance and a controlled container update flow, see `docs/deployment.md`.
For a compact API overview, see `docs/api.md`.
For current architecture and stabilization status, see `docs/architecture/current-state.md`.

## Local Dev Server Quick Start

For hot-reload local development without fully containerizing the app:

```powershell
.\scripts\start-dev.ps1
```

On Linux or a Proxmox LXC container:

```bash
./scripts/setup-env.sh
./scripts/start-dev.sh
```

The older development Compose file is still available:

```bash
docker compose -f infra/docker-compose.dev.yml up --build
```

## CI and Deployment Scripts

GitHub Actions and local runner checks should call the reusable Bash scripts:

```bash
./scripts/ci-backend.sh
./scripts/ci-frontend.sh
docker compose config --quiet
docker compose build
```

For a self-hosted runner deployment job on the LXC host:

```bash
./scripts/deploy.sh
./scripts/healthcheck.sh
```

## Implemented Workflows

- Inventory records define managed execution targets.
- Inventory is the orchestration source of truth and tracks provider linkage, lifecycle state, synchronization state, and SSH execution metadata.
- Proxmox integration discovers nodes, VMs/containers, cluster summary data, import status, and supports guarded VM lifecycle actions.
- Discovered Proxmox assets can be imported into Inventory, but NexusOps does not blindly auto-import every VM.
- Provisioning clones cloud-init-capable Proxmox templates, configures static networking, starts VMs, waits for SSH, and registers inventory records.
- Provisioning blueprints save repeatable defaults such as Proxmox template, node, sizing, disks, bridge, gateway, DNS, environment, tags, default username, and bootstrap selections. Per-machine values such as VM name, VMID, hostname, and static IP remain editable every run.
- Provisioning supports a root disk plus optional additional disks.
- Jobs execute SSH commands against inventory targets and persist status, stdout, stderr, exit code, timestamps, correlation IDs, activity events, and redacted command history.
- Jobs resolve node credentials and execution credential references server-side. Sensitive values are never returned to the frontend, and commands persisted to job history are redacted when runtime secrets are injected.
- Jobs now persist immutable execution intent metadata, including command hash, command policy result, initiator metadata, correlation ID, and append-only execution events for future runtime expansion.
- Inventory health checks perform lightweight TCP reachability checks against SSH ports without logging in on each refresh.
- Runtime refresh runs conservatively in the backend after login and on a scheduler, updating inventory reachability and Docker deployment state so frontend pages can poll normalized state without direct infrastructure checks.
- Backend logs default to human-readable output such as `INFO - timestamp : message | key=value`, while JSON logging remains available with `LOG_FORMAT=json`.
- Credential records store reusable secret material encrypted with Fernet using `NEXUSOPS_MASTER_KEY`. API responses expose only masked secret status.
- Production startup fails if required security settings are unsafe, including default `SECRET_KEY`, missing `NEXUSOPS_MASTER_KEY`, disabled Proxmox TLS verification, `DEBUG=true`, or default-looking bootstrap admin credentials.
- Inventory records can reference a shared `credential_id` for SSH execution while retaining inline SSH metadata for backward-compatible local MVP use.
- Operational actions provide predefined workflows such as uptime, disk usage, memory usage, Docker checks, Docker restart, and simple installation actions.
- Package definitions describe reusable install/validation commands for common infrastructure packages and can be extended with custom definitions.
- Built-in package definitions can be edited as persisted working copies, cloned into custom templates, or restored to the system default.
- Package variables use simple `{{ variable_name }}` placeholders and are resolved before execution from defaults, runtime inputs, and credential references for sensitive values.
- Infrastructure profiles orchestrate ordered package/action/command workflows through Jobs and can be built from built-in or custom structured steps.
- Built-in profiles can be edited as persisted working copies, cloned into user-managed templates, reordered, or restored to the system default.
- Integration records provide a central place to store and test provider/monitoring connection metadata while runtime adapters still primarily use local environment configuration.
- Docker Compose deployments store compose/env definitions and execute deploy/redeploy/restart/stop/status/logs through the Jobs -> SSH pipeline. Deployment-specific credential references are resolved server-side into `.env` at runtime and redacted from persisted job command history.
- Remote shell access uses short-lived, one-time, server-scoped remote-access tokens instead of sending the long-lived auth JWT through the WebSocket URL.
- SSH connections use a trust-on-first-use fingerprint foundation for remote access and reject later host-key mismatches.
- Monitoring stores lightweight validation snapshots for managed Inventory nodes, checks node_exporter, promtail, and cAdvisor availability, validates Prometheus as provider-level infrastructure, and links operators to Grafana when configured.
- Identity orchestration stores Linux users, groups, SSH public keys, and permission templates, then replicates user/group/access/permission changes across selected Inventory-managed hosts through Jobs and SSH.
- Identity includes guided access profiles such as Administrator, Deployment Operator, Docker Operator, Log Viewer, Read Only, and Service Account. These profiles configure shell, sudo behavior, recommended groups, and defaults while preserving advanced Linux controls.
- Identity resolves administrator access through a distro-aware abstraction, using `sudo` on Debian/Ubuntu style hosts and `wheel` on RHEL/CentOS/Fedora style hosts during replicated execution.
- Identity user/group discovery can adopt discovered objects into managed records, show host-origin context, pass selected password/SSH-password credentials into sudo-backed replication, and keep local create/adopt separate from remote sync target selection.
- Permission workflows include presets and a human-friendly read/write/execute matrix that generates octal modes while retaining advanced raw mode controls.

Current orchestration flow:

```text
Provisioning blueprint -> Proxmox template/cloud-init -> Inventory -> Profiles / Packages / Actions -> Jobs -> SSH adapter -> managed Linux host
```

Proxmox remains a provider/discovery layer. Inventory deletion or archival does
not destroy provider infrastructure. Remote execution intentionally runs through
Inventory-managed targets. Identity is Linux access orchestration and replication,
not centralized authentication; NexusOps does not implement LDAP, Kerberos,
FreeIPA, Active Directory, or SSSD.
