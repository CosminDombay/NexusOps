# NexusOps Current State

## Implementation Status

NexusOps is currently a modular monolith with a FastAPI backend, a React/Vite frontend, PostgreSQL persistence, local platform authentication, JWT sessions, RBAC foundations, and a CMDB-style server inventory. The platform also includes Proxmox infrastructure visibility, controlled VM lifecycle actions, Proxmox template provisioning, NexusOps provisioning blueprints, Proxmox-to-inventory synchronization, SSH-backed job execution, browser-based remote shell/file access for inventory-managed hosts, persistent workflow runs, scheduled automations, reusable operational actions, package definitions, infrastructure profiles, editable built-in operational templates, integration records, a credential manager, variable-manager foundations, Docker Compose deployments, monitoring foundations, Linux identity orchestration, and credential-backed variable-driven execution.

The implemented system is focused on foundations, visibility, narrowly scoped VM lifecycle control, template provisioning, inventory synchronization, reusable automation templates, local platform login, role-based access boundaries, and the first orchestration layer. It does not yet perform VM deletion, full secrets vaulting, Terraform execution, Ansible execution, SSO/federated identity, MFA, or workflow chaining.

## Working Functionality

- Backend API startup through FastAPI.
- Versioned API routing under `/api/v1`.
- Health endpoint.
- Local platform authentication:
  - username/email and password login
  - bcrypt password hashing
  - JWT access and refresh tokens
  - token-version based revocation for logout, password reset, and role/security changes
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
  - VM status lookup
  - cluster summary
  - frontend infrastructure dashboard
  - controlled VM start, stop, reboot, and shutdown actions
  - VM inventory synchronization status
  - import to Inventory workflow for unmanaged discovered VMs
  - reconciliation for missing, mismatched, and orphaned inventory records
  - guest-agent IP discovery for QEMU VMs when the agent is available
  - node detail page with per-node VM visibility
  - Proxmox VMID-backed inventory imports are classified as managed `vm` nodes
  - Proxmox hosts without VMIDs can be represented as `hypervisor` inventory records, but automated Proxmox host registration and host-level management are not yet complete
- Provisioning:
  - Proxmox template selection
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
  - optional profile/package bootstrap through Jobs
  - provisioning lifecycle history
- Jobs and orchestration:
  - execute SSH commands against inventory-managed servers
  - persist redacted command, status, stdout, stderr, exit code, and timestamps
  - support key-based, password-based, shared-credential, and explicit credential-ref execution
  - expose reusable operational actions backed by the jobs pipeline
  - custom operational actions with create/update/delete support for operator-defined command sequences
  - custom actions can be executed directly from Jobs and referenced by Profiles and Automations
  - frontend Jobs page with shared target selection, action runner, raw command runner, history, and tabbed stdout/stderr/command/metadata result viewer
  - bulk command execution foundation for sequential multi-host fanout
- Remote access:
  - `/api/v1/remote-access` module for Inventory-bounded shell and file access
  - WebSocket shell sessions through backend Paramiko channels
  - SFTP directory listing and file reading
  - hash-checked file writes with stale-write rejection
  - operator write allowlist for `/opt`, `/srv`, `/var/www`, and `/home`
  - admin/operator remote-access authorization and viewer denial
  - lightweight structured audit hooks without command transcript or file-content logging
  - Host Tools frontend page with a unified files/editor workspace above a persistent terminal panel
