# NexusOps Documentation And Code Audit - 2026-06-06

This review compares the durable documentation against the current code shape in the workspace. The audit source of truth was the registered FastAPI router tree, module route decorators, runtime snapshot models, frontend router, and repository file layout.

## Code Shape Confirmed

The backend still follows the modular monolith architecture:

```text
backend/app/api/v1/router.py
  -> backend/app/modules/<domain>/router.py
  -> service.py
  -> repository.py
  -> models.py
```

Implemented API modules registered under `/api/v1` are:

```text
auth
audit-events
automations
credentials
vms
servers
identity
deployments
integrations
packages
monitoring
profiles
jobs
proxmox
remote-access
runtime-state
variables
workflows
```

The frontend route tree in `frontend/src/app/router.tsx` exposes:

```text
authenticated: /, /nodes/:id, /inventory/:id, /infrastructure, /infrastructure/nodes/:id, /monitoring, /workflows
operator: /provisioning, /deployments, /packages, /profiles, /jobs, /automations, /inventory/:id/tools
admin: /infrastructure/credentials, /identity, /settings/integrations, /settings/users
```

## Documentation Updates Made

- `README.md` now points to this review as the latest project review.
- `docs/api.md` now uses the current date and lists the more exact route surface for auth users, inventory health/inspection, Proxmox sync/lifecycle, jobs actions, integrations sync, provisioning, monitoring, and runtime-state refresh.
- `docs/architecture/backend.md` now includes audit, runtime-state, and variables in the route overview, documents the centralized RBAC boundary, and updates migration coverage for audit, monitoring validation, and runtime snapshot/status/event tables.
- `docs/architecture/frontend.md` now matches the current React Router path list and documents the viewer/operator/admin route groups as code-like Markdown.
- `docs/architecture/runtime-snapshots.md` now describes the implemented `node_runtime_snapshots`, `runtime_refresh_status`, and `runtime_refresh_events` contract more precisely.
- `docs/development.md` now records this documentation audit separately from the 2026-06-04 runtime validation status.

## Current Gaps And Risks

- Frontend automated tests are still not configured.
- Full backend validation was not rerun for this Markdown-only pass.
- Several older project review logs remain historical snapshots and should not be treated as current architecture documents.
- API docs are still a concise operational overview rather than a generated OpenAPI reference. `/docs` or `/api/v1/openapi.json` remains the exact request/response schema source when OpenAPI is enabled.
- Deployment logs are available on demand through deployment APIs, but they are not yet indexed as first-class searchable records.
- Distributed workers, SSO, MFA, API keys, fine-grained permissions, production secret rotation, broad provider-side destructive lifecycle operations, Terraform, and Ansible remain out of implemented scope.

## Validation Notes

This pass changed documentation only. The code comparison used read-only inspection commands against local files; no migrations or application runtime code were modified.

Before finalizing future code-bearing changes, run:

```bash
cd frontend && npm run lint
cd frontend && npm run build
DEBUG=false .venv/bin/python -m pytest backend/tests -q
DEBUG=false .venv/bin/alembic heads
```
