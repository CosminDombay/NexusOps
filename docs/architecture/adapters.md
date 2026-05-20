# Adapter Architecture

## Philosophy

Adapters define boundaries between NexusOps application services and external infrastructure systems. They keep provider-specific HTTP APIs, authentication, sessions, SDKs, and protocol details out of routers and domain services.

The adapter layer currently prioritizes:

- explicit contracts
- testability
- provider isolation
- operational safety for infrastructure visibility and controlled lifecycle actions
- future replacement or extension without changing API routers

## Canonical Structure

Adapters live under `backend/app/adapters`.

```text
backend/app/adapters/
  base.py
  docker/
    base.py
  proxmox/
    base.py
    http.py
  ssh/
    base.py
    paramiko.py
```

`base.py` defines the shared `Adapter` base contract. Provider-specific folders define more precise abstract interfaces.

## Proxmox Adapter

The Proxmox adapter is the first concrete external infrastructure adapter.

Files:

- `backend/app/adapters/proxmox/base.py`
- `backend/app/adapters/proxmox/http.py`

The abstract `ProxmoxAdapter` defines visibility and lifecycle methods:

- `get_nodes()`
- `list_vms()`
- `get_vm_status()`
- LXC discovery and lifecycle helpers
- hypervisor/node metadata helpers
- `get_cluster_summary()`

It also defines controlled lifecycle methods:

- `start_vm()`
- `stop_vm()`
- `reboot_vm()`
- `shutdown_vm()`

The concrete `HttpProxmoxAdapter` uses `httpx.AsyncClient` and Proxmox API tokens.

Configuration:

- `PROXMOX_API_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_VERIFY_SSL`
- `PROXMOX_TIMEOUT_SECONDS`

Current safety boundary:

- no VM deletion
- no host mutation
- lifecycle control is limited to start, stop, reboot, and shutdown
- provisioning is limited to template/cloud-init workflows owned by the provisioning service
- importing a discovered VM into Inventory does not mutate the VM

## SSH Adapter

The SSH adapter provides the concrete remote execution boundary used by Jobs.

Files:

- `backend/app/adapters/ssh/base.py`
- `backend/app/adapters/ssh/paramiko.py`

It defines:

- `SshAdapter`
- `SshExecutionResult`
- `ParamikoSshAdapter`

The concrete adapter uses Paramiko and supports:

- key-based authentication through per-server private key path, global `SSH_PRIVATE_KEY_PATH`, SSH agent, or default local keys
- password authentication through inventory server metadata
- command execution with stdout, stderr, and exit code capture

SSH execution targets are inventory-managed servers, not raw Proxmox VM records.

## Docker Adapter

The Docker adapter is currently an abstract boundary only.

File:

- `backend/app/adapters/docker/base.py`

It defines Docker Compose-oriented operations:

- `deploy_compose()`
- `stop_compose()`
- `get_compose_status()`

Docker Compose deployment execution is implemented through the Jobs and SSH pipeline rather than a separate Docker daemon adapter. Deployment services generate remote compose/env operations, execute them on managed nodes through SSH, and persist deployment/runtime state in the deployments module.

## Service Integration Pattern

Services depend on adapter contracts rather than concrete infrastructure details.

Current Proxmox flow:

```text
FastAPI router -> ProxmoxService -> ProxmoxAdapter -> Proxmox API
```

Inventory synchronization keeps provider discovery separate from orchestration authority:

```text
ProxmoxAdapter discovers hypervisor/VM/LXC -> ProxmoxService normalizes provider objects -> InventoryService/ServerRepository matches, imports, or reconciles managed nodes -> Jobs execute only against Inventory records
```

Current Jobs/SSH flow:

```text
FastAPI router -> JobService -> SshAdapter -> Linux host
```

Operational actions resolve to commands inside the Jobs module before following the same SSH flow.

Package definitions and profiles also resolve to commands before entering the same Jobs/SSH flow. They do not introduce separate execution adapters.

Provisioning extends the Proxmox adapter with VM template listing, LXC template listing, template cloning, cloud-init configuration, container creation, disk resize, guest start, and task status polling. Bootstrap still uses the SSH adapter only after the VM or LXC is registered in Inventory with provider linkage and synchronized lifecycle metadata. SSH readiness is tracked separately from provider discovery so a node can exist and be partially managed before shell access is available.

The service normalizes provider-specific data into frontend-friendly Pydantic schemas.

## Error Handling

The Proxmox adapter maps low-level HTTP failures into adapter-specific exceptions:

- `ProxmoxConfigurationError`
- `ProxmoxConnectionError`

The router maps those exceptions into HTTP responses:

- missing configuration: `503`
- connection/auth/API failures: `502`

## Future Extensibility

Future provider implementations should:

- implement the existing abstract adapter for their boundary
- keep provider-specific response shapes inside the adapter/service layer
- expose normalized API schemas to frontend consumers
- avoid leaking provider SDK objects into routers or database models
- keep destructive or provisioning operations separate from visibility and lifecycle-control endpoints
