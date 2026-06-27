# NexusOps Current State

## Implementation Status

NexusOps is currently a modular monolith with a FastAPI backend, a React/Vite frontend, PostgreSQL persistence, local platform authentication, JWT sessions, RBAC foundations, and a CMDB-style managed-node inventory. The platform also includes Proxmox infrastructure visibility, first-class Proxmox hypervisor host management, Proxmox VM and LXC discovery, LXC provisioning foundations, controlled guest lifecycle actions, Proxmox template provisioning, NexusOps provisioning blueprints, Proxmox-to-inventory synchronization, SSH-backed job execution, browser-based remote shell/file access for inventory-managed hosts, persistent workflow runs, scheduled automations, reusable operational actions, package definitions, infrastructure profiles, editable built-in operational templates, integration records, a credential manager, variable-manager foundations, multi-target Docker Compose deployment runtime tracking, operational monitoring readiness, Linux identity orchestration, and credential-backed variable-driven execution.

The implemented system is focused on foundations, visibility, narrowly scoped provider lifecycle control, template provisioning, inventory synchronization, reusable automation templates, local platform login, role-based access boundaries, managed-node operations, and the first observable orchestration runtime layer. It does not yet perform full secrets vaulting, Terraform execution, Ansible execution, SSO/federated identity, MFA, distributed worker queueing, advanced filesystem editing, or workflow chaining.

## Working Functionality

- Backend API startup through FastAPI.
- Versioned API routing under `/api/v1`.
- Health endpoint.
- Local platform authentication:
  - username/email and password login
  - bcrypt password hashing
  - JWT access and refresh tokens
  - token-version based revocation for logout, password reset, and role/security changes
  - persisted refresh-token sessions with rotation and family reuse detection
  - current-session logout and logout-all session invalidation
  - per-user inactivity timeout overrides
  - `/api/v1/auth/me` current-user lookup
  - environment-based initial admin bootstrap
  - reusable RBAC dependencies for admin, operator, and viewer access
  - admin-only user administration APIs for listing, creating, role editing, deactivation, and password reset
- Frontend authentication:
  - login page
  - session restore from session-scoped browser storage
  - logout
  - protected route guards
  - role-aware sidebar navigation
  - 401 redirect and 403 access-denied handling
  - admin Users & RBAC page
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
  - managed node type: VM, LXC, physical host, or hypervisor
  - lifecycle state: discovered, imported, managed, provisioned, unmanaged, deleting, deleted, failed, archived, decommissioned
  - management state: discovered, unmanaged, managed, retired
  - synchronization state: unknown, synced, unmanaged, orphaned, mismatch, archived
  - capability metadata foundation for SSH, shell, filesystem, identity, monitoring, and provisioning
  - provider linkage through provider, external ID/VMID, node, type, source, and last-seen metadata
- PostgreSQL-backed persistence through async SQLAlchemy.
- Alembic migrations for inventory, jobs, SSH authentication metadata, credentials, variables, and orchestration template metadata.
- React inventory dashboard with create form, responsive server list, loading states, and error handling.
- Shared contextual drawer component for secondary create/edit/configure workflows across operational pages.
- Inventory SSH authentication metadata:
  - key authentication
  - password authentication
  - optional private key path
  - optional shared credential reference through `credential_id`
- Credential Manager:
  - encrypted reusable credential records for passwords, SSH passwords, SSH keys, API tokens, and environment secrets
  - Fernet encryption using `NEXUSOPS_MASTER_KEY`
  - masked API responses that never return decrypted values
  - type-aware frontend drawer for credential creation and metadata/secret replacement edits
  - credential selection in Inventory node create/edit flows
  - soft-delete Trash lifecycle with restore and permanent purge controls
  - permanent credential purge blocked by active references from Inventory, Deployments, Automations, Integrations, Profiles, Variables, or Identity users
- Variable Manager foundations:
  - persisted variable records with key, value, category, description, secret flag, and optional credential reference
  - secret variables must use credential references instead of plaintext values
- Shared Axios API client using `VITE_API_BASE_URL`.
- Shared TargetSelector frontend component for orchestration target selection:
  - single-host and bulk-host modes
  - searchable host list
  - environment, provider, and managed/unmanaged filters
  - consistent target cards showing hostname, IP, environment, provider, managed state, and lifecycle state
- Proxmox integration:
  - node discovery
  - VM/container discovery
  - first-class hypervisor host discovery and Inventory reconciliation
  - VM status lookup
  - cluster summary
  - frontend infrastructure dashboard
  - controlled VM start, stop, reboot, and shutdown actions
  - LXC start, stop, restart, shutdown, delete/archive, and sync/reconcile foundations
  - VM inventory synchronization status
  - LXC inventory synchronization status
  - import to Inventory workflow for unmanaged discovered VMs
  - reconciliation for missing, mismatched, and orphaned inventory records
  - guest-agent IP discovery for QEMU VMs when the agent is available
  - LXC IP/status/capacity metadata when Proxmox exposes it
  - node detail page with per-node VM visibility
  - Proxmox VMID-backed inventory imports are classified as managed `vm` nodes
  - Proxmox cluster nodes are classified as managed `hypervisor` records with provider metadata, lifecycle state, monitoring state, guest counts, and operational detail pages
