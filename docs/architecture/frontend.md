# Frontend Architecture

## Overview

The frontend is a React, TypeScript, Vite, and TailwindCSS application. It is organized by feature under `frontend/src/features` and uses React Router for page routing.

The frontend currently implements:

- inventory dashboard
- contextual host import workflow for externally provisioned or bare-metal systems
- server list table/card views with edit, archive, and delete actions
- Proxmox infrastructure dashboard
- Proxmox import/reconciliation visibility
- Jobs page with operational actions, raw command execution, history, and result viewer
- Package definitions page with contextual create/edit drawer workflow
- Infrastructure profiles page with contextual create/edit drawer workflow, apply workflow, and execution visibility
- Credential Manager page for reusable encrypted secrets and shared SSH accounts with contextual create/edit drawer workflow
- shared execution variable modal for normal inputs and credential-backed sensitive inputs
- visual variable definition editor for packages and profiles
- VM provisioning page with provider template selection, NexusOps blueprints, cloud-init, static networking, disk controls, bootstrap, and history sections
- host detail and Proxmox node detail pages
- integrations settings page
- deployment runtime dashboard with drawer-based create/edit and per-target execution state
- monitoring readiness board for telemetry availability, degraded nodes, exporters, stale metrics, and provider health
- shared target selection across orchestration pages
- admin Users & RBAC page
- shared contextual drawer shell for secondary create/edit/configuration workflows
- shared operational components for page-level actions, runtime badges, status pills, toolbars, and collapsible action panels
- unified Host Tools workspace with files/editor and persistent resizable terminal
- route-level lazy loading/code splitting

## Application Shell

Key files:

- `frontend/src/main.tsx`
- `frontend/src/app/App.tsx`
- `frontend/src/app/router.tsx`
- `frontend/src/components/layout/AppLayout.tsx`
- `frontend/src/components/layout/PageHeader.tsx`

`AppLayout` provides the persistent navigation and page content area. Routes are registered in `router.tsx`.

Current main routes:

- `/` inventory
- `/inventory/:id` host detail
- `/infrastructure` Proxmox visibility, import, and inventory synchronization
- `/infrastructure/credentials` credential manager
- `/infrastructure/nodes/:id` Proxmox node detail
- `/jobs` SSH-backed operations and job history
- `/identity` Linux user, group, SSH key, sudo, and permission replication
- `/packages` package definition catalog
- `/profiles` reusable infrastructure profile templates
- `/provisioning` Proxmox template provisioning workflow
- `/deployments` Docker Compose deployment workflows
- `/monitoring` Prometheus/Grafana monitoring foundations
- `/settings/integrations` integration records and connection tests
- `/settings/users` admin-only user and RBAC lifecycle management

## Feature-Based Structure

Implemented feature folders follow this structure:

```text
src/features/<feature>/
  api/
  components/
  hooks/
  pages/
  types/
  utils/
```

Inventory, Proxmox, Jobs, Packages, and Profiles follow this pattern. Placeholder modules currently use simple page components only.

## Operational Workspace UX

The frontend is moving away from static CRUD pages and permanently visible create/edit forms. The current interaction model is:

```text
entity list / explorer -> selected operational context -> contextual drawer or modal for create/edit/configure
```

Creation is treated as a secondary workflow. Entity management, runtime state, target selection, cards, tables, and logs remain the primary page content.

The reusable drawer primitive is:

- `frontend/src/components/ContextDrawer.tsx`

It provides consistent:

- centered responsive overlay layout
- fixed header with title, description, and close action
- scrollable body for long operational forms
- width presets for compact, standard, and large workflows

The deployment dashboard remains the strongest visual and interaction reference for operational cards, runtime controls, and contextual create/edit. Inventory edit modal behavior remains the reference for preserving page context while editing a selected entity.

Shared operational primitives live under `frontend/src/components/operations/` and standardize:

- page-level actions in `PageHeader`
- runtime and lifecycle badges
- compact operational toolbars
- collapsible action sections for large forms
- consistent status pills for managed nodes, telemetry, and orchestration state

## API Client

The shared API client is `frontend/src/lib/api/client.ts`.

It uses Axios with:

