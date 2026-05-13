# Sprint 6: Proxmox Template Provisioning MVP

## Goal

Implement the first controlled VM provisioning workflow using Proxmox templates, cloud-init, static IP assignment, inventory registration, and optional bootstrap orchestration.

## Backend Implementation

Provisioning is implemented under:

```text
backend/app/modules/provisioning/
backend/app/adapters/proxmox/
```

The Proxmox adapter now supports:

- listing VM templates
- cloning a template
- configuring cloud-init
- resizing the default disk
- starting the VM
- polling Proxmox task status

Provisioning records persist:

- VM settings
- cloud-init settings
- static network settings
- lifecycle status
- Proxmox task IDs
- linked inventory server
- bootstrap profile/package selections
- generated bootstrap job IDs

## API Endpoints

```text
GET /api/v1/vms
GET /api/v1/vms/templates
GET /api/v1/vms/{request_id}
POST /api/v1/vms
```

## Lifecycle

```text
requested
validating_ip
cloning
configuring
starting
waiting_for_ssh
inventory_registration
bootstrap_running
completed
failed
```

## Orchestration Flow

```text
Provisioning
  -> Proxmox template clone
  -> cloud-init static networking
  -> VM start
  -> SSH readiness polling
  -> Inventory registration
  -> optional Profiles/Packages
  -> Jobs
  -> SSH
```

Inventory remains the orchestration source of truth. Provisioning does not run bootstrap commands directly against raw Proxmox VM records.

## Frontend Implementation

The Provisioning page now includes:

- VM settings
- template selection
- cloud-init identity and SSH configuration
- static networking
- profile/package bootstrap selection
- provisioning history

## Non-Goals

Not implemented:

- ISO installers
- VMware/cloud providers
- Terraform abstraction
- advanced IPAM/DHCP/VLAN orchestration
- websocket status streaming
- background workers
- rollback orchestration
- RBAC/vault integration

## Status

Sprint 6 establishes the first infrastructure lifecycle workflow in NexusOps.
