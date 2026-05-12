# Sprint 3: VM Lifecycle Control

## Goal

Add a narrow infrastructure control layer for Proxmox VM lifecycle operations while preserving operational safety and avoiding provisioning scope.

Implemented lifecycle actions:

- start VM
- stop VM
- reboot VM
- shutdown VM

Not implemented:

- VM creation
- VM deletion
- provisioning
- Terraform
- cloud-init
- SSH execution
- Docker deployment
- realtime updates
- background workers

## Backend Implementation

The existing Proxmox adapter and service were extended rather than duplicated.

Backend changes:

- `ProxmoxAdapter` now declares lifecycle action methods.
- `HttpProxmoxAdapter` calls Proxmox status action endpoints.
- `ProxmoxService` resolves VM node/type from the current VM list before dispatching actions.
- Service-level validation prevents invalid operations before API dispatch.
- Router endpoints map validation failures to frontend-friendly HTTP responses.

## API Endpoints

Lifecycle endpoints:

```text
POST /api/v1/proxmox/vms/{vm_id}/start
POST /api/v1/proxmox/vms/{vm_id}/stop
POST /api/v1/proxmox/vms/{vm_id}/reboot
POST /api/v1/proxmox/vms/{vm_id}/shutdown
```

Validation behavior:

- missing VM: `404`
- invalid state transition: `409`
- missing Proxmox configuration: `503`
- Proxmox/API connectivity failure: `502`

## Frontend Implementation

The existing Infrastructure dashboard now includes VM lifecycle buttons in the VM table/cards.

UI behavior:

- stopped VMs show `Start` as the valid action.
- running VMs show `Shutdown`, `Reboot`, and `Stop` as valid actions.
- invalid actions are disabled.
- stop, reboot, and shutdown require browser confirmation.
- each VM row/card tracks its own action loading state.
- success/error notifications are shown.
- dashboard state refreshes after accepted actions.

## Operational Safety

Safety decisions:

- action endpoints accept only `vm_id`; node/type are resolved server-side.
- the service validates VM existence before dispatch.
- the service validates current VM status before dispatch.
- no provisioning or deletion methods were added.
- no background task polling is implemented yet.

## Validation

Validated locally:

- backend tests passed
- frontend lint passed
- frontend build passed
- Proxmox dashboard still loads real cluster data
- missing VM lifecycle action returns `404`
- shutdown stopped VM returns `409`
- inventory CRUD still works
- Infrastructure frontend route loads

## Status

Sprint 3 is implemented. The next stabilization step should be action audit persistence and task status polling before expanding infrastructure control further.
