# Inventory Synchronization

## Role

Inventory is the NexusOps orchestration authority. Infrastructure providers such as Proxmox remain discovery and lifecycle-control integrations. A discovered provider asset does not become an execution target until it is represented by a managed Inventory record.

## State Model

Inventory records track two related state dimensions:

- Lifecycle state: `discovered`, `managed`, `provisioned`, `unmanaged`, `archived`
- Synchronization status: `unknown`, `synced`, `unmanaged`, `orphaned`, `mismatch`, `archived`

Provider linkage is stored with:

- `provider`
- `external_id`
- `vmid`
- `provider_node`
- `provider_type`
- `source`
- `managed`
- `provider_metadata`
- `last_seen_at`

## Synchronization Flow

```text
Proxmox VM discovery
  -> match Inventory by provider/external_id, vmid, hostname, or IP when available
  -> surface status in Infrastructure
  -> operator imports unmanaged VM when it should be orchestrated
  -> Inventory stores SSH and provider metadata
  -> Jobs, Packages, Profiles, and Actions execute only against Inventory
```

## Reconciliation

Initial reconciliation is intentionally lightweight:

- Proxmox VM exists but no Inventory record: `unmanaged`
- Inventory record links to existing Proxmox VM: `synced`
- Inventory hostname differs from Proxmox name: `mismatch`
- Inventory Proxmox record cannot be found in discovery: `orphaned`
- Inventory record has been retired locally: `archived`

Reconciliation updates NexusOps metadata only. It does not start, stop, delete, or otherwise mutate provider infrastructure.

## Lifecycle Operations

Operators can edit Inventory metadata, archive an Inventory record, or delete it. These actions affect the CMDB and orchestration registry only. Provider destruction remains a non-goal for the current phase.

Provisioning creates Inventory records automatically with:

```text
provider=proxmox
external_id=<vmid>
source=provisioned
managed=true
lifecycle_state=provisioned
sync_status=synced
```