- Provisioning:
  - Proxmox template selection
  - LXC template discovery and LXC provisioning request support
  - NexusOps provisioning blueprints for reusable VM defaults
  - full clone from cloud-init-capable templates
  - cloud-init username/password/SSH key configuration
  - static IP/CIDR, gateway, DNS configuration
  - configurable root disk sizing
  - optional additional disk creation after clone
  - batch provisioning from blueprints with sequential VMID/IP/name generation
  - Proxmox task polling
  - SSH readiness polling
  - inventory auto-registration
  - optional ordered profile/package/deployment bootstrap through Jobs
  - reusable bootstrap order templates for saving and reapplying profile/package/deployment sequences
  - provisioning lifecycle history
  - provisioning UI distinguishes VM and LXC run paths while reusing managed-node registration
- Jobs and orchestration:
  - execute SSH commands against inventory-managed servers
  - persist redacted display command, immutable actual command metadata, status, stdout, stderr, exit code, and timestamps
  - append-only execution intent events, command hashes, command policy results, initiator metadata, and correlation IDs
  - support key-based, password-based, shared-credential, and explicit credential-ref execution
  - expose reusable operational actions backed by the jobs pipeline
  - built-in validation action for SSH/sudo readiness checks through the selected execution credential
  - admin-managed custom operational actions with create/update/delete support
  - custom actions can be executed directly from Jobs and referenced by Profiles and Automations
  - frontend Jobs page with shared target selection, action runner, raw command runner, history, and tabbed stdout/stderr/command/metadata result viewer
  - bulk command execution foundation for sequential multi-host fanout
- Remote access:
  - `/api/v1/remote-access` module for Inventory-bounded shell and file access
  - WebSocket shell sessions through backend Paramiko channels using short-lived one-time scoped shell tokens
  - SFTP directory listing and file reading
  - hash-checked file writes with stale-write rejection
  - operator write allowlist for `/opt`, `/srv`, `/var/www`, and `/home`
  - admin/operator remote-access authorization and viewer denial
  - SSH trust-on-first-use fingerprint storage and host-key mismatch blocking
  - lightweight structured audit hooks without command transcript or file-content logging
  - Host Tools frontend page with a unified files/editor workspace above a persistent terminal panel
  - resizable terminal panel for operational workspace management
- Workflow engine foundation:
  - persisted workflow runs
  - persisted workflow steps
  - workflow status lifecycle: pending, queued, running, success, failed, cancelled
  - step status lifecycle: pending, running, success, failed, skipped
  - ordered step logs and errors
  - workflow list/detail API
  - frontend Workflows page with timeline/log view and target host visibility for workflow steps
  - runtime progress fields for current step, completed/failed step counts, linked jobs, target nodes, and duration
- Scheduled automations foundation:
  - interval and cron schedules
  - predefined action automations
  - custom action automations
  - package execution automations
  - profile execution automations
  - create/update/delete/enable/disable/run-now API
  - APScheduler startup/shutdown integration
  - automation runs create WorkflowRuns and execute through existing Jobs/Profile/Package services
  - frontend Automations page with edit and delete controls
  - scheduled automation cards show execution target hostnames, target groups, runtime state, last/next run, execution counts, duration, and recent execution history for operational visibility
- Inventory health:
  - lightweight TCP reachability check against SSH port
  - per-host last health state, timestamp, and error metadata
  - bulk health refresh and health summary endpoints
  - scheduled runtime refresh updates online/offline state and last-seen metadata
- Package definitions:
  - Docker Engine
  - Tailscale
  - Node Exporter
  - Promtail
  - Fail2Ban
  - UFW
  - custom create/update/delete support
  - direct package execution through Jobs with shared single/bulk target selection
  - editable built-in working copies that preserve recoverable system defaults
  - clone workflow for deriving user-managed templates from built-ins or custom records
  - restore-default workflow for built-in package overrides
  - install, uninstall, validation, variable, tag, category, and description editing
  - visual variable editor for required/sensitive/defaulted variables
  - contextual create/edit drawer so package management does not dominate the page layout
  - simple `{{ variable_name }}` command parameterization with execution-time inputs
  - runtime variables can be supplied from typed values or Credential Manager references
  - persisted job commands redacted when credential-backed runtime values are injected
- Infrastructure profiles:
  - Base Linux Server
  - Docker Host
  - Monitoring Node
  - Development VM
  - sequential execution through Jobs with shared single/bulk target selection
  - custom create/update/delete support
  - editable built-in working copies that preserve recoverable system defaults
  - clone workflow for deriving user-managed profiles from built-ins or custom records
  - restore-default workflow for built-in profile overrides
  - action, package, deployment, Identity user, Identity group, Identity permission, and raw command steps
  - structured visual step cards for package, action, deployment, Identity, and script steps
  - variable definitions through a visual editor
  - execution modal with normal runtime inputs and credential dropdowns for sensitive variables
  - move up/down and drag-and-drop step ordering in the editor
  - contextual create/edit drawer so profile authoring remains secondary to profile selection and execution
- Integrations:
  - persisted integration records for infrastructure providers, monitoring, networking, and database integrations
  - credential reference fields for API tokens and bearer-style auth secrets
  - connection test support for Proxmox, Prometheus, and Grafana
  - structured settings forms for Proxmox, Prometheus, Grafana, and Tailscale placeholder configuration
  - normal UX hides secrets and generates config JSON server-compatible payloads
  - optional advanced JSON overlay for extra configuration
  - contextual add/edit drawer for integration configuration
  - Proxmox runtime can resolve an enabled persisted Proxmox integration record
  - Monitoring runtime resolves enabled Prometheus, Grafana, and Loki integration records by explicit provider type
  - environment-backed monitoring settings remain fallback/bootstrap only