- Workflow engine foundation:
  - persisted workflow runs
  - persisted workflow steps
  - workflow status lifecycle: pending, queued, running, success, failed, cancelled
  - step status lifecycle: pending, running, success, failed, skipped
  - ordered step logs and errors
  - workflow list/detail API
  - frontend Workflows page with timeline/log view and target host visibility for workflow steps
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
  - scheduled automation cards show execution target hostnames for operational visibility
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
  - direct package execution through Jobs with shared single/bulk target selection
  - editable built-in working copies that preserve recoverable system defaults
  - clone workflow for deriving user-managed templates from built-ins or custom records
  - restore-default workflow for built-in package overrides
  - install, uninstall, validation, variable, tag, category, and description editing
  - visual variable editor for required/sensitive/defaulted variables
  - contextual create/edit drawer so package management does not dominate the page layout
  - simple `{{ variable_name }}` command parameterization with execution-time inputs
  - sensitive variables resolved from Credential Manager references at runtime
  - persisted job commands redacted when sensitive runtime values are injected
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
  - action, package, and raw command steps
  - structured visual step cards for package, action, deployment placeholder, and script placeholder steps
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
  - credential-backed environment variables resolved server-side at deploy time
  - redacted deployment command history when secrets are injected into `.env`
  - configurable remote base path for deployment project directories
  - generated remote compose file name is `docker-compose.yaml`
  - deployment target and revision persistence
  - deploy/redeploy/restart/stop/status/log operations through Jobs
  - deployment edit and delete API/UI
  - operational deployment cards with runtime status, target host, ports, compose source, uptime, health state, and synchronization state
  - centered responsive create/edit deployment drawer so forms appear only when requested
  - inspect and log panels for operational feedback
  - shared target selector and request-shape support for future bulk deployment fanout while preserving current single-target execution
- Monitoring foundation:
  - Prometheus HTTP API health check
  - basic per-server CPU, memory, disk, and uptime query support
  - Grafana deep-link generation when configured
  - Prometheus, Grafana, and Loki quick links for hybrid monitoring workflows
  - provider readiness and connection status derived from enabled Integration records
  - partial provider failures return status/error metadata without crashing the monitoring overview
  - monitoring summary is currently integration-adjacent, not a complete observability control plane
- Linux identity orchestration:
  - reusable Linux user and group records
  - SSH public key records
  - filesystem permission templates
  - user/group/key/permission replication across selected inventory hosts
  - existing Linux user and group discovery through Jobs
  - managed user edit/delete and managed group edit/delete flows
  - optional Credential Manager password selection when creating/updating Linux users; passwords are applied with `chpasswd` and redacted from Job history
  - live user group inspection per host using `id -nG`
  - live group member inspection per host, combining supplementary members from `getent group` with primary-group members from `getent passwd`
  - per-host execution history through Jobs and identity execution records
  - guided access profiles for administrator, deployment, Docker, log viewer, read-only, and service-account workflows
  - distro-aware administrator group resolution
  - operational group presets and group discovery
  - permission presets, rwx matrix UI, and generated command previews
  - protected `root` account exclusion from discovery, creation/adoption, direct inspection, and remote lifecycle operations
  - password expiration and login-shell disable actions for account lifecycle workflows
- Host detail operational hub:
  - tabbed host context for Overview, Metrics, Terminal, Files, Deployments, Jobs, Workflows, Packages, Profiles, and Identity
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

Integration records provide a persisted configuration surface for provider and monitoring systems. The normal frontend path is now schema-driven instead of raw JSON editing. Operators select Proxmox, Prometheus, Grafana, or the Tailscale placeholder, then configure URL, auth mode, credential references, SSL verification, and timeout fields.

The backend still stores a JSON `config` payload for compatibility, but validates known integration shapes and expects secrets to flow through credential references. Advanced JSON remains available only as an override surface.

Runtime consumption of persisted integrations is uneven. Proxmox adapters can resolve an enabled persisted Proxmox integration and fall back to environment variables. Monitoring still reads Prometheus, Grafana, and Loki URLs from environment-backed settings, so adding Prometheus/Grafana/Loki records in the Integrations UI does not yet activate Monitoring.

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
- bootstrap profile and package selections

Blueprints intentionally do not lock per-machine identity values such as VM name, VMID, cloud-init hostname, or static IP/CIDR. Operators select a blueprint, fill in the unique host identity/network fields, then provisioning registers Inventory before running bootstrap profiles/packages through Jobs.

Provisioning is currently QEMU VM-focused. Proxmox discovery and lifecycle views can represent guest type, including LXC, but the provisioning clone/configure path uses QEMU endpoints and cloud-init VM configuration. CT/LXC provisioning, CT shell, and CT lifecycle workflows still need explicit implementation.

### Inventory Synchronization and CMDB Lifecycle

Inventory now reconciles provider discovery with orchestration ownership:

