# Sprint 2: Proxmox Visibility

## Goal

Add infrastructure visibility through Proxmox without implementing provisioning, deletion, SSH execution, or Docker deployment. This sprint later gained a narrow lifecycle control layer for start, stop, reboot, and shutdown.

## Backend Implementation

The Proxmox integration uses the canonical adapter architecture.

Implemented adapter files:

- `backend/app/adapters/proxmox/base.py`
- `backend/app/adapters/proxmox/http.py`

Implemented module files:

- `backend/app/modules/proxmox/router.py`
- `backend/app/modules/proxmox/service.py`
- `backend/app/modules/proxmox/schemas.py`

## API Endpoints

Proxmox endpoints are registered under:

```text
/api/v1/proxmox
```

Implemented endpoints:

- `GET /api/v1/proxmox/nodes`
- `GET /api/v1/proxmox/vms`
- `GET /api/v1/proxmox/vms/{node}/{vm_type}/{vm_id}/status`
- `GET /api/v1/proxmox/cluster/summary`
- `GET /api/v1/proxmox/dashboard`
- `POST /api/v1/proxmox/vms/{vm_id}/start`
- `POST /api/v1/proxmox/vms/{vm_id}/stop`
- `POST /api/v1/proxmox/vms/{vm_id}/reboot`
- `POST /api/v1/proxmox/vms/{vm_id}/shutdown`

## Frontend Implementation

Frontend Proxmox visibility code lives under:

```text
frontend/src/features/proxmox/
```

Implemented structure:

- `api/proxmoxApi.ts`
- `components/NodeCards.tsx`
- `components/StatusBadge.tsx`
- `components/SummaryCards.tsx`
- `components/VmTable.tsx`
- `hooks/useProxmoxDashboard.ts`
- `pages/InfrastructurePage.tsx`
- `types/proxmox.ts`
- `utils/format.ts`

## User Interface

The infrastructure page displays:

- cluster summary cards
- node cards
- VM table on desktop
- VM cards on mobile
- loading state
- API error state
- retry action
- VM lifecycle action buttons
- confirmation prompts for stop, reboot, and shutdown
- per-VM action loading state
- success/error notifications

## Configuration

The adapter reads Proxmox configuration from environment variables:

- `PROXMOX_API_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_VERIFY_SSL`
- `PROXMOX_TIMEOUT_SECONDS`

Token secrets are not committed to source-controlled files.

## Validation

The integration was validated against a real Proxmox host using a read-only API token.

Observed validation result:

- 1 node discovered: `hellgate`
- 12 VMs/containers discovered
- invalid credentials return an API error
- unreachable host returns an API error
- frontend route `/infrastructure` loads
- inventory CRUD remained functional
- lifecycle safety paths were validated with 404 for missing VMs and 409 for invalid stopped-VM operations

## Status

Sprint 2 is implemented as a visibility and controlled lifecycle layer. It prepares the foundation for future inventory synchronization and audit persistence. It does not create, delete, or provision infrastructure.
