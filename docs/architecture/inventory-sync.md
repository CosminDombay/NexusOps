# Inventory Synchronization

## Role

Inventory is the NexusOps orchestration authority. Infrastructure providers such as Proxmox remain discovery and lifecycle-control integrations. A discovered provider asset does not become an execution target until it is represented by a managed Inventory record.

## State Model

Inventory records track two related state dimensions:

- Node type: `vm`, `lxc`, `physical`, `hypervisor`
- Lifecycle state: `discovered`, `imported`, `managed`, `provisioned`, `unmanaged`, `archived`, `decommissioned`
- Management state: `discovered`, `unmanaged`, `managed`, `retired`
- Synchronization status: `unknown`, `synced`, `unmanaged`, `orphaned`, `mismatch`, `archived`
- Capabilities: optional metadata such as `ssh`, `shell`, `filesystem`, `identity`, `monitoring`, and `provisioning`

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

Proxmox host/node management is the next gap to close. The model now supports `node_type=hypervisor`, but discovery does not yet automatically create or reconcile Inventory records for each Proxmox cluster node. Until that is implemented, Proxmox nodes remain visible through Infrastructure discovery and can only be represented manually in Inventory.

## Reconciliation

Initial reconciliation is intentionally lightweight:

- Proxmox VM exists but no Inventory record: `unmanaged`
- Inventory record links to existing Proxmox VM: `synced`
- Inventory hostname differs from Proxmox name: `mismatch`
- Inventory Proxmox record cannot be found in discovery: `orphaned`
- Inventory record has been retired locally: `archived`
- Inventory record has been decommissioned locally: `archived`

Reconciliation updates NexusOps metadata only. It does not start, stop, delete, or otherwise mutate provider infrastructure.

## Lifecycle Operations

Operators can edit Inventory metadata, mark a node unmanaged, archive an Inventory record, decommission a node, restore/reactivate an inactive record, or delete it. These actions affect the CMDB and orchestration registry only. Provider destruction remains a non-goal for the current phase.

Archived and decommissioned records are excluded from active operational flows by default. They remain available through historical inventory queries with `include_inactive=true`.

Provisioning creates Inventory records automatically with:

```text
provider=proxmox
external_id=<vmid>
source=provisioned
managed=true
lifecycle_state=provisioned
sync_status=synced
```
