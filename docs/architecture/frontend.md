# Frontend Architecture

## Overview

The frontend is a React, TypeScript, Vite, and TailwindCSS application. It is organized by feature under `frontend/src/features` and uses React Router for page routing.

The frontend currently implements:

- inventory dashboard
- server creation form
- server list table/card views
- Proxmox infrastructure dashboard
- Jobs page with operational actions, raw command execution, history, and result viewer
- Package definitions page
- Infrastructure profiles page with apply workflow and execution visibility
- VM provisioning page with template, cloud-init, static networking, bootstrap, and history sections
- placeholder pages for future modules

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
- `/infrastructure` read-only Proxmox visibility
- `/jobs` SSH-backed operations and job history
- `/packages` package definition catalog
- `/profiles` reusable infrastructure profile templates
- `/provisioning` Proxmox template provisioning workflow
- `/provisioning` placeholder
- `/deployments` placeholder
- `/packages` placeholder
- `/monitoring` placeholder
- `/profiles` placeholder

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
- responsive table/cards
- summary metric cards

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
- stdout/stderr result viewer
- responsive table/cards

## Packages Frontend Flow

```text
PackagesPage
  -> packagesApi
  -> shared apiClient
  -> FastAPI /api/v1/packages
```

The Packages UI displays reusable package definitions with install commands, validation commands, tags, category, and supported OS metadata. It also supports adding custom package definitions, deleting custom definitions, selecting a target host, and running a package through Jobs.

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
- profile builder using package/action references
- target inventory host selector
- apply profile action
- generated job sequence visibility

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