- ESLint 9 flat configuration, TypeScript build, TailwindCSS, and Prettier configuration.
- Docker Compose deployments:
  - deployment definitions with compose/env storage
  - deployment executions and per-target execution records
  - credential-backed environment variables resolved server-side at deploy time
  - redacted deployment command history when secrets are injected into `.env`
  - configurable remote base path for deployment project directories
  - remote base path persists on the deployment definition and is applied to deployment targets
  - generated remote compose file name is `docker-compose.yaml`
  - deployment target and revision persistence
  - multi-target deploy/redeploy/restart/stop/status/log operations through Jobs
  - deployment edit and delete API/UI
  - operational deployment cards with runtime status, per-target state, target hosts, ports, compose source, duration, output summaries, health state, and synchronization state
  - persisted deployment target runtime state refreshed by manual and scheduled Docker inspection
  - centered responsive create/edit deployment drawer so forms appear only when requested
  - inspect and log panels for operational feedback
  - partial success/failure rollups for multi-target orchestration
- Monitoring validation:
  - persisted monitoring snapshots per managed Inventory node
  - node states: monitored, partial, unmonitored, stale, and unknown
  - node-local service checks for node_exporter, promtail, and cAdvisor
  - TCP reachability validation for exporter ports
  - SSH `systemctl is-active` fallback where Inventory SSH metadata is available
  - cAdvisor Docker fallback through `docker ps` when cAdvisor is containerized
  - Prometheus shown as provider-level monitoring infrastructure health, not a per-node row signal
  - Grafana jump links generated from integration templates and node metadata
  - Monitoring overview renders persisted snapshots only and does not query Prometheus, Loki, or Grafana during page rendering
  - unmanaged/discovered provider assets are excluded; Monitoring follows the managed Inventory CMDB boundary
  - NexusOps treats Prometheus and Grafana as external observability tools, not dashboard lifecycle systems
- Linux identity orchestration:
  - reusable Linux user and group records
  - planned group member lists on managed Linux groups for future replication/profile application
  - optional stored account password credential references on managed Linux users
  - SSH public key records with optional planned assigned users
  - filesystem permission templates saved as planned desired state before host replication
  - user/group/key/permission replication across selected inventory hosts
  - existing Linux user and group discovery through Jobs
  - discovered user/group adoption into managed records
  - managed user edit/delete and managed group edit/delete flows
  - optional Credential Manager password selection when creating/updating Linux users; stored account password credential references can be reused by Profile Identity steps; passwords are applied with `chpasswd` and redacted from Job history
  - selected password/SSH-password credential support for sudo-backed user/group replication, lock/unlock, shell-disable, password-expire, and member add/remove actions
  - group-only user updates avoid unrelated password, lock, sudoers, and shell/home operations unless those fields changed
  - live user group inspection per host using `id -nG`
  - live group member inspection per host, combining supplementary members from `getent group` with primary-group members from `getent passwd`
  - per-host execution history through Jobs and identity execution records
  - host-origin context for discovered users/groups in the Identity UI
  - guided access profiles for administrator, deployment, Docker, log viewer, read-only, and service-account workflows
  - distro-aware administrator group resolution
  - operational group presets and group discovery
  - permission presets, rwx matrix UI, and generated command previews
  - protected `root` account exclusion from discovery, creation/adoption, direct inspection, and remote lifecycle operations
  - password expiration and login-shell disable actions for account lifecycle workflows
- Host detail operational hub:
  - unified managed-node operational page for hypervisors, VMs, LXCs, and physical hosts
  - tabbed node context for Overview, Management, Metrics, Terminal, Files, Deployments, Jobs, Workflows, Packages, Profiles, and Identity
  - operational readiness state, SSH readiness, monitoring readiness, provider metadata, networking, runtime history, lifecycle controls, and shell/file access foundation
  - terminal/files tab entries route into the unified Host Tools workspace
- Frontend performance:
  - route-level lazy loading and code splitting
  - xterm/remote tools isolated from the initial app chunk

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

The Proxmox integration validates the adapter architecture against a real infrastructure provider. It retrieves infrastructure state from Proxmox and renders hypervisor nodes, VMs, LXCs, and summary metrics in the frontend. Active Proxmox integrations can now reconcile cluster hosts and guests into Inventory as distinct managed node types.

### Controlled VM Lifecycle Actions

The infrastructure dashboard now exposes guarded VM lifecycle controls for start, stop, reboot, and shutdown. The backend validates VM existence and current state before dispatching Proxmox actions, and the frontend provides confirmation prompts, per-VM action loading state, and success/error feedback.

### Jobs, SSH Execution, and Operational Actions

Jobs established the first orchestration backbone:

```text
Inventory -> Jobs -> SSH adapter -> managed Linux host
```

Inventory remains the source of managed execution targets. Jobs persist every command execution and operational action result. Operational actions provide reusable workflows such as uptime checks, disk and memory diagnostics, Docker status/restart, simple installation commands, and approved storage setup while reusing the Jobs execution path.

### Package Definitions and Profiles