- `VITE_API_BASE_URL`
- JSON content headers
- reusable API error formatting
- bearer token injection from session-scoped auth storage
- automatic refresh attempt on expired access tokens
- token-storage abstraction preserved for future migration to safer refresh-token transport

Feature folders define their own API functions and types, but they use the shared client for transport.

## Inventory Frontend Flow

```text
InventoryDashboardPage
  -> useServers
  -> serversApi
  -> shared apiClient
  -> FastAPI /api/v1/servers
```

Inventory frontend components:

- `CreateServerForm`
- `ServerList`
- `ServerBadges`
- `InventoryDashboardPage`

The inventory UI includes:

- loading skeletons
- API error display
- required field validation
- SSH port validation
- SSH authentication method selection
- optional private key path input
- password input for password-auth hosts
- shared credential selector for credential-backed SSH execution
- responsive table/cards
- summary metric cards
- lifecycle and synchronization badges
- secondary "Import Existing Host" drawer workflow for bare-metal, unmanaged, or externally provisioned hosts
- edit, archive, and delete workflows

Inventory deletion and archival are CMDB operations only. They do not destroy Proxmox VMs.

## Proxmox Frontend Flow

```text
InfrastructurePage
  -> useProxmoxDashboard
  -> proxmoxApi
  -> shared apiClient
  -> FastAPI /api/v1/proxmox/dashboard
```

Proxmox frontend components:

- `SummaryCards`
- `NodeCards`
- `VmTable`
- `StatusBadge`

The Proxmox UI includes:

- cluster summary cards
- node cards
- visually distinct hypervisor, VM, and LXC sections
- VM/LXC tables on desktop
- VM/LXC cards on mobile
- loading state
- API error state
- retry action
- managed/unmanaged synchronization badges
- import action for unmanaged discovered VMs
- import/sync handling for discovered LXCs
- first-class hypervisor host cards and links into managed-node operations
- experimental inventory synchronization action labeled as discovered-guest synchronization rather than a finished desired-state reconciliation workflow

Discovered Proxmox guests are not automatically promoted into active orchestration targets without Inventory metadata. Operators supply execution metadata, including IP address and SSH username when needed, before a VM or LXC becomes a managed target. Hypervisor hosts are reconciled from active Proxmox integrations as `hypervisor` managed nodes and can be archived or decommissioned from active orchestration without erasing history.

## Jobs Frontend Flow

```text
JobsPage
  -> jobsApi
  -> shared apiClient
  -> FastAPI /api/v1/jobs
```

Jobs frontend components:

- `OperationalActionsPanel`
- `RunCommandPanel`
- `JobsTable`
- `JobResultViewer`
- `JobStatusBadge`

The Jobs UI includes:

- shared target inventory host selector with single/bulk modes and filters
- predefined operational action selector grouped by category
- destructive action confirmation
- raw command execution form
- persisted job history
- tabbed stdout/stderr/command/metadata result viewer
- larger expandable output inspector
- server-generated sanitized command snapshots in job history
- copy and wrap controls for command output
- responsive table/cards
- contextual drawer workflow for custom operational action create/edit

## Identity Frontend Flow

```text
IdentityPage
  -> identityApi
  -> shared apiClient
  -> FastAPI /api/v1/identity
```

The Identity UI includes Linux user creation/replication, group creation/membership replication, discovered user/group adoption, SSH public key deployment/revocation, lightweight chmod/chown permission application, password expiration, login-shell disable, and a primary multi-host target selector. Replication results show per-host success/failure details from the Jobs-backed fanout response.

The default Identity experience is guided rather than raw-Linux-first:

- access profile selector configures shell, sudo, and recommended groups
- shell presets hide raw shell paths unless advanced mode is enabled
- sudo options are shown as operational choices such as password-required sudo and passwordless admin access
- group presets explain common operational groups and use cases
- permission presets and an owner/group/others rwx matrix generate octal chmod values
- generated command preview panels show the Linux operations before replication
- replication target selection supports search, select all, clear, and selected host badges
- local create/adopt remains available without selected targets, while remote sync, discovery, inspection, and replication clearly require selected targets
- password/SSH-password credentials can be selected for sudo-backed execution during user and group replication
- discovered host-origin chips appear in user/group context so operators can tell where live Linux state was observed