```text
Proxmox discovery -> synchronization status -> optional import -> Inventory authority -> Jobs / Profiles / Packages
```

Discovered VMs are shown as unmanaged until an operator imports them. Import creates an Inventory record with Proxmox provider linkage, SSH metadata, lifecycle state, source metadata, and synchronization status. Reconciliation updates linked inventory records as synced, mismatched, orphaned, or archived without destroying provider-side infrastructure.

Inventory deletion now performs reference cleanup before removing the active server record. It clears provisioning request links, virtual machine links, workflow target links, and deployment target rows where applicable. If historical constraints prevent a hard delete, NexusOps archives the inventory record instead of destroying history.

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

Important gap: this foundation models `hypervisor` nodes, but Proxmox host/node management is not first-class yet. NexusOps still discovers Proxmox nodes from the active Proxmox integration and does not automatically register each Proxmox cluster node as an Inventory-managed hypervisor with host lifecycle, monitoring, credentials, and migration/replacement workflows. This is the next required convergence point.

### UX Consistency and Operational Workspace

Orchestration pages now share common target-selection and contextual-workflow patterns:

```text
TargetSelector -> selected inventory host(s) -> module-specific request -> existing service pipeline
```

Packages, Profiles, Automations, Jobs, and Deployments use the shared selector for consistent search, filtering, single-target selection, and bulk-target intent. Deployments accept bulk target IDs in the request shape but still execute the current single-target Docker Compose service path until distributed orchestration queueing is implemented.

Create/edit/configuration workflows are now treated as secondary contextual actions instead of permanent CRUD panels:

```text
entity list / explorer -> operational cards or tables -> ContextDrawer for create/edit/configure
```

The shared `ContextDrawer` component provides the standard right-size overlay shell for Inventory host import, Credential create/edit, custom Job action create/edit, Automation create/edit, Package create/edit, Profile create/edit, Integration add/edit, and provisioning blueprint/batch actions. The Deployments drawer was centered and kept as the primary visual baseline for service-style operational workflows.

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

### Review Findings on 2026-05-19

The latest review confirmed several important boundaries:

- Integration records for Prometheus/Grafana/Loki can be created, tested, and consumed by Monitoring at runtime.
- Monitoring remains a quick summary and external-link surface rather than a complete observability workspace.
- The single VM provisioning wizard still dominates the Provisioning page and should be moved into the contextual workspace pattern.
- Provisioning blueprints should become workflow/automation operations rather than Profile steps, because profiles execute against already-existing Inventory targets.
- Automations currently execute actions, packages, and profiles only; provisioning and deployment automation are not wired yet.
- CT/LXC support is partial: discovery/lifecycle visibility exists, but QEMU VM provisioning remains the implemented path.
- Managed-node lifecycle foundations exist for VMs, LXCs, physical hosts, and hypervisors, but Proxmox host/node registration and host-level management still need implementation.

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
- Provisioning blueprints persist reusable provisioning defaults while keeping Proxmox VM templates as the provider-side base image.
- Batch provisioning creates a parent batch record and normal child provisioning requests. Each generated VM still goes through the existing Proxmox clone, cloud-init, SSH readiness, Inventory registration, and optional bootstrap flow.
- Docker Compose deployments reuse Jobs for deploy/redeploy/restart/stop/status/logs and resolve credential-backed env values server-side.
- Deployment API reads include derived operational metadata, but execution still flows through the existing Jobs pipeline.
- Frontend create/edit/configuration workflows should prefer `ContextDrawer` or focused modals over permanent page-level forms.
- Remote Access reuses Inventory as the target boundary and Credential Manager resolution for SSH material; it does not accept arbitrary host targets or expose credentials to the frontend.
- RBAC user management is implemented under the auth module and remains admin-only through backend route dependencies.
- Inventory deletion cleanup is owned by `InventoryService`; it clears active references without hard-deleting historical job logs.
- Adapter packages are canonicalized under `backend/app/adapters/`.
- SSH has a concrete Paramiko adapter for key/password command execution.
- Frontend is feature-based under `frontend/src/features/`.
- Shared shell, routing, API client, and layout code remain outside feature folders.

