# Sprint 13 - Batch Provisioning Foundation

## Scope

Sprint 13 adds the first batch provisioning workflow for Proxmox VM creation from NexusOps provisioning blueprints.

Implemented:

- `provisioning_batches` parent table
- `batch_id` and `batch_index` on child provisioning requests
- backend batch create/list/detail APIs
- sequential child VM provisioning through the existing safe provisioning pipeline
- blueprint-based generation of VM names, hostnames, VMIDs, and static IP/CIDR values
- frontend batch provisioning panel
- frontend batch history summary
- tests for batch generation and child request creation

## Operator Flow

An operator selects a blueprint and supplies:

- batch name
- VM count
- VM name pattern
- hostname pattern
- starting VMID
- starting IP/CIDR
- optional cloud-init password

Patterns support:

- `{index}` for zero-padded values such as `001`
- `{number}` for plain values such as `1`

Example:

```text
Blueprint: Docker Host
Count: 10
VM name pattern: lab-docker-{index}
Hostname pattern: lab-docker-{index}
Starting VMID: 300
Starting IP/CIDR: 192.168.1.50/24
```

This generates:

```text
lab-docker-001 -> VMID 300 -> 192.168.1.50/24
lab-docker-002 -> VMID 301 -> 192.168.1.51/24
...
```

## Architecture

Batch provisioning does not create a second provisioning engine. Each child VM still runs through:

```text
Blueprint defaults
  -> generated per-VM request
  -> Proxmox clone/config/start
  -> SSH readiness polling
  -> Inventory registration
  -> optional profile/package bootstrap
  -> persisted ProvisioningRequest
```

The batch record is a parent summary for dashboard visibility and progress history. Child records remain normal provisioning requests with their own statuses, task IDs, inventory IDs, errors, and bootstrap job IDs.

## Scheduling

Scheduling batch provisioning is intentionally left as the next slice. The natural integration point is Automations with a future operation type such as:

```text
provisioning_batch
```

That should schedule the same batch payload rather than bypassing the batch service.

## Safety Notes

- Batch provisioning is operator/admin only through the existing provisioning route protection.
- IP generation validates that generated IPs remain inside the starting CIDR network.
- Existing per-VM validation still applies, including inventory IP conflict checks.
- Batch execution is sequential in this foundation sprint to avoid uncontrolled provider load.
