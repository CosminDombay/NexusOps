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

- local platform authentication:
  - username/email password login
  - JWT access and refresh tokens
  - token-version session revocation
  - admin/operator/viewer RBAC dependencies
  - admin user lifecycle page and APIs
- inventory CRUD
- frontend/backend inventory integration
- PostgreSQL inventory persistence
- managed-node inventory lifecycle:
  - VM, LXC, physical host, and hypervisor node types
  - managed/unmanaged/retired state
  - discovered/imported/provisioned/archived/decommissioned lifecycle states
  - provider linkage and synchronization metadata
- inventory SSH authentication metadata:
  - key authentication
  - password authentication
  - optional per-server private key path
  - optional shared credential reference
- Credential Manager:
  - encrypted passwords, SSH passwords, SSH keys, API tokens, and environment secrets
  - Fernet encryption through `NEXUSOPS_MASTER_KEY`
  - masked API responses
- Proxmox infrastructure visibility
- Proxmox hypervisor, VM, and LXC discovery
- Proxmox inventory import, synchronization, reconciliation, archive, and decommission flows
- controlled Proxmox guest lifecycle actions:
  - start
  - stop
  - reboot
  - shutdown
- LXC lifecycle foundations:
  - start
  - stop
  - restart
  - shutdown
  - archive/delete path
- Proxmox template-based VM provisioning:
  - template listing
  - clone from cloud-init capable template
  - cloud-init identity/SSH/static network configuration
  - Proxmox task polling
  - SSH readiness polling
  - inventory auto-registration
  - optional profile/package bootstrap through Jobs
- Proxmox LXC provisioning foundations:
  - container template discovery
  - CTID/node/storage/network inputs
  - inventory registration
  - optional bootstrap through Jobs/Profile/Package paths
- provisioning blueprints and batch provisioning
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
- Package definitions:
  - Docker Engine
  - Tailscale
  - Node Exporter
  - Promtail
  - Fail2Ban
  - UFW
  - custom package create/update/delete
  - editable built-in package working copies
  - package clone workflow
  - built-in package reset-to-default workflow
  - package variable definitions and execution-time variable injection
  - package execution through Jobs
- Infrastructure profiles:
  - Base Linux Server
  - Docker Host
  - Monitoring Node
  - Development VM
  - sequential package/action execution through Jobs
  - custom profile create/update/delete
  - editable built-in profile working copies
  - profile clone workflow
  - built-in profile reset-to-default workflow
  - profile variable definitions and execution-time variable injection
  - raw command profile steps
  - Identity user, group, and permission profile steps
  - frontend step reordering preview
- Packages and Profiles frontend pages
- Workflows domain:
  - persisted workflow runs and steps
  - status lifecycle for runs and steps
  - workflow timeline/log frontend
- Scheduled automations:
  - interval and cron schedules
  - predefined action, custom action, package, and profile operations
  - in-process scheduler and async queue foundation
- Docker Compose deployments:
  - deployment definitions and target records
  - multi-target deploy/redeploy/restart/stop/status/log operations through Jobs
  - deployment executions and per-target execution records
  - credential-backed environment variable injection
- Remote access:
  - backend-mediated WebSocket shell
  - SFTP directory listing, file read, and hash-checked file write
  - operator write allowlist
- Linux identity orchestration:
  - user creation/update/delete
  - password expiration and login-shell disable
  - group creation/membership
  - SSH authorized_keys deployment/revocation
  - sudoers.d snippets
  - filesystem chmod/chown templates
  - multi-host replication through Jobs
  - guided access profiles
  - distro-aware administrator group abstraction
  - operational group presets
  - permission presets and rwx matrix UX
- Integration records and frontend Integrations settings page
- runtime consumption of persisted Proxmox and monitoring integration records
- monitoring readiness:
  - Prometheus provider health
  - Loki provider health
  - optional Grafana deep links
  - per-node metrics/log/exporter/staleness readiness
  - runtime snapshot persistence
- Provisioning frontend page
- Deployments, Workflows, Automations, Credentials, Identity, Monitoring, Host Tools, and Users/RBAC frontend pages
- ESLint, Prettier, Tailwind, and TypeScript tooling
- persistent docs under `docs/architecture/` and `docs/sprints/`

## Not Implemented Yet

- SSO/federated authentication:
  - Google SSO
  - OIDC
  - SAML
  - LDAP/Kerberos/FreeIPA/Active Directory/SSSD/PAM federation
- MFA/WebAuthn
- API keys and fine-grained permissions
- provider-side VM deletion for QEMU VMs
- Terraform
- Ansible integration
- distributed background workers
- realtime updates beyond current polling/read-refresh patterns
- infrastructure action audit persistence
- ISO installation workflows
- production-grade secret vaulting, rotation, and usage audit
- full workflow chaining and rollback orchestration
- provisioning and deployment idempotency keys
- Proxmox task audit/status persistence for all lifecycle actions
- frontend automated test coverage
- broader PostgreSQL-backed service/integration validation beyond Alembic migration smoke tests

