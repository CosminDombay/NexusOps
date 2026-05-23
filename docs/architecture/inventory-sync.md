# Inventory Synchronization

## Role

Inventory is the NexusOps orchestration authority. Infrastructure providers such as Proxmox remain discovery and lifecycle-control integrations. A discovered provider asset does not become an execution target until it is represented by a managed Inventory record.

## State Model

Inventory records track two related state dimensions:

- Node type: `vm`, `lxc`, `physical`, `hypervisor`
- Lifecycle state: `discovered`, `imported`, `managed`, `provisioned`, `unmanaged`, `archived`, `decommissioned`
- Management state: `discovered`, `unmanaged`, `managed`, `retired`
- Synchronization status: `unknown`, `synced`, `unmanaged`, `orphaned`, `mismatch`, `archived`, `stale`, `disconnected`
- Capabilities: optional metadata such as `ssh`, `shell`, `filesystem`, `identity`, `monitoring`, and `provisioning`

Provider linkage is stored with:

- `provider`
- `external_id`
- `vmid`
- `provider_node`
- `provider_type`
- `integration_id`
- `source_type`
- `source`
- `managed`
- `provider_metadata`
- `sync_metadata`
- `last_seen_at`
- `last_sync_at`
- `stale_since`

Persisted infrastructure integrations are the authoritative source for provider discovery. On startup, NexusOps may bootstrap a default Proxmox integration from local environment variables when no infrastructure integration exists yet, but runtime discovery and synchronization use database integration records after that point.

## Synchronization Flow

```text
Proxmox integration
  -> discover hypervisor nodes, QEMU VMs, and LXC containers for that integration
  -> match Inventory by integration_id plus provider/external_id, provider node, vmid/ctid, hostname, or IP when available
  -> surface status in Infrastructure
  -> reconcile active Proxmox nodes as node_type=hypervisor
  -> operator imports unmanaged guests when they should be orchestrated
  -> Inventory stores SSH, readiness, lifecycle, and provider metadata
  -> Jobs, Packages, Profiles, Deployments, Identity, Monitoring, and Actions execute only against Inventory managed nodes
```

Proxmox host/node management is now part of the same Inventory authority model. Active integrations reconcile every Proxmox cluster node as a `hypervisor` managed node with provider metadata, guest counts, management IP, lifecycle state, and monitoring readiness. Guest VMs and LXCs remain distinct managed node types so operator workflows do not confuse the physical hypervisor with the workloads running on it.

Multiple Proxmox integrations are isolated by `integration_id`. Discovery for one cluster must not update or reconcile resources owned by another cluster.

During migration from the earlier single-provider model, Proxmox synchronization may adopt compatible legacy Inventory rows that have no `integration_id`. This allows existing records such as previously imported hypervisors or guests to be stamped with integration ownership instead of creating duplicate rows that collide on hostname or IP uniqueness.

## Reconciliation

Initial reconciliation is intentionally lightweight:

- Proxmox guest exists but no Inventory record: `unmanaged`
- Inventory record links to existing Proxmox host/guest: `synced`
- Inventory hostname differs from Proxmox name: `mismatch`
- Inventory Proxmox record cannot be found in discovery: `orphaned`
- Inventory record belongs to an integration that failed or disconnected: `disconnected`
- Inventory record belongs to an integration whose discovery no longer sees the resource: `stale`
- Inventory record has been retired locally: `archived`
- Inventory record has been decommissioned locally: `archived`

Reconciliation updates NexusOps metadata only. It does not start, stop, delete, or otherwise mutate provider infrastructure.

Inventory records are preserved when an integration disconnects. NexusOps marks affected resources as stale or disconnected, records stale timestamps and error state, and allows later manual resync to recover the records without requiring re-import.

## Lifecycle Operations

Operators can edit Inventory metadata, mark a node unmanaged, archive an Inventory record, decommission a node, restore/reactivate an inactive record, or delete it. These actions affect the CMDB and orchestration registry by default. Provider destruction remains explicit and provider-specific; decommissioning a Proxmox hypervisor disconnects it from active NexusOps orchestration/synchronization without implying power or hardware lifecycle operations.

Archived and decommissioned records are excluded from active operational flows by default. They remain available through historical inventory queries with `include_inactive=true`.

Provisioning creates Inventory records automatically with:

```text
provider=proxmox
external_id=<vmid>
source=provisioned
managed=true
lifecycle_state=provisioned
sync_status=synced
integration_id=<integration uuid>
source_type=proxmox
```

LXC provisioning creates Inventory records with `node_type=lxc` and the same provider linkage shape. Shell access readiness is validated separately from provider discovery so an LXC can be visible as `discovered`, `booted`, `ip_missing`, `ssh_unreachable`, `partially_managed`, or `degraded` without blocking Inventory synchronization.