Package definitions describe reusable install, uninstall, validation, variable, and metadata fields. Built-in package definitions provide starter standards, and custom definitions can be created for local workflows. Built-ins can also be edited as persisted working copies: the original code-defined template remains recoverable, while the persisted record carries `is_builtin`, `is_modified`, `base_version`, `source_template_id`, and `modified_at` metadata.

Profiles compose ordered package/action/deployment/Identity/command steps and apply them to inventory-managed hosts through the Jobs pipeline:

```text
Profile -> Package/Action/Deployment/Identity step -> Job -> SSH adapter -> managed Linux host
```

Profile execution is synchronous and sequential for the MVP. Each step creates a persisted job or calls a module service that creates persisted Jobs. Profiles can be built from built-in actions, built-in packages, custom package definitions, Docker Compose deployments, managed Identity users/groups/permission templates, and raw command steps. Built-in profiles can be edited as persisted working copies, cloned into user-managed templates, or reset to the code-defined default.

Template variables use the intentionally small syntax `{{ variable_name }}`. Variables are resolved before Jobs execution using definition defaults, execution-time inputs, and server-side credential references. Operators can select Credential Manager records as runtime variable values for packages and profiles, which keeps reusable tokens such as a Tailscale auth key out of plaintext run forms. Sensitive variables marked `sensitive=true` must be supplied as `credential_refs`; plaintext sensitive variable values are rejected. This is not a full templating engine: NexusOps does not execute Jinja, Python, or arbitrary template logic.

Runtime secret handling now flows through Credential Manager:

```text
Credential Manager -> encrypted credential -> runtime credential_ref -> command injection in memory -> redacted Job command history
```

Clone behavior intentionally breaks system update linkage. A cloned package/profile stores `source_template_id` for traceability but becomes user-managed and is no longer reset by built-in template changes.

Reset-to-default behavior applies only to built-in templates. It discards the persisted override while preserving execution history in Jobs.

### Integrations and Settings

Integration records provide a persisted configuration surface for provider and monitoring systems. The normal frontend path is now schema-driven instead of raw JSON editing. Operators select Proxmox, Prometheus, Grafana, or the Tailscale placeholder, then configure URL, auth mode, credential references, SSL verification, and timeout fields.

The backend still stores a JSON `config` payload for compatibility, but validates known integration shapes and expects secrets to flow through credential references. Advanced JSON remains available only as an override surface.

Runtime consumption of persisted integrations is active for the primary provider and observability paths. Proxmox adapters resolve enabled persisted Proxmox integrations only; environment values are used only to bootstrap the first default infrastructure integration when none exists yet. Monitoring resolves enabled Prometheus, Grafana, and Loki integration records by provider type, with environment-backed settings remaining as fallback/bootstrap configuration.

### Proxmox Template Provisioning and Blueprints

Provisioning uses only Proxmox VM templates and cloud-init customization:

```text
Provisioning request -> Proxmox clone/config/start -> SSH readiness -> Inventory registration -> optional bootstrap Jobs
```

Provisioned VMs become Inventory records before any bootstrap profile/package execution. This preserves Inventory as the orchestration source of truth.

NexusOps provisioning blueprints are UI/API-side presets for repeatable VM creation. The actual base image remains a Proxmox template; the blueprint stores the fixed operational defaults around that template:

- Proxmox template ID and target node
- CPU, RAM, root disk, and additional disks
- network bridge, gateway, DNS, environment, tags, and start-on-boot behavior
- default cloud-init username and optional SSH public key
- ordered bootstrap profile, package, and deployment selections

Blueprints intentionally do not lock per-machine identity values such as VM name, VMID, cloud-init hostname, or static IP/CIDR. Operators select a blueprint, fill in the unique host identity/network fields, then provisioning registers Inventory before running the ordered bootstrap plan through Jobs. Bootstrap items can mix infrastructure profiles, package definitions, and Docker Compose deployments. Deployment bootstrap attaches the freshly provisioned Inventory host as a deployment target when needed, then runs the deployment through the existing Jobs-backed Docker Compose path.

Bootstrap order templates store only the ordered profile/package/deployment sequence. They are useful when the same bootstrap run order should be reused across multiple provisioning blueprints or one-off VM/LXC requests without copying the full sizing, network, and Proxmox template defaults.

Provisioning now separates QEMU VM provisioning from LXC provisioning. VM provisioning uses Proxmox templates and cloud-init customization. LXC provisioning uses downloaded Proxmox container templates, CTID allocation, target node/storage/network sizing inputs, Inventory registration, readiness-state metadata, and optional bootstrap through the existing Jobs/Profile/Package paths. Shell access is validated separately from infrastructure discovery so a container can be imported even when SSH is not ready.

### Inventory Synchronization and CMDB Lifecycle

Inventory now reconciles provider discovery with orchestration ownership:

```text
Proxmox discovery -> synchronization status -> optional import -> Inventory authority -> Jobs / Profiles / Packages
```

Discovered VMs are shown as unmanaged until an operator imports them. Import creates an Inventory record with Proxmox provider linkage, `integration_id`, source type, SSH metadata, lifecycle state, sync metadata, and synchronization status. Reconciliation is scoped per integration and updates linked inventory records as synced, mismatched, stale, disconnected, or archived without destroying provider-side infrastructure. Guest sync also marks linked VM/LXC inventory records stale when the provider guest no longer appears in Proxmox, which leaves operator history visible while making the stale state explicit before cleanup.

