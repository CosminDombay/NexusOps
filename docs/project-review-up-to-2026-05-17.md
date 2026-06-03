# NexusOps Project Review - Up to 2026-05-17

> Historical snapshot: this file preserves the 2026-05-17 review. Several gaps listed here, including user management, audit persistence, token hardening, and CI pipeline coverage, have since been completed or partially completed. Use `docs/architecture/current-state.md`, `docs/development.md`, `docs/recommended-next-steps.md`, and `docs/api.md` for current status.

## Executive Summary

NexusOps is a self-hosted infrastructure orchestration platform built as a modular monolith. The project has evolved from a basic inventory application into an operational control plane for lab/server infrastructure.

The platform currently supports:

- server inventory and CMDB-style lifecycle tracking
- Proxmox infrastructure visibility
- controlled VM lifecycle actions
- Proxmox template-based VM provisioning
- SSH-backed job execution
- reusable operational actions
- package and infrastructure profile automation
- integration records
- encrypted credential records
- Docker Compose deployment foundations
- monitoring foundations
- Linux identity orchestration
- workflow and automation foundations
- local platform authentication
- JWT sessions
- role-based access control foundations

The current system is intentionally focused on safe orchestration boundaries. NexusOps can operate on inventory-managed infrastructure, but it avoids high-risk features such as VM deletion, arbitrary provider mutation, external identity federation, and production-grade secret vault behavior.

## Technical Stack

### Backend

- FastAPI
- async SQLAlchemy
- PostgreSQL
- Alembic migrations
- Pydantic v2
- structlog
- httpx for provider APIs
- Paramiko for SSH execution
- passlib/bcrypt for password hashing
- python-jose for JWTs

### Frontend

- React
- TypeScript
- Vite
- TailwindCSS
- Axios
- React Router
- lucide-react icons

## Architecture

NexusOps uses a modular monolith architecture.

Backend domains live under:

```text
backend/app/modules/
```

Most database-backed modules follow:

```text
models.py
schemas.py
repository.py
service.py
router.py
tasks.py
```

The architecture separates:

- routers: HTTP request/response concerns
- services: orchestration and business rules
- repositories: database queries
- adapters: external infrastructure integrations

The frontend is feature-based:

```text
frontend/src/features/<feature>/
  api/
  components/
  hooks/
  pages/
  types/
  utils/
```

This keeps platform domains isolated and makes future modules easier to add.

## Core Design Principle

Inventory is the orchestration abstraction layer.

Jobs, packages, profiles, deployments, identity operations, and future workflows execute against inventory-managed servers. NexusOps does not treat raw Proxmox VM records as direct execution targets.

This gives the platform a consistent safety model:

```text
Provider discovery -> Inventory ownership -> Jobs/SSH execution -> Persisted history
```

## Implemented Backend Domains

### Inventory

Inventory is the source of truth for managed servers.

Implemented capabilities:

- create, list, update, delete, and archive servers
- track hostname, IP, OS, provider, VMID/external ID, environment, tags
- track managed/unmanaged lifecycle state
- track synchronization status with provider state
- store SSH connection metadata
- support password/key authentication metadata
- support reusable credential references
- reconcile Proxmox-discovered VMs with inventory records

Important boundary:

- deleting or archiving inventory does not delete provider VMs

### Proxmox Visibility and Lifecycle

Proxmox integration provides infrastructure visibility and controlled lifecycle operations.

Implemented capabilities:

- list nodes
- list VMs/containers
- show cluster summary
- show node detail
- query VM status
- discover guest-agent IPs when available
- start, stop, reboot, and shutdown VMs
- resolve VM node/type server-side before lifecycle action dispatch

Safety limits:

- no VM deletion
- no arbitrary Proxmox mutation
- lifecycle actions are validated server-side
- destructive lifecycle actions require frontend confirmation

### Provisioning

Provisioning uses Proxmox templates and cloud-init.

Implemented capabilities:

- list Proxmox templates
- clone from cloud-init capable template
- configure CPU, memory, disk, network bridge, static IP/CIDR, gateway, DNS
- configure cloud-init username, password, and SSH key
- poll Proxmox tasks
- poll SSH readiness
- register new VM into Inventory before bootstrap execution
- optionally run packages/profiles after provisioning
- persist provisioning history
- support provisioning blueprints for reusable VM defaults

Important boundary:

- provisioning uses templates only
- no ISO/raw installer workflows

### Jobs

Jobs are the execution backbone.

Implemented capabilities:

- execute SSH commands against inventory-managed servers
- persist pending/running/success/failed/cancelled status
- capture stdout, stderr, exit code, command, and timestamps
- resolve SSH authentication from inventory metadata or credential records
- execute predefined operational actions
- execute bulk commands sequentially

Operational actions reuse Jobs instead of creating another execution pipeline.

