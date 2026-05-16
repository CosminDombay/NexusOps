# NexusOps Current State

## Implementation Status

NexusOps is currently a modular monolith with a FastAPI backend, a React/Vite frontend, PostgreSQL persistence, and a CMDB-style server inventory. The platform also includes Proxmox infrastructure visibility, controlled VM lifecycle actions, Proxmox template provisioning, Proxmox-to-inventory synchronization, SSH-backed job execution, reusable operational actions, package definitions, infrastructure profiles, editable built-in operational templates, integration records, a credential manager, variable-manager foundations, and credential-backed variable-driven execution.

The implemented system is focused on foundations, visibility, narrowly scoped VM lifecycle control, template provisioning, inventory synchronization, reusable automation templates, and the first orchestration layer. It does not yet perform VM deletion, full secrets vaulting, Terraform execution, Ansible execution, authentication, authorization, or workflow chaining.

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
  - archive server without destroying provider infrastructure
  - filter/search server inventory
- Inventory CMDB metadata:
  - managed/unmanaged state
  - lifecycle state: discovered, managed, provisioned, unmanaged, archived
  - synchronization state: unknown, synced, unmanaged, orphaned, mismatch, archived
  - provider linkage through provider, external ID/VMID, node, type, source, and last-seen metadata
- PostgreSQL-backed persistence through async SQLAlchemy.
- Alembic migrations for inventory, jobs, SSH authentication metadata, credentials, variables, and orchestration template metadata.
- React inventory dashboard with create form, responsive server list, loading states, and error handling.
- Inventory SSH authentication metadata:
  - key authentication
  - password authentication
  - optional private key path
  - optional shared credential reference through `credential_id`
- Credential Manager:
  - encrypted reusable credential records for passwords, SSH passwords, SSH keys, API tokens, and environment secrets
  - Fernet encryption using `NEXUSOPS_MASTER_KEY`
  - masked API responses that never return decrypted values
  - type-aware frontend form for credential creation
  - credential selection in Inventory node create/edit flows
- Variable Manager foundations:
  - persisted variable records with key, value, category, description, secret flag, and optional credential reference
  - secret variables must use credential references instead of plaintext values
- Shared Axios API client using `VITE_API_BASE_URL`.
- Proxmox integration:
  - node discovery
  - VM/container discovery
  - VM status lookup
  - cluster summary
  - frontend infrastructure dashboard
  - controlled VM start, stop, reboot, and shutdown actions
  - VM inventory synchronization status
  - import to Inventory workflow for unmanaged discovered VMs
  - reconciliation for missing, mismatched, and orphaned inventory records
  - guest-agent IP discovery for QEMU VMs when the agent is available
  - node detail page with per-node VM visibility
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
  - persist redacted command, status, stdout, stderr, exit code, and timestamps
  - support key-based, password-based, shared-credential, and explicit credential-ref execution
  - expose reusable operational actions backed by the jobs pipeline
  - frontend Jobs page with action runner, raw command runner, history, and tabbed stdout/stderr/command/metadata result viewer
  - bulk command execution foundation for sequential multi-host fanout
- Inventory health:
  - lightweight TCP reachability check against SSH port
  - per-host last health state, timestamp, and error metadata
  - bulk health refresh and health summary endpoints
- Package definitions:
  - Docker Engine
  - Tailscale
  - Node Exporter
  - Promtail
  - Fail2Ban
  - UFW
  - custom create/update/delete support
  - direct package execution through Jobs
  - editable built-in working copies that preserve recoverable system defaults
  - clone workflow for deriving user-managed templates from built-ins or custom records
  - restore-default workflow for built-in package overrides
  - install, uninstall, validation, variable, tag, category, and description editing
  - visual variable editor for required/sensitive/defaulted variables
  - simple `{{ variable_name }}` command parameterization with execution-time inputs
  - sensitive variables resolved from Credential Manager references at runtime
  - persisted job commands redacted when sensitive runtime values are injected
- Infrastructure profiles:
  - Base Linux Server
  - Docker Host
  - Monitoring Node
  - Development VM
  - sequential execution through Jobs
  - custom create/update/delete support
  - editable built-in working copies that preserve recoverable system defaults
  - clone workflow for deriving user-managed profiles from built-ins or custom records
  - restore-default workflow for built-in profile overrides
  - action, package, and raw command steps
  - structured visual step cards for package, action, deployment placeholder, and script placeholder steps
  - variable definitions through a visual editor
  - execution modal with normal runtime inputs and credential dropdowns for sensitive variables
  - move up/down and drag-and-drop step ordering in the editor
- Integrations:
  - persisted integration records for infrastructure providers, monitoring, networking, and database integrations
  - connection test support for Proxmox, Prometheus, and Grafana
  - Settings page for integration visibility and basic create/toggle/test workflows
- ESLint 9 flat configuration, TypeScript build, TailwindCSS, and Prettier configuration.
- Docker Compose deployments:
  - deployment definitions with compose/env storage
  - deployment target and revision persistence
  - deploy/redeploy/restart/stop/status/log operations through Jobs
- Monitoring foundation:
  - Prometheus HTTP API health check
  - basic per-server CPU, memory, disk, and uptime query support
  - Grafana deep-link generation when configured
- Linux identity orchestration:
  - reusable Linux user and group records
  - SSH public key records
  - filesystem permission templates
  - user/group/key/permission replication across selected inventory hosts
  - per-host execution history through Jobs and identity execution records
  - guided access profiles for administrator, deployment, Docker, log viewer, read-only, and service-account workflows
  - distro-aware administrator group resolution
  - operational group presets and group discovery
  - permission presets, rwx matrix UI, and generated command previews

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