Inventory records survive integration failures. If a Proxmox integration disconnects or a sync fails, NexusOps marks owned resources stale or disconnected, records timestamps/errors, and keeps the records visible for future resync or operator recovery.

Existing Proxmox inventory created before integration ownership is adopted during sync when it matches the discovered host or guest and has no `integration_id`. This preserves the old inventory identity while moving it under the persisted integration authority model.

Inventory deletion performs reference cleanup before removing the active server record. It clears or removes Jobs-backed runtime links, provisioning request links and stale bootstrap job IDs, virtual machine links, workflow target links, deployment target rows, monitoring/runtime records, and other server-owned execution records. Archive and decommission remain the retained-history lifecycle paths.

Inventory also now has a managed-node lifecycle foundation:

```text
provider discovery -> discovered/unmanaged
operator import -> imported/managed
NexusOps provisioning -> provisioned/managed
operator unmanage -> unmanaged
operator archive -> archived/retired
operator decommission -> decommissioned/retired
operator restore -> managed
```

Archived and decommissioned records are hidden from active operational flows by default but remain historically queryable with `include_inactive=true`. Jobs, deployments, remote access, provisioning reuse, and health checks treat retired records as non-active targets.

Proxmox host/node management is now first-class in the managed-node model. Active Proxmox integrations discover cluster nodes and reconcile them as `node_type=hypervisor` Inventory records with provider metadata, guest counts, lifecycle state, monitoring readiness, and operational pages. Decommissioning a hypervisor disconnects it from active orchestration and provider synchronization while preserving historical queryability.

### UX Consistency and Operational Workspace

Orchestration pages now share common target-selection, contextual-workflow, and operational action patterns:

```text
TargetSelector -> selected inventory host(s) -> module-specific request -> existing service pipeline
```

Packages, Profiles, Automations, Jobs, and Deployments use the shared selector for consistent search, filtering, single-target selection, and bulk-target intent. Deployments now persist all selected targets and execute per-target Jobs sequentially in the MVP, recording per-target state and partial success/failure outcomes.

Create/edit/configuration workflows are now treated as secondary contextual actions instead of permanent CRUD panels:

```text
entity list / explorer -> operational cards or tables -> ContextDrawer for create/edit/configure
```

The shared `ContextDrawer` component provides the standard right-size overlay shell for Inventory host import, Credential create/edit, custom Job action create/edit, Automation create/edit, Package create/edit, Profile create/edit, Integration add/edit, and provisioning blueprint/batch actions. The Deployments drawer was centered and kept as the primary visual baseline for service-style operational workflows.

The shared operational component set now standardizes page-level action placement, runtime badges, status pills, collapsible action panels, and compact operational toolbars. Large provisioning, package, profile, automation, workflow, credential, deployment, and job forms should be opened from page headers, drawers, or collapsed panels instead of permanently occupying dashboard space.

Inventory manual onboarding is now labeled `Import Existing Host` to clarify that provisioning and provider discovery are the primary onboarding paths. The Proxmox synchronization action is labeled as discovered-guest synchronization rather than a completed desired-state reconciliation workflow.

Remote Access now presents files and the file editor above a persistent terminal console. The backend shell, SFTP, RBAC, credential resolution, and audit boundaries remain unchanged.

### Final Refinement Slice

The first final-refinement slice tightened operational UX and session safety without changing the modular monolith architecture:

- Docker deployments now present a card-based operational dashboard modeled after service/stack views.
- Deployment create/edit forms are drawer-based instead of permanently visible.
- Deployment reads include lightweight derived metadata for ports, health, uptime, compose source, and sync state.
- Monitoring exposes external Prometheus, Grafana, and Loki links while keeping NexusOps focused on quick operational summaries.
- Local auth tokens now carry a per-user token version, allowing logout, password reset, and security-sensitive user changes to revoke older tokens.
- Frontend auth persistence now uses `sessionStorage` and clears older `localStorage` tokens.
- Linux `root` is treated as a protected account for identity orchestration.

### Operational Workspace Refactor

The next refinement pass standardized create/edit workflows around contextual drawers instead of independent collapsibles or permanently visible forms:

- Added reusable `ContextDrawer`.
- Inventory import is a secondary `Import Existing Host` workflow.
- Credentials, Jobs custom actions, Automations, Packages, Profiles, Integrations, and RBAC users use contextual drawer workflows for create/edit.
- Provisioning keeps the VM wizard as the main center workflow, while blueprint actions and batch provisioning move into drawers.
- Scheduled automations show target hostnames.
- Deployment create/edit positioning is centered and responsive.

### Review Findings on 2026-05-20

The 2026-05-20 review confirmed the platform had shifted from inventory plus CRUD pages toward a managed-node operational control plane:

- Proxmox hypervisors, VMs, LXCs, and physical hosts are represented as distinct managed node types.
- Hypervisor host discovery and decommissioning are integration-driven rather than VM lifecycle features.
- LXC discovery/provisioning/lifecycle foundations are wired into Inventory and Infrastructure, while advanced file editing remains future work.
- Deployments are now runtime operations with definitions, executions, per-target executions, and partial-success states.
- Automations and workflows expose runtime state, target visibility, recent executions, and linked operational history.
- Monitoring is now an observability readiness board focused on metrics/log availability, stale telemetry, exporters, scrape health, and provider readiness.
- Grafana is treated as optional deep analysis tooling, not a dashboard lifecycle dependency.
- Operational forms are increasingly collapsed, drawer-based, or header-triggered to reduce dashboard clutter.

