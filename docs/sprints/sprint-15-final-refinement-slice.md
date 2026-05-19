# Sprint 15 - Final Refinement Slice

## Purpose

This slice starts the final refinement and operational stabilization phase before workflow validation, rebuild testing, final documentation, and demo preparation.

The goal is not to add a new architecture layer. NexusOps remains a modular monolith, and existing APIs, inventory boundaries, credential resolution, provisioning logic, shell functionality, deployment workflows, and Jobs-backed execution paths are preserved.

## Implemented

### Deployment UX

Docker Deployments were refactored from a permanent create/edit form plus table into an operational service dashboard.

The page now provides:

- deployment cards
- runtime status badges
- target host display
- detected port mappings from Compose content
- compose source
- uptime indicator
- health state
- synchronization state
- direct start, stop, restart, redeploy, inspect, logs, edit, and delete actions
- status filtering
- inspect output panel
- log output panel
- drawer-based create/edit workflow

The backend now includes lightweight derived deployment metadata in `DeploymentRead`:

- `ports`
- `compose_source`
- `uptime_seconds`
- `health_state`
- `sync_status`

Deployment execution still uses the existing Jobs-backed Docker Compose pipeline.

### Monitoring Links

Monitoring now follows the intended hybrid model more clearly:

- NexusOps shows quick metrics and operational summaries.
- Prometheus, Grafana, and Loki remain the advanced observability tools.

Added:

- `LOKI_BASE_URL` configuration
- Prometheus quick links
- Grafana links
- Loki links
- link metadata in monitoring API responses

### Authentication Hardening

Local auth now uses user token versions in JWTs.

Token versions are incremented when:

- a user logs out
- an admin resets a user's password
- role, active state, or superuser state changes

This revokes older access and refresh tokens for that user.

Frontend auth persistence now uses `sessionStorage` instead of `localStorage`, and legacy local-storage auth keys are cleared.

### Identity Safety

The Linux `root` account is now protected from NexusOps identity orchestration.

NexusOps now prevents:

- discovering root as a managed identity candidate
- creating/adopting root as a managed Linux user
- inspecting root group membership through the identity endpoint
- running remote lifecycle operations against existing root identity records

Identity remains Linux account orchestration, not ownership of privileged system accounts.

## Validation

Validated with:

```powershell
cd frontend
npm run lint
npm run build
```

and:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
```

Current backend result:

```text
81 passed
```

## Deferred

The following items remain for later refinement slices:

- provider lifecycle management UX
- reusable execution target abstraction for host, VM, LXC, and Docker container workflows
- full Docker container runtime management
- HDS-DEV rebuild blueprint workflow
- broader create/edit drawer cleanup across packages, profiles, integrations, hosts, and provider entities
- refresh-token rotation and reuse detection
- short-lived scoped remote-access tokens for shell WebSockets