Advanced mode keeps raw shell path, raw group selection, recursive chmod/chown, and raw octal controls available for power users.

The `root` account is intentionally hidden from discovery and blocked from NexusOps identity orchestration. Identity remains Linux infrastructure orchestration, not centralized authentication or privileged root-account ownership.

Current UI debt: Identity still needs a clearer target-first matrix for large environments. Managed records, discovered host observations, and drift/reconciliation status should become easier to distinguish as manual testing findings mature.

## Packages Frontend Flow

```text
PackagesPage
  -> packagesApi
  -> shared apiClient
  -> FastAPI /api/v1/packages
```

The Packages UI displays reusable package definitions with install, uninstall, validation, variable, tag, category, and supported OS metadata. It supports adding custom package definitions, editing built-in working copies, cloning templates, restoring modified built-ins to defaults, deleting custom definitions, shared single/bulk target selection, bulk execution, and running packages through Jobs.

Package variable definitions are edited through a visual editor instead of raw JSON. Before execution, a modal displays the execution preview, normal runtime inputs, and credential dropdowns for sensitive variables. Sensitive values are sent as `credential_refs`, not plaintext.

Package create/edit now uses `ContextDrawer`; the package catalog, target selector, and execution context remain visible behind the workflow.

## Profiles Frontend Flow

```text
ProfilesPage
  -> profilesApi
  -> shared apiClient
  -> FastAPI /api/v1/profiles
```

The Profiles UI includes:

- profile cards
- ordered step display
- profile builder using visual step cards for package/action/deployment/script step types
- editable built-in working copies
- clone and restore-default workflows
- move up/down and drag-and-drop step ordering preview
- visual variable definition editor
- execution modal with runtime inputs and credential dropdowns for sensitive variables
- shared target inventory host selector
- apply profile action
- generated job sequence visibility

Profile steps are authored as structured JSON through visual cards. The frontend still preserves backend compatibility with older `kind/reference_id` step shape, but operators no longer edit compact step text directly.

Profile create/edit now uses `ContextDrawer`; the profile explorer, target selection, result panels, and execution context remain primary page content.

## Credentials Frontend Flow

```text
CredentialsPage
  -> credentialsApi
  -> shared apiClient
  -> FastAPI /api/v1/credentials
```

The Credentials UI includes:

- credential list with type and scope badges
- contextual create/edit drawer
- type-aware username behavior
- masked secret display only
- delete credential action

Secret material is submitted once and never shown again after creation. When editing a credential, operators may update metadata without replacing the stored secret, or submit replacement secret material through the drawer.

## Integrations Frontend Flow

```text
IntegrationsPage
  -> integrationsApi
  -> shared apiClient
  -> FastAPI /api/v1/integrations
```

The Integrations UI includes:

- configured integration cards
- enabled/disabled badges
- contextual add/edit integration drawer
- Proxmox, Prometheus, Grafana, and Tailscale placeholder presets
- auth mode selection for URL-only, username/password, token, and username/token modes
- credential references for secrets
- SSL verification and timeout controls
- advanced JSON override for local MVP escape hatches
- connection test action

Integration configs are generated into the existing JSON payload for DB compatibility. Secrets should use credential references and should not be placed in config JSON.

## Provisioning Frontend Flow

```text
ProvisioningPage
  -> provisioningApi
  -> shared apiClient
  -> FastAPI /api/v1/vms
```

The Provisioning UI includes:

- provisioning blueprint selector
- contextual blueprint action drawer for save, update, clone, and delete
- contextual batch provisioning drawer
- collapsible VM and LXC provisioning action panels
- Proxmox template selector
- Proxmox LXC template selector
- VM sizing and network bridge inputs
- root disk and additional disk controls
- cloud-init username/password/SSH key inputs
- static IP/CIDR, gateway, and DNS inputs
- profile/package bootstrap selectors
- provisioning lifecycle history cards

Blueprints fill the fixed defaults while keeping VM name, VMID, cloud-init hostname, and static IP/CIDR editable for each run.