### Review Findings on 2026-05-23

The 2026-05-23 review confirms that the implementation has moved beyond the older sprint memory and now behaves like a broad local control-plane MVP:

- Local auth/RBAC, admin user management, token-version revocation, and session-scoped frontend token storage are implemented.
- Inventory is now a managed-node CMDB for hypervisors, VMs, LXCs, and physical hosts rather than a simple server CRUD list.
- Proxmox, provisioning, Jobs, profiles, packages, deployments, identity, monitoring, remote access, workflows, and automations all converge on Inventory-managed targets.
- Credential-backed runtime secret resolution exists, but it should still be treated as encrypted local MVP secret handling rather than a production vault.
- Runtime snapshots and monitoring validation are present. The Monitoring overview is snapshot-first and avoids live Prometheus/Grafana/Loki discovery during normal rendering.
- Durable audit events are now persisted for authentication, inventory reconciliation, Proxmox lifecycle mutations, credentials, provisioning entrypoints, Jobs/package/profile/deployment/identity executions, workflows, remote access, and monitoring validation.
- Monitoring validation now persists historical validation attempts with method, duration, structured failure reason, component results, and optional audit-event linkage.
- CI is defined for frontend lint/build, backend tests, Alembic head/current/upgrade/downgrade validation, and generated-artifact hygiene checks.
- Frontend lint and production build pass on the current working tree.
- Backend tests are isolated from live infrastructure and pass against fake/synthetic adapters and fixtures.

### Preparation Review on 2026-05-27

The 2026-05-27 review confirms that the app is ready to move into deployment preparation and structured testing:

- Docker Compose is the preferred first deployment path because it builds the backend/frontend, provides PostgreSQL, proxies frontend `/api` calls, and runs Alembic migrations during backend startup.
- On-prem LXC/VM deployment is viable as a service-style install with PostgreSQL, a Python virtual environment, Uvicorn, a built frontend, and Nginx reverse proxying.
- Container updates can be automated as an operator-triggered flow: back up PostgreSQL, pull/build images, start the stack, allow migrations to run, and smoke-test health, auth, inventory, jobs/actions, Proxmox, and monitoring.
- Unattended self-updating should wait until backups, rollback, migration validation, and smoke tests are scripted.
- The only tracked zero-byte code file is `backend/app/modules/identity/__init__.py`, which is an intentional Python package marker.

### Stabilization Review on 2026-06-03

The 2026-06-03 stabilization pass focused on deployment and identity manual test findings:

- Credential Manager edit, infrastructure storage display, inventory import, stale inventory import conflicts, provisioning frontend/backend synchronization, and Node Management SSH connectivity were fixed before the current documentation refresh.
- Docker deployment runtime diagnostics were improved with per-target execution output, better status/error visibility, runtime refresh reconciliation, Docker discovery sudo fallback, and permission-aware messaging.
- Identity discovery, user/group creation, discovered-object adoption, group membership synchronization, sudo credential propagation, and user/group card host-origin context were improved.

### Documentation And Code Audit on 2026-06-06

The 2026-06-06 documentation/code audit aligned durable Markdown docs with the current router tree, frontend route tree, and runtime snapshot models:

- `docs/api.md` now lists the more exact implemented route surface for auth, inventory, Proxmox, Jobs, integrations, provisioning, monitoring, and runtime-state refresh.
- `docs/architecture/backend.md` now includes audit, runtime-state, variables, and the centralized router authorization boundary.
- `docs/architecture/frontend.md` now matches `frontend/src/app/router.tsx`, including route groups for authenticated, operator, and admin users.
- `docs/architecture/runtime-snapshots.md` now describes the implemented snapshot/status/event tables more precisely.
- The 2026-06-06 review log remains a historical router/docs audit. The latest thesis-readiness documentation review is `docs/project-review-2026-06-21-thesis-docs-readiness.md`.
- Failed job completion and failed audit events now log at error severity. Human-readable logs are the default with JSON logging still available through `LOG_FORMAT=json`.
- The local ignored `backlog.md` is the manual stabilization tracker. Items believed fixed should be marked `Needs testing` until manual validation confirms the final status.
- Full backend validation passed locally with `DEBUG=false .venv/bin/python -m pytest backend/tests -q` producing 147 passing tests after the Identity replication credential changes.

### Stabilization Update on 2026-06-04

The 2026-06-04 stabilization update tightened execution credentials, deployment diagnostics, and operator preflight checks:

- Jobs, Packages, Profiles, Automations, and Deployments can pass an execution/sudo credential separately from application environment secrets.
- Deployments persist `execution_credential_ref` and use it for deploy, redeploy, restart, stop, status, logs, and runtime refresh Jobs.
- Deployment create/update/deploy/redeploy paths validate Compose structure before execution.
- Deployment dry-run previews show Compose validation, service names, target hosts, remote paths, env keys, credential-backed env keys, and redacted generated commands.
- Deployment runtime reads include stale state, runtime age, concise failure reason, per-target container state, missing services, health, and sync drift.
- Host Detail / Node Management includes credential readiness signals for managed state, SSH metadata, credential references, sudo fallback, and Docker operation readiness.
- Proxmox guest sync marks missing linked guests stale, and discovered-record self-sanitize supports dry-run preview before deletion.
- Manual testing is still required before these are moved from `Needs testing` to fixed/tested in the local backlog.