## Operational Safety

- At the start of each working session, Codex should check root `backlog.md` to understand local manual-test status, recent fixes, open retest items, and what should be summarized back to the user.
- After each meaningful code or behavior change, Codex should review whether durable documentation needs updates and keep relevant docs current.
- Session summaries should include a short backlog review: what was done, what was tested, what still needs manual testing, and what remains pending.
- Proxmox lifecycle actions are intentionally limited to start, stop, reboot, and shutdown.
- The backend resolves VM node/type server-side before dispatching lifecycle actions.
- The backend validates VM existence and status before action dispatch.
- The frontend requires confirmation for stop, reboot, and shutdown.
- Inventory remains the orchestration abstraction layer. Jobs and operational actions execute only against inventory-managed servers, not raw Proxmox VM records.
- Operational actions must reuse the Jobs -> SSH -> persistence pipeline instead of creating standalone execution logic.
- Packages and Profiles must resolve into Jobs; they must not bypass the Jobs -> SSH -> persistence pipeline.
- Built-in package/profile defaults must remain recoverable through reset-to-default behavior.
- Cloned package/profile templates are user-managed and should not be implicitly changed by system template updates.
- Template variables use simple `{{ variable_name }}` substitution only; do not add Jinja, arbitrary Python execution, or a workflow engine.
- Identity operations must resolve into Jobs; they must not bypass the Jobs -> SSH -> persistence pipeline.
- Identity is Linux infrastructure orchestration and replication, not centralized authentication. Do not add LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, or login federation.
- Default Identity UX should be guided and operational. Preserve advanced Linux controls behind advanced mode rather than removing them.
- Provisioning must use Proxmox templates and cloud-init only; do not add ISO/raw installer provisioning.
- Provisioning must register Inventory before profile/package/bootstrap execution.
- Built-in package/profile templates may be listed and executed, but only custom persisted definitions should be editable/deletable.
- Destructive operational actions should require frontend confirmation.
- Remote access is for inventory-managed hosts only. Do not add arbitrary host/IP shell access.
- Remote shell WebSocket authentication uses short-lived scoped remote-access tokens issued by the backend; do not reintroduce long-lived JWT query tokens.
- Integration records may reference credentials, but they are not a full vault or rotation system.
- SSH passwords and private key paths are temporary local MVP metadata; do not treat them as production-grade secret management.
- Secrets must not be committed. Proxmox token values belong in local environment variables or ignored `.env` files.
- Generated logs, screenshots, local SQLite files, and build artifacts must not be committed.
- Local manual-testing trackers such as root `backlog.md`, review scratch files, and screenshots are for local use only and must not be pushed to the main repository.
- Keep pushes clean: include only relevant code, migrations, tests, and durable project documentation intended for the main repository.
- Codex must not push to `development` or `main` unless the user explicitly approves the exact changes to be pushed.
- `development` is the test/validation branch for fixes and improvements. `main` is the stable branch.
- Pushes to `development` may trigger automatic deployment to the development/test environment after the user approves the push.
- Future production deployment target is a server named `nexusops`; deploy stable app versions from `main` only after fixes are validated and the user explicitly approves promotion.
- Production deployment from `main` should be manually triggered, not silently run on every push unless the user changes this policy.

## Validation Requirements

Before finalizing substantial changes:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `DEBUG=false .venv/bin/python -m pytest backend/tests -q`
- verify Alembic migrations when database models change
- smoke-test inventory after backend changes
- smoke-test `/api/v1/proxmox/dashboard` after Proxmox changes
- smoke-test `/api/v1/jobs` and `/api/v1/jobs/actions` after Jobs/actions changes

## Codex Project Skills

The following local Codex skills are installed under `/home/cerberus/.codex/skills/` for NexusOps work:

- `nexusops-backend`: backend module, service/repository/router, migrations, jobs/actions, adapters, auth/RBAC, credentials, Proxmox, monitoring, identity, deployment, workflow, automation, and backend test guidance.
- `nexusops-frontend`: React/Vite/Tailwind feature structure, API/type contracts, shared operational UI, route loading, destructive-action confirmation, and frontend validation guidance.
- `nexusops-review`: repository/change review checklist for architecture boundaries, operational safety, inventory constraints, secret handling, RBAC, migrations, frontend/backend contracts, and validation.

## Review Snapshot

As of 2026-06-21, the repository contains a broad implemented modular monolith with approximately 190 backend Python files, 113 frontend TypeScript/TSX files, and 42 Alembic migration files. Existing generated or local artifacts must remain out of commits. Current known intentionally-flexible areas include in-process scheduling/runtime execution, JSON runtime metadata columns marked for future typed-column promotion, persisted integration records that are not a full vault/rotation system, and polling/read-refresh patterns instead of realtime updates.