The VM and LXC provisioning workflows are available as operational actions without permanently occupying the full page. Advanced storage, bootstrap, and batch provisioning settings are collapsed or drawer-based so the page reads as an operational workspace instead of a wall of forms.

## Deployments Frontend Flow

```text
DeploymentsPage
  -> deploymentsApi
  -> shared apiClient
  -> FastAPI /api/v1/deployments
```

The Deployments UI is now an operational service dashboard rather than a permanently visible create form. It includes:

- service-style deployment cards
- runtime status, health, sync, uptime, target hosts, per-target state, duration, ports, compose source, and credential-ref indicators
- direct start, stop, restart, redeploy, inspect, logs, edit, and delete actions
- status filtering
- inspect and log output panels
- drawer-based create/edit workflow
- Docker Compose content, non-secret env content, and credential-backed env variable mappings
- shared target selection in the drawer
- execution history and output summaries for deployment runs

Credential-backed env mappings send only credential IDs to the backend; secret values are resolved server-side.

## Host Tools Frontend Flow

```text
HostToolsPage
  -> remoteAccessApi
  -> shared apiClient for shell-token and SFTP requests
  -> browser WebSocket for shell stream
```

The Host Tools UI includes:

- file browser and editor for inventory-managed hosts
- hash-checked file writes through the backend
- operator/admin role gating
- shell startup through a short-lived scoped token request before the WebSocket opens
- resizable terminal area that refits xterm as the panel changes size

The frontend no longer sends the long-lived access token directly as the shell WebSocket query token.

Deployments now pass both `target_server_id` and optional `target_server_ids` in the request shape. The backend persists all selected targets, executes per-target Jobs sequentially in the MVP, returns per-target execution state, and polls persisted runtime state so operators can see succeeded, failed, partial, degraded, drifted, and stale outcomes without reading backend logs.

## Monitoring Frontend Flow

```text
MonitoringPage
  -> monitoringApi
  -> shared apiClient
  -> FastAPI /api/v1/monitoring
```

The Monitoring UI is an operational observability readiness board. NexusOps shows telemetry provider health, observable/degraded node counts, missing metrics/logs, stale telemetry, exporter detection, scrape target health, and per-node readiness reasons. Advanced dashboards and log exploration stay in the external observability stack.

The page exposes:

- Prometheus API health
- Prometheus scrape/exporter readiness
- Loki reachability and log availability where available
- optional Grafana deep links when configured
- per-host CPU, memory, disk, and uptime summaries
- per-node monitoring state such as `monitoring_ready`, `metrics_missing`, `logs_missing`, `stale_metrics`, `exporter_missing`, and `monitoring_partial`

NexusOps does not generate Grafana dashboards, assume dashboard-per-node URLs, or manage Loki exploration views. Prometheus, Loki, and Grafana are telemetry providers; NexusOps owns operational readiness and infrastructure awareness.

## Types, Hooks, and Utilities

Frontend API response types live in each feature's `types/` folder.

Hooks own async data loading state:

- `useServers`
- `useProxmoxDashboard`

Utilities own small feature-specific formatting and label helpers.

## TailwindCSS

Tailwind is configured through:

- `frontend/tailwind.config.ts`
- `frontend/postcss.config.js`
- `frontend/src/styles/global.css`

The UI uses utility classes directly. Shared visual primitives are minimal and feature components remain explicit.

Shared UI components now include:

- `ContextDrawer` for reusable contextual create/edit/configure workflows
- `PageHeader` action slots for consistent page-level actions
- `OperationalComponents` for runtime badges, status pills, action toolbars, and collapsible action panels
- `ExecutionVariablesModal` for package/profile execution inputs and credential selection
- `VariableDefinitionEditor` for visual variable definition editing
- `TargetSelector` for searchable, filterable single/bulk inventory target selection

## Tooling

Frontend tooling currently includes:

- TypeScript build through `tsc -b`
- Vite production build
- ESLint 9 flat config
- Prettier config
- TailwindCSS

Validation command:

```bash
npm run lint
npm run build
```

## Frontend/Backend Communication

The frontend expects the backend API at `VITE_API_BASE_URL`, defaulting to:

```text
http://localhost:8000/api/v1
```

The backend CORS configuration allows the local Vite origin:

```text
http://localhost:5173
```