### Stabilization Update on 2026-06-18

The 2026-06-18 stabilization work focused on keeping the app steady for thesis validation while closing manual-test findings:

- Sidebar scrolling now allows small screens to reach lower navigation entries such as RBAC and Trash.
- Identity planned-state records now support users, groups, group members, SSH key assignment, and permission templates before replication to real target hosts.
- Custom action creation avoids page-wide rerenders during field editing, improving typing responsiveness in the Jobs custom action drawer.
- Profile builder layout was widened and step controls were adjusted so target/type/credential controls fit better in dense profiles.
- Docker deployments can now be saved as planned drafts with no selected target. Deployment create/edit no longer silently falls back to the first inventory host, and cards label no-target records as planning-only.
- Docker deployment cards expose target lists and per-target runtime state for multi-host deployments.
- Package uninstall commands are now executable through Jobs as explicit uninstall operations; package install remains install plus validation, while uninstall runs the uninstall command alone.
- Search, credential references, and the universal Trash workflow were manually retested and worked in the remote test environment.
- Credentials now use the universal Trash page for restore and purge, keeping one clear Trash entrypoint.
- Full unattended VM provisioning plus profile/package/deployment application still needs final start-to-end validation before being marked complete.

### Thesis Documentation Readiness Review on 2026-06-21

The 2026-06-21 review aligned the living documentation and local thesis use-case files with the current simplified demonstration plan:

- `USECASE.md` and `USECASE-001-RUNBOOK.md` now describe a focused Docker demo host instead of the earlier monitoring-heavy node.
- The primary demo flow is base utilities, optional data disk preparation, Docker Engine, an Identity step that places `cerberus` in the `docker` group, Portainer, cAdvisor, a demo Nginx service, and final Jobs-backed validation.
- Node Exporter, Promtail, Tailscale, code-server, broad account rollout, and monitoring deep dives are intentionally out of the first live presentation path.
- The router/page review found no `.doc` or `.docx` Word files in the repository at the time of review.
- Repository shape at review time was approximately 190 backend Python files, 113 frontend TypeScript/TSX files, 42 Alembic migration files, and 20 backend test modules.
- Validation after the documentation refresh passed with frontend lint, frontend build, 175 backend tests, and an Alembic single-head check at `20260620_0042`. The backend suite emitted one `passlib` `crypt` deprecation warning.

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
- Variable resolution lives in `backend/app/common/variables.py` and intentionally supports `{{ variable_name }}` placeholder substitution only. Shell-style `${variable}` is not NexusOps template syntax unless the remote shell has already defined that environment variable.
- Provisioning orchestrates Proxmox, Inventory, and bootstrap Jobs without creating a separate execution path.
- Provisioning blueprints persist reusable provisioning defaults while keeping Proxmox VM templates as the provider-side base image.
- Batch provisioning creates a parent batch record and normal child provisioning requests. Each generated VM still goes through the existing Proxmox clone, cloud-init, SSH readiness, Inventory registration, and optional bootstrap flow.
- Docker Compose deployments reuse Jobs for deploy/redeploy/restart/stop/status/logs, resolve credential-backed env values server-side, and persist definition/execution/target-execution runtime separation. Application/env secrets and execution/sudo credentials are distinct concepts. Deployment definitions may exist as planned drafts without targets, but runtime operations require one or more managed inventory targets.
- Deployment API reads include derived operational metadata, per-target runtime state, runtime age, stale markers, failure reasons, and redacted dry-run previews while execution still flows through the existing Jobs pipeline.
- Frontend create/edit/configuration workflows should prefer `ContextDrawer` or focused modals over permanent page-level forms.
- Frontend operational pages should prefer shared page-header actions, operational toolbars, runtime badges, and collapsible action panels over page-local button/form patterns.
- Remote Access reuses Inventory as the target boundary and Credential Manager resolution for SSH material; it does not accept arbitrary host targets or expose credentials to the frontend.
- Remote Access uses one-time scoped shell tokens for WebSocket setup and stores trusted SSH host-key fingerprints on Inventory records.
- Production startup validates unsafe configuration and emits structured warnings or errors based on environment.
- Baseline security middleware adds rate limiting and security headers for public-exposure readiness.
- RBAC user management is implemented under the auth module and remains admin-only through backend route dependencies. Users & RBAC includes per-user session inactivity policy controls for system default, 30 minutes, 60 minutes, 90 minutes, and no inactivity timeout.
- Inventory deletion cleanup is owned by `InventoryService`; it clears active server references and stale provisioning bootstrap job links without turning reusable configuration records into machine-owned data.
- Adapter packages are canonicalized under `backend/app/adapters/`.
- SSH has a concrete Paramiko adapter for key/password command execution.
- Frontend is feature-based under `frontend/src/features/`.
- Shared shell, routing, API client, and layout code remain outside feature folders.

## Current Technical Debt