Current predefined actions include:

- uptime
- disk usage
- memory usage
- Docker containers
- Docker status
- Docker restart
- Docker Engine install
- Tailscale install
- Node Exporter install

### Packages

Packages define reusable installation/validation automation.

Implemented capabilities:

- built-in packages:
  - Docker Engine
  - Tailscale
  - Node Exporter
  - Promtail
  - Fail2Ban
  - UFW
- custom package create/update/delete
- edit built-in package working copies
- clone package templates
- reset built-in package back to defaults
- variable definitions
- execution-time variable injection
- sensitive variable resolution through Credential Manager
- execution through Jobs

Template variables use simple `{{ variable_name }}` substitution only.

### Profiles

Profiles compose ordered infrastructure steps.

Implemented capabilities:

- built-in profiles:
  - Base Linux Server
  - Docker Host
  - Monitoring Node
  - Development VM
- custom profile create/update/delete
- edit built-in profile working copies
- clone profile templates
- reset built-in profiles to defaults
- action/package/raw-command steps
- profile execution through Jobs
- variable definitions and execution-time injection
- frontend step reordering preview

Profiles do not bypass Jobs.

### Credentials

Credential Manager stores reusable secret material.

Implemented capabilities:

- encrypted credential records
- supported credential types for passwords, SSH passwords, SSH keys, API tokens, and env secrets
- Fernet encryption using `NEXUSOPS_MASTER_KEY`
- masked API responses
- runtime decryption only inside backend execution paths
- credential references from Inventory, Jobs, Packages, Profiles, Deployments, and Integrations

Important limitation:

- this is not yet a production-grade vault

### Variables

Variable Manager foundations are implemented.

Implemented capabilities:

- persisted variable records
- key/value/category/description metadata
- secret variables must reference credentials
- package/profile variable substitution

Important boundary:

- no Jinja
- no Python execution
- no workflow engine hidden inside templates

### Integrations

Integration records provide a persisted configuration surface.

Implemented capabilities:

- create/toggle/test integration records
- support Proxmox, Prometheus, Grafana-style integration metadata
- credential references for API tokens/bearer secrets
- Proxmox runtime can resolve from enabled persisted integrations, with environment fallback

### Deployments

Docker Compose deployment foundations are implemented.

Implemented capabilities:

- persist deployment definitions
- store compose content
- store non-secret environment values
- resolve credential-backed env values at runtime
- deploy/redeploy/restart/stop/status/logs through Jobs
- persist deployment revisions and targets
- redact command history when secrets are injected

### Monitoring

Monitoring foundations are implemented.

Implemented capabilities:

- Prometheus API health check
- basic per-server CPU, memory, disk, and uptime query support
- Grafana deep-link generation when configured
- monitoring frontend page

### Linux Identity Orchestration

Identity is infrastructure identity, not platform login.

Implemented capabilities:

- Linux user records
- Linux group records
- SSH public key records
- filesystem permission templates
- guided access profiles
- operational group presets
- distro-aware administrator group abstraction
- permission presets and rwx matrix UI
- replication across selected inventory hosts through Jobs
- identity execution history

Important boundary:

- no LDAP
- no Kerberos
- no FreeIPA
- no Active Directory
- no SSSD/PAM rewriting
- no login federation

### Workflows and Automations

Workflow and automation foundations are implemented.

Implemented capabilities:

- persisted workflow runs
- persisted workflow steps
- workflow status lifecycle
- ordered step logs/errors
- automation schedules using APScheduler
- interval and cron schedules
- automation run-now
- automation enable/disable
- automations execute predefined actions, packages, profiles, or raw commands through existing pipelines

Current boundary:

- no advanced workflow chaining yet
- no external background worker stack yet

## Sprint 12: Authentication and RBAC Foundation

The latest implemented sprint added platform authentication.

Implemented backend capabilities:

- new `backend/app/modules/auth/` module
- `users` table
- local username/email and password login
- passlib/bcrypt password hashing
- JWT access tokens
- JWT refresh tokens
- `/api/v1/auth/login`
- `/api/v1/auth/refresh`
- `/api/v1/auth/logout`
- `/api/v1/auth/me`
- environment-based admin bootstrap
- reusable auth dependencies:
  - `get_current_user`
  - `require_admin`
  - `require_operator`
  - `require_viewer`
- protected backend routers
- role restrictions for admin/operator/viewer access

Implemented frontend capabilities:

- login page
- logout
- auth context/provider
- session restore on refresh
- token persistence
- route guards
- access denied page
- role-aware sidebar navigation
- Axios JWT attachment
- refresh-token handling for expired access tokens
- 401 redirect to login

Current roles:

- `admin`: full platform access
- `operator`: operational execution areas
- `viewer`: read-oriented access