Package definitions describe reusable install, uninstall, validation, variable, and metadata fields. Built-in package definitions provide starter standards, and custom definitions can be created for local workflows. Built-ins can also be edited as persisted working copies: the original code-defined template remains recoverable, while the persisted record carries `is_builtin`, `is_modified`, `base_version`, `source_template_id`, and `modified_at` metadata.

Profiles compose ordered package/action/command steps and apply them to inventory-managed hosts through the Jobs pipeline:

```text
Profile -> Package/Action step -> Job -> SSH adapter -> managed Linux host
```

Profile execution is synchronous and sequential for the MVP. Each step creates a persisted job. Profiles can be built from built-in actions, built-in packages, custom package definitions, and raw command steps. Built-in profiles can be edited as persisted working copies, cloned into user-managed templates, or reset to the code-defined default.

Template variables use the intentionally small syntax `{{ variable_name }}`. Variables are resolved before Jobs execution using definition defaults, execution-time inputs, and server-side credential references for sensitive values. Sensitive variables marked `sensitive=true` must be supplied as `credential_refs`; plaintext sensitive variable values are rejected. This is not a full templating engine: NexusOps does not execute Jinja, Python, or arbitrary template logic.

Runtime secret handling now flows through Credential Manager:

```text
Credential Manager -> encrypted credential -> runtime credential_ref -> command injection in memory -> redacted Job command history
```

Clone behavior intentionally breaks system update linkage. A cloned package/profile stores `source_template_id` for traceability but becomes user-managed and is no longer reset by built-in template changes.

Reset-to-default behavior applies only to built-in templates. It discards the persisted override while preserving execution history in Jobs.

### Integrations and Settings

Integration records provide a persisted configuration surface for provider and monitoring systems. They currently support basic creation, enable/disable toggling, and connection tests for Proxmox, Prometheus, and Grafana.

Runtime Proxmox, Prometheus, and Grafana services still primarily read local environment configuration. Integration records are the foundation for later runtime adapter selection and secret management, not a production-grade vault.

### Proxmox Template Provisioning

Provisioning uses only Proxmox VM templates and cloud-init customization:

```text
Provisioning request -> Proxmox clone/config/start -> SSH readiness -> Inventory registration -> optional bootstrap Jobs
```

Provisioned VMs become Inventory records before any bootstrap profile/package execution. This preserves Inventory as the orchestration source of truth.

### Inventory Synchronization and CMDB Lifecycle

Inventory now reconciles provider discovery with orchestration ownership:

```text
Proxmox discovery -> synchronization status -> optional import -> Inventory authority -> Jobs / Profiles / Packages
```

Discovered VMs are shown as unmanaged until an operator imports them. Import creates an Inventory record with Proxmox provider linkage, SSH metadata, lifecycle state, source metadata, and synchronization status. Reconciliation updates linked inventory records as synced, mismatched, orphaned, or archived without destroying provider-side infrastructure.

## Architecture Status

- Backend remains organized as a modular monolith.
- Module routers are the canonical API source.
- Inventory uses repository-service separation.
- Jobs use repository-service separation and reuse inventory targets for execution.
- Proxmox uses service-adapter separation because it talks to an external API rather than local persistence.
- Operational actions are a lightweight registry in the Jobs module and execute through the existing Jobs service.
- Package definitions and profiles combine built-in registries with persisted custom definitions and reuse Jobs for execution.
- Built-in packages and profiles are code-defined system templates with persisted editable overrides.
- Credential resolution lives in `backend/app/modules/credentials/` and decrypts secret material only inside backend runtime execution paths.
- Variable resolution lives in `backend/app/common/variables.py` and intentionally supports placeholder substitution only.
- Provisioning orchestrates Proxmox, Inventory, and bootstrap Jobs without creating a separate execution path.
- Adapter packages are canonicalized under `backend/app/adapters/`.
- SSH has a concrete Paramiko adapter for key/password command execution.
- Frontend is feature-based under `frontend/src/features/`.
- Shared shell, routing, API client, and layout code remain outside feature folders.

## Current Technical Debt

- Execution module is still a placeholder.
- Authentication and authorization are not implemented.
- Legacy inline SSH passwords/private key paths still exist for backward compatibility and local MVP use; shared Credential Manager records are the preferred path for reusable secrets.
- Integration configs are not a secrets vault yet; runtime provider adapters still primarily read local environment configuration.
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
- No centralized authentication or domain identity provider. Identity is Linux orchestration only; LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, and login federation are intentionally out of scope.
- Existing `docs/architecture.md` is older and less precise than the newer files in `docs/architecture/`.
- Runtime adapters do not yet load active integration records as their source of truth.
- Runtime adapter selection from persisted integration records is not implemented yet.

## Current Safety Boundary

The platform can mutate NexusOps-owned inventory data, import and reconcile discovered Proxmox VMs into Inventory, request controlled Proxmox VM lifecycle actions, provision VMs from Proxmox templates, edit reusable automation templates, execute commands/actions/packages/profiles against inventory-managed Linux hosts over SSH, resolve encrypted runtime secrets server-side, deploy Docker Compose projects, query Prometheus metrics, and replicate Linux identity state. Inventory deletion and archival are CMDB operations only; they do not destroy Proxmox VMs. Template reset restores NexusOps defaults only; it does not alter historical Jobs. The platform does not expose VM deletion, ISO installation, Kubernetes, Terraform execution, centralized authentication, or arbitrary provider-side infrastructure mutation.