- Execution module is still a placeholder.
- `backend/app/modules/identity/__init__.py` is the only tracked zero-byte code file and is intentionally kept as a Python package marker.
- Authentication, authorization, and admin user lifecycle are implemented for local users. Google SSO, OIDC, LDAP, SAML, MFA, API keys, and fine-grained permissions are not implemented.
- Workflow chaining is still partial. Provisioning can bootstrap profiles, packages, and deployment items, and ProfileService can run deployment steps when a deployment service is supplied. A deeper WorkflowRun-backed orchestration model for clone/config/bootstrap/deployment phases remains future work.
- Legacy inline SSH passwords/private key paths still exist for backward compatibility and local MVP use; shared Credential Manager records are the preferred path for reusable secrets.
- Integration configs are structured and credential-reference aware, but they are not a secrets vault yet.
- No frontend test framework is configured yet.
- CI pipeline coverage exists for lint, build, backend tests, Alembic single-head/current/upgrade validation, downgrade smoke, and generated-artifact hygiene.
- PostgreSQL migration behavior is validated by the CI workflow against a PostgreSQL service.
- Proxmox live validation depends on local environment variables and a reachable Proxmox host.
- Proxmox credentials are intentionally not persisted in source-controlled files.
- Proxmox lifecycle actions currently return accepted task IDs but do not poll task completion.
- Proxmox lifecycle action audit persistence is implemented for start, stop, reboot, and shutdown outcomes.
- Jobs still execute synchronously inside the JobService call, but scheduled automations now dispatch through WorkflowRuns and an in-process async queue.
- Profiles still run sequentially inside ProfileService, but automation-triggered profile runs now persist workflow steps.
- Provisioning still needs the deeper background refactor so each clone/config/bootstrap phase is driven fully by WorkflowRun steps.
- Provisioning blueprints do not yet discover valid Proxmox storage targets per node; extra disks currently rely on operator-entered storage names.
- Deployment logs are pulled on demand from Docker Compose and are not yet indexed as first-class log records.
- Docker deployment steps can execute through `ProfileService`, but richer blueprint-style deployment composition still needs refinement.
- Docker deployment discovery/adoption is not implemented yet. NexusOps can manage deployments it creates or records explicitly, but it does not yet scan existing Compose projects, adopt them into managed records, or destructively remove machine-side services/files through a dedicated removal workflow.
- No centralized domain identity provider. Identity is Linux orchestration only; LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, and login federation are intentionally out of scope.
- Identity discovery reads live Linux state through Jobs and does not yet persist per-host user/group membership snapshots as first-class inventory records.
- Identity UI still needs a clearer target-first matrix for large environments so managed records, discovered host observations, and drift/reconciliation status are not visually blended.
- Identity splits "account password to set" from "execution/sudo credential"; future UX work should continue making that distinction visible in target-first workflows.
- Existing `docs/architecture.md` is older and less precise than the newer files in `docs/architecture/`.
- Runtime adapter support from persisted integration records is partial; Proxmox and Monitoring can resolve active integration records, while future adapters still need deeper runtime integration.
- Proxmox integration failover/replacement workflows are not implemented yet.
- Provisioning now collapses large action areas, but a full guided review wizard is still planned.
- Provisioning blueprints are not yet first-class Workflow/Automation operations.
- CT/LXC support is operationally wired for discovery, provisioning, lifecycle, and Inventory registration, but advanced filesystem editing, deeper network validation, and richer template/storage discovery remain future work.
- Monitoring validation is operational with durable validation attempt history and structured failure reasons. Deep log exploration and centralized log indexing remain future work.
- Remote shell WebSocket authentication now uses short-lived scoped remote-access tokens instead of the active JWT.
- Refresh-token rotation and reuse detection are implemented with persisted token session families. Future work remains around httpOnly refresh-cookie transport and session management UX.
- Monitoring overview should remain snapshot-first. Avoid live provider discovery or dashboard search during ordinary rendering unless it is behind an explicit refresh path.
- Runtime visibility is eventually consistent: login and scheduler-triggered refreshes update inventory health and Docker deployment state in the backend, while frontend inventory/deployment pages poll normalized API state without direct infrastructure checks or page reloads.
- CI/CD has improved, but feature-specific smoke suites and Playwright coverage for critical UI flows remain recommended for deployment/identity stabilization.

## Current Safety Boundary

The platform can authenticate local NexusOps users, enforce coarse RBAC boundaries, revoke existing JWT sessions through token-version changes, mutate NexusOps-owned inventory data, import and reconcile discovered Proxmox hypervisors, VMs, and LXCs into Inventory, request controlled Proxmox guest lifecycle actions, provision VMs from Proxmox templates, provision LXCs from Proxmox container templates, edit reusable automation templates, execute commands/actions/packages/profiles against inventory-managed Linux hosts over SSH, provide backend-mediated shell/file access to inventory-managed Linux hosts, resolve encrypted runtime secrets server-side, run multi-target Docker Compose deployments, derive monitoring readiness from telemetry providers, and replicate non-root Linux identity state. Inventory deletion and archival are CMDB operations only unless a provider-specific lifecycle endpoint explicitly performs provider mutation. Deployment record deletion is a NexusOps record operation only; destructive machine-side Compose removal remains future work. Template reset restores NexusOps defaults only; it does not alter historical Jobs. The platform does not expose ISO installation, Kubernetes, Terraform execution, SSO/federated login, arbitrary SSH targets, raw Proxmox consoles, Docker/container shells, root account orchestration, dynamic Grafana dashboard generation, or arbitrary provider-side infrastructure mutation.