Implemented but intentionally not yet added:

- user management UI
- role assignment UI
- password reset/change UI
- force password change on first login
- fine-grained permissions
- SSO/OIDC/LDAP/MFA

Bootstrap admin is configured through ignored local `.env` values:

```text
NEXUSOPS_ADMIN_USER
NEXUSOPS_ADMIN_EMAIL
NEXUSOPS_ADMIN_PASSWORD
```

This avoids committing a default admin account or hardcoding credentials in migrations.

## Frontend Implemented Pages

Current frontend pages include:

- Inventory
- Host detail
- Infrastructure dashboard
- Infrastructure node detail
- Credentials
- Provisioning
- Deployments
- Packages
- Profiles
- Jobs
- Automations
- Workflows
- Monitoring
- Identity
- Integrations settings
- Login
- Access denied

The frontend uses shared API clients, feature-specific API modules, route guards, and role-aware navigation.

## Documentation Added

Persistent documentation exists under:

```text
docs/architecture/
docs/sprints/
```

Important documents include:

- backend architecture
- frontend architecture
- current state
- adapter architecture
- sprint records from foundation through auth/RBAC

## Validation Status

The current implementation has been validated with:

```powershell
cd frontend
npm run lint
npm run build
```

and:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
```

Recent backend test result:

```text
49 passed
```

Recent frontend validation:

```text
ESLint clean
TypeScript/Vite production build clean
```

Alembic migration chain was also rendered offline successfully through the new auth migration.

## Local Development Utilities

The project now includes helper scripts:

```text
scripts/start-dev.ps1
scripts/reset-bootstrap-admin.ps1
```

`start-dev.ps1`:

- creates local `.env` if missing
- prompts for bootstrap admin values
- runs migrations
- starts backend
- starts frontend

`reset-bootstrap-admin.ps1`:

- resets or creates the local bootstrap admin according to `.env`
- useful when the stored password no longer matches local `.env`

## Current Safety Boundaries

NexusOps currently can:

- mutate NexusOps-owned inventory data
- reconcile provider-discovered infrastructure into Inventory
- request controlled Proxmox lifecycle actions
- provision VMs from templates
- execute commands through SSH against managed inventory hosts
- run packages/profiles/deployments through Jobs
- resolve encrypted runtime secrets server-side
- replicate Linux identity state to managed hosts
- enforce local platform login and coarse RBAC

NexusOps currently does not implement:

- VM deletion
- Terraform execution
- Ansible integration
- Kubernetes orchestration
- ISO/raw installer provisioning
- public SSO/federated login
- LDAP/SAML/OIDC/MFA
- API keys
- fine-grained permissions
- production-grade vault semantics
- workflow rollback orchestration
- advanced workflow chaining
- real-time updates

## Main Technical Debt

Important remaining work:

- user management UI/API
- password change and reset flow
- force password change for bootstrap admin
- better token storage strategy
- fine-grained route/action-level RBAC
- audit log persistence
- background worker architecture
- real-time workflow/job updates
- deployment step execution inside profiles
- richer workflow chaining
- production-grade secret storage
- integration-driven runtime adapter configuration everywhere
- frontend automated tests
- CI pipeline

## Recommended Next Steps

Short-term:

1. Add user management for admins.
2. Add password change and bootstrap password rotation.
3. Add audit persistence for login/logout/execution actions.
4. Add finer route/action-level RBAC checks.
5. Add frontend auth smoke tests.

Medium-term:

1. Move long-running provisioning and execution into a durable worker system.
2. Add real-time updates for jobs, workflows, provisioning, and automations.
3. Expand workflow chaining and rollback behavior.
4. Harden credential storage and token handling.
5. Add CI validation for backend tests, frontend lint/build, and migrations.

Long-term:

1. Add SSO/OIDC providers behind the provider-agnostic auth architecture.
2. Add Terraform/Ansible integrations as controlled orchestration modules.
3. Add advanced monitoring/log collection.
4. Add public exposure hardening before Tailscale Funnel or external access.

## Bachelor Presentation Framing

NexusOps demonstrates a practical infrastructure orchestration platform with a strong emphasis on modular architecture, operational safety, and progressive implementation.

Key points to highlight:

- It is not just a CRUD app; it has real infrastructure workflows.
- Inventory is used as the central authority for safe orchestration.
- Execution is centralized through Jobs, avoiding duplicated remote-command logic.
- Proxmox integration uses a service-adapter pattern.
- Packages, profiles, deployments, identity, and automations reuse the same execution pipeline.
- Authentication and authorization were introduced without mixing platform users with Linux infrastructure users.
- The system intentionally avoids dangerous provider operations such as VM deletion.
- The project has tests, migrations, documentation, and local development scripts.

The current state is a strong MVP/foundation for a self-hosted infrastructure control plane.
