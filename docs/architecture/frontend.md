# Frontend Architecture

## Overview

The frontend is a React, TypeScript, Vite, and TailwindCSS application. It is organized by feature under `frontend/src/features` and uses React Router for page routing.

The frontend currently implements:

- inventory dashboard
- server creation form
- server list table/card views with edit, archive, and delete actions
- Proxmox infrastructure dashboard
- Proxmox import/reconciliation visibility
- Jobs page with operational actions, raw command execution, history, and result viewer
- Package definitions page
- Infrastructure profiles page with apply workflow and execution visibility
- Credential Manager page for reusable encrypted secrets and shared SSH accounts
- shared execution variable modal for normal inputs and credential-backed sensitive inputs
- visual variable definition editor for packages and profiles
- VM provisioning page with template, cloud-init, static networking, bootstrap, and history sections
- host detail and Proxmox node detail pages
- integrations settings page
- deployment and monitoring foundation pages

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
- `/infrastructure` Proxmox visibility, lifecycle controls, and inventory synchronization
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

## API Client

The shared API client is `frontend/src/lib/api/client.ts`.

It uses Axios with:

- `VITE_API_BASE_URL`
- JSON content headers
- reusable API error formatting

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
- VM table on desktop
- VM cards on mobile
- loading state
- API error state
- retry action
- managed/unmanaged synchronization badges
- import action for unmanaged discovered VMs
- reconciliation action for linked inventory records

Discovered Proxmox VMs are not automatically imported. Operators supply Inventory execution metadata, including IP address and SSH username, before a VM becomes a managed target.

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

- target inventory host selector
- predefined operational action selector grouped by category
- destructive action confirmation
- raw command execution form
- persisted job history
- tabbed stdout/stderr/command/metadata result viewer
- larger expandable output inspector
- copy and wrap controls for command output
- responsive table/cards

## Identity Frontend Flow

```text
IdentityPage
  -> identityApi
  -> shared apiClient
  -> FastAPI /api/v1/identity
```

The Identity UI includes Linux user creation/replication, group creation/membership replication, SSH public key deployment/revocation, lightweight chmod/chown permission application, and a primary multi-host target selector. Replication results show per-host success/failure details from the Jobs-backed fanout response.

The default Identity experience is guided rather than raw-Linux-first:

- access profile selector configures shell, sudo, and recommended groups
- shell presets hide raw shell paths unless advanced mode is enabled
- sudo options are shown as operational choices such as password-required sudo and passwordless admin access
- group presets explain common operational groups and use cases
- permission presets and an owner/group/others rwx matrix generate octal chmod values
- generated command preview panels show the Linux operations before replication
- replication target selection supports search, select all, clear, and selected host badges

Advanced mode keeps raw shell path, raw group selection, recursive chmod/chown, and raw octal controls available for power users.

## Packages Frontend Flow

```text
PackagesPage
  -> packagesApi
  -> shared apiClient
  -> FastAPI /api/v1/packages
```

The Packages UI displays reusable package definitions with install, uninstall, validation, variable, tag, category, and supported OS metadata. It supports adding custom package definitions, editing built-in working copies, cloning templates, restoring modified built-ins to defaults, deleting custom definitions, selecting target hosts, bulk execution, and running packages through Jobs.

Package variable definitions are edited through a visual editor instead of raw JSON. Before execution, a modal displays the execution preview, normal runtime inputs, and credential dropdowns for sensitive variables. Sensitive values are sent as `credential_refs`, not plaintext.

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
- target inventory host selector
- apply profile action
- generated job sequence visibility

Profile steps are authored as structured JSON through visual cards. The frontend still preserves backend compatibility with older `kind/reference_id` step shape, but operators no longer edit compact step text directly.

## Credentials Frontend Flow

```text
CredentialsPage
  -> credentialsApi
  -> shared apiClient
  -> FastAPI /api/v1/credentials
```

The Credentials UI includes:

- credential list with type and scope badges
- create credential form
- type-aware username behavior
- masked secret display only
- delete credential action

Secret material is submitted once and never shown again after creation.

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
- raw config preview for local MVP use
- create integration form
- Proxmox, Prometheus, and Grafana presets
- connection test action

Integration configs are currently local MVP metadata and should not be treated as production-grade secret storage.

## Provisioning Frontend Flow

```text
ProvisioningPage
  -> provisioningApi
  -> shared apiClient
  -> FastAPI /api/v1/vms
```

The Provisioning UI includes:

- Proxmox template selector
- VM sizing and network bridge inputs
- cloud-init username/password/SSH key inputs
- static IP/CIDR, gateway, and DNS inputs
- profile/package bootstrap selectors
- provisioning lifecycle history cards

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

- `ExecutionVariablesModal` for package/profile execution inputs and credential selection
- `VariableDefinitionEditor` for visual variable definition editing

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
