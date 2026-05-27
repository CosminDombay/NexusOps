# NexusOps Preparation Review - 2026-05-27

This review reflects the current workspace state after the security hardening, session policy, runtime refresh, remote-access token, command governance, and deployment packaging work present in the codebase.

## Current Application Shape

NexusOps is now a broad local infrastructure control-plane MVP rather than a simple inventory tool. The implemented system includes local platform authentication, admin RBAC, managed-node inventory, Proxmox visibility and provisioning, Jobs-backed SSH execution, packages, profiles, workflows, scheduled automations, Docker Compose deployments, remote shell/file access, integrations, monitoring readiness, audit events, runtime snapshots, and Linux identity orchestration.

The architecture still follows the modular monolith rules:

- FastAPI module routers are the canonical API surface under `/api/v1`.
- Database-backed domains use repository/service separation.
- Proxmox, SSH, and Docker runtime behavior stays behind service/adapter boundaries.
- Inventory remains the orchestration boundary for Jobs, deployments, remote access, packages, profiles, identity, monitoring, and provisioning bootstrap.
- Frontend pages remain feature-scoped under `frontend/src/features/` with shared layout, API client, drawers, target selection, and operational components outside individual features.

## Backend Review

Implemented backend domains are registered through `backend/app/api/v1/router.py`:

- `auth`
- `audit-events`
- `automations`
- `credentials`
- `vms` / provisioning
- `servers` / inventory
- `identity`
- `deployments`
- `integrations`
- `packages`
- `monitoring`
- `profiles`
- `jobs`
- `proxmox`
- `remote-access`
- `runtime-state`
- `variables`
- `workflows`

Recent hardening is visible in the application startup and auth/runtime modules:

- Production startup validates unsafe configuration before serving traffic.
- Security headers and in-memory rate limiting are installed globally.
- Refresh-token sessions are persisted, rotated, and revocable by token version.
- Remote shell WebSockets use short-lived scoped remote-access tokens instead of long-lived auth JWT query parameters.
- SSH host-key trust-on-first-use fingerprints are stored and mismatches are blocked.
- Jobs persist execution intent metadata, command hashes, policy results, events, initiator metadata, correlation IDs, and audit events.
- Runtime refresh updates inventory reachability and Docker deployment runtime state in the backend instead of making UI pages perform live infrastructure checks.

## Frontend Review

The route tree in `frontend/src/app/router.tsx` exposes the working product surface:

- Inventory and host detail are the default authenticated workspace.
- Infrastructure and monitoring are viewer-visible operational pages.
- Provisioning, deployments, packages, profiles, jobs, automations, and host tools are operator-visible pages.
- Credentials, Linux identity, integrations, and users/RBAC are admin-visible pages.
- Pages are lazy loaded, including heavier remote-tool surfaces, to keep the initial app smaller.

The UI has converged around the right interaction patterns for the platform:

- Operational pages use page headers, drawers, tabs, tables, cards, and runtime badges.
- Target selection is shared across Jobs, packages, profiles, deployments, and automations.
- Destructive or infrastructure-mutating actions remain confirmation-oriented.
- Remote tools are bounded to inventory-managed hosts.

## Docker And On-Prem Readiness

The repository has a working production-oriented Docker path:

- `docker-compose.yml` runs PostgreSQL, backend, and frontend.
- `backend/Dockerfile.prod` installs Python dependencies, copies the backend, and runs Alembic migrations through `backend/docker-entrypoint.sh` before starting Uvicorn.
- `frontend/Dockerfile.prod` builds the Vite app and serves static assets with Nginx.
- The frontend Nginx config proxies `/api` to the backend container.
- `scripts/start-docker.ps1` and `scripts/stop-docker.ps1` provide Windows-friendly wrappers.

For an on-prem LXC install, the app can run as normal processes:

- PostgreSQL installed locally or reachable on the network.
- Backend running in a Python virtual environment under Uvicorn.
- Frontend built with Vite and served by Nginx.
- Alembic migrations run before backend service start or during controlled releases.
- Environment variables stored in a local `.env` or systemd environment file outside source control.

Docker is the lower-friction deployment path for repeatable updates. LXC gives more direct host control and simpler inspection, but requires a small release procedure and service management.

## Empty File And Document Audit

Tracked empty code files:

- `backend/app/modules/identity/__init__.py` is intentionally empty and should remain. It marks `identity` as an importable Python package.

Tracked docs were checked and now serve current review, architecture, sprint, and roadmap purposes. Placeholder `.gitkeep` files under documentation folders are intentional directory markers and should remain unless those folders are removed entirely.

Generated or local artifacts that should remain out of commits include:

- development logs such as `backend-dev.log`, `backend-dev.err.log`, and `frontend-dev*.log`
- screenshots generated for review
- `.pytest_cache/`
- `.venv/`
- `frontend/node_modules/`
- frontend build output

## Current Gaps Before Testing

- Frontend tests are still not configured.
- Provisioning, deployments, and bulk operations still need fuller WorkflowRun-backed async execution.
- Idempotency keys are still needed for provisioning and deployment operations.
- Distributed background workers are not implemented.
- Deployment logs are retrieved on demand and not yet indexed as first-class records.
- Proxmox lifecycle task persistence/polling is partial.
- Production secret vaulting, rotation, and usage audit remain future work beyond the local encrypted Credential Manager.
- SSO, MFA, API keys, and fine-grained permissions remain out of scope for this phase.

## Update Automation Answer

Yes, updates can be automated in a container workflow, but the safest MVP shape is a controlled pull-build-migrate-restart script rather than self-updating application code.

Recommended container update flow:

1. Pull the latest Git revision or image tag.
2. Back up the PostgreSQL volume or database.
3. Rebuild or pull backend/frontend images.
4. Start the stack with `docker compose up -d --build`.
5. Let the backend entrypoint run Alembic migrations.
6. Verify `/api/v1/health`, login, inventory, jobs/actions, and any provider dashboards.

For production-like use, prefer CI-built tagged images and an operator-triggered update command. Avoid automatic unattended updates until backups, rollback, migration validation, and health checks are formalized.