## Current Technical Debt

- Execution module is still a placeholder.
- Authentication, authorization, and admin user lifecycle are implemented for local users. Google SSO, OIDC, LDAP, SAML, MFA, API keys, and fine-grained permissions are not implemented.
- Workflow chaining is still implicit. Provisioning can bootstrap profiles/packages, but deployment-as-a-profile-step is not fully executed yet.
- Legacy inline SSH passwords/private key paths still exist for backward compatibility and local MVP use; shared Credential Manager records are the preferred path for reusable secrets.
- Integration configs are structured and credential-reference aware, but they are not a secrets vault yet.
- No frontend test framework is configured yet.
- No CI pipeline is defined in the repo.
- Inventory tests use SQLite fixtures; PostgreSQL migration behavior is validated manually, not in automated CI.
- Proxmox live validation depends on local environment variables and a reachable Proxmox host.
- Proxmox credentials are intentionally not persisted in source-controlled files.
- Proxmox lifecycle actions currently return accepted task IDs but do not poll task completion.
- Proxmox lifecycle action audit persistence is not implemented yet.
- Jobs still execute synchronously inside the JobService call, but scheduled automations now dispatch through WorkflowRuns and an in-process async queue.
- Profiles still run sequentially inside ProfileService, but automation-triggered profile runs now persist workflow steps.
- Provisioning still needs the deeper background refactor so each clone/config/bootstrap phase is driven fully by WorkflowRun steps.
- Provisioning blueprints do not yet discover valid Proxmox storage targets per node; extra disks currently rely on operator-entered storage names.
- Deployment logs are pulled on demand from Docker Compose and are not yet indexed as first-class log records.
- Docker deployment steps can execute through `ProfileService`, but richer blueprint-style deployment composition still needs refinement.
- No centralized domain identity provider. Identity is Linux orchestration only; LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, and login federation are intentionally out of scope.
- Identity discovery reads live Linux state through Jobs and does not yet persist per-host user/group membership snapshots as first-class inventory records.
- Existing `docs/architecture.md` is older and less precise than the newer files in `docs/architecture/`.
- Runtime adapter support from persisted integration records is partial; Proxmox and Monitoring can resolve active integration records, while future adapters still need deeper runtime integration.
- Proxmox cluster hosts are not yet managed-node first-class citizens. They can be manually represented as `hypervisor` inventory records, but discovery does not yet create/update hypervisor nodes and Proxmox integration failover/replacement workflows are not implemented.
- Provisioning still presents the single VM wizard as a large page section; it needs the same contextual workflow treatment as batch provisioning and blueprint actions.
- Provisioning blueprints are not yet first-class Workflow/Automation operations.
- CT/LXC provisioning and CT/LXC execution-target management are not implemented end-to-end.
- Remote shell WebSocket authentication uses the current JWT as a query parameter for MVP browser compatibility; a short-lived scoped remote-access token is still planned.
- Refresh tokens are revoked through token-version changes, but refresh-token rotation/reuse detection is not implemented yet.

## Current Safety Boundary

The platform can authenticate local NexusOps users, enforce coarse RBAC boundaries, revoke existing JWT sessions through token-version changes, mutate NexusOps-owned inventory data, import and reconcile discovered Proxmox VMs into Inventory, request controlled Proxmox VM lifecycle actions, provision VMs from Proxmox templates, edit reusable automation templates, execute commands/actions/packages/profiles against inventory-managed Linux hosts over SSH, provide backend-mediated shell/file access to inventory-managed Linux hosts, resolve encrypted runtime secrets server-side, deploy Docker Compose projects, query Prometheus metrics, link out to Prometheus/Grafana/Loki, and replicate non-root Linux identity state. Inventory deletion and archival are CMDB operations only; they do not destroy Proxmox VMs. Template reset restores NexusOps defaults only; it does not alter historical Jobs. The platform does not expose VM deletion, ISO installation, Kubernetes, Terraform execution, SSO/federated login, arbitrary SSH targets, raw Proxmox consoles, Docker/container shells, root account orchestration, or arbitrary provider-side infrastructure mutation.
