# NexusOps

NexusOps is a centralized infrastructure orchestration and automation platform for Linux environments.

This repository is scaffolded as a modular monolith:

- `backend/` contains the FastAPI application, domain modules, repositories, services, adapters, jobs, and database setup.
- `frontend/` contains the React/Vite/TypeScript application organized by features.
- `infra/` contains local development infrastructure such as Docker Compose and database initialization scripts.

The current implementation includes the platform foundation, CMDB-style inventory CRUD,
Proxmox visibility/lifecycle control, template-based VM provisioning,
Proxmox-to-inventory synchronization, SSH-backed job execution, reusable operational actions, package definitions,
infrastructure profiles, editable operational templates, credential-backed secret injection, and simple variable-driven execution.

## MVP Domains

- VM provisioning through Proxmox API
- Proxmox template cloning with cloud-init configuration
- Static IP provisioning and inventory auto-registration
- Server inventory management
- Credential Manager for reusable SSH accounts, API tokens, and environment secrets
- Proxmox discovery-to-inventory import
- Managed/unmanaged/orphaned inventory reconciliation
- SSH-based remote execution
- Operational action execution through Jobs
- Package definition catalog
- Editable built-in package templates with clone and reset-to-default workflows
- Reusable infrastructure profiles
- Editable built-in profile templates with clone, step ordering, and reset-to-default workflows
- Simple `{{ variable_name }}` parameterization for package/profile execution
- Credential-backed sensitive package/profile variables with redacted job history
- Variable Manager foundations for reusable runtime values
- Integration records for provider and monitoring connection settings
- SSH-backed Docker Compose deployment workflows
- Package installation automation
- Prometheus-backed monitoring/statistics foundations
- Linux identity orchestration and replication
- guided access profiles for Linux identity operations
- distro-aware administrator group abstraction
- built-in operational group and permission presets
- User/group standardization profiles
- Job execution tracking and logging

## Quick Start

```bash
cp .env.example .env
docker compose -f infra/docker-compose.dev.yml up --build
```

Backend API docs will be available at `http://localhost:8000/docs`.

## Implemented Workflows

- Inventory records define managed execution targets.
- Inventory is the orchestration source of truth and tracks provider linkage, lifecycle state, synchronization state, and SSH execution metadata.
- Proxmox integration discovers nodes, VMs/containers, cluster summary data, import status, and supports guarded VM lifecycle actions.
- Discovered Proxmox assets can be imported into Inventory, but NexusOps does not blindly auto-import every VM.
- Provisioning clones cloud-init-capable Proxmox templates, configures static networking, starts VMs, waits for SSH, and registers inventory records.
- Jobs execute SSH commands against inventory targets and persist status, stdout, stderr, exit code, and timestamps.
- Jobs resolve node credentials and execution credential references server-side. Sensitive values are never returned to the frontend, and commands persisted to job history are redacted when runtime secrets are injected.
- Inventory health checks perform lightweight TCP reachability checks against SSH ports without logging in on each refresh.
- Credential records store reusable secret material encrypted with Fernet using `NEXUSOPS_MASTER_KEY`. API responses expose only masked secret status.
- Inventory records can reference a shared `credential_id` for SSH execution while retaining inline SSH metadata for backward-compatible local MVP use.
- Operational actions provide predefined workflows such as uptime, disk usage, memory usage, Docker checks, Docker restart, and simple installation actions.
- Package definitions describe reusable install/validation commands for common infrastructure packages and can be extended with custom definitions.
- Built-in package definitions can be edited as persisted working copies, cloned into custom templates, or restored to the system default.
- Package variables use simple `{{ variable_name }}` placeholders and are resolved before execution from defaults, runtime inputs, and credential references for sensitive values.
- Infrastructure profiles orchestrate ordered package/action/command workflows through Jobs and can be built from built-in or custom structured steps.
- Built-in profiles can be edited as persisted working copies, cloned into user-managed templates, reordered, or restored to the system default.
- Integration records provide a central place to store and test provider/monitoring connection metadata while runtime adapters still primarily use local environment configuration.
- Docker Compose deployments store compose/env definitions and execute deploy/redeploy/restart/stop/status/logs through the Jobs -> SSH pipeline.
- Monitoring reads metrics from the Prometheus HTTP API when configured and links to Grafana when configured.
- Identity orchestration stores Linux users, groups, SSH public keys, and permission templates, then replicates user/group/access/permission changes across selected Inventory-managed hosts through Jobs and SSH.
- Identity includes guided access profiles such as Administrator, Deployment Operator, Docker Operator, Log Viewer, Read Only, and Service Account. These profiles configure shell, sudo behavior, recommended groups, and defaults while preserving advanced Linux controls.
- Identity resolves administrator access through a distro-aware abstraction, using `sudo` on Debian/Ubuntu style hosts and `wheel` on RHEL/CentOS/Fedora style hosts during replicated execution.
- Permission workflows include presets and a human-friendly read/write/execute matrix that generates octal modes while retaining advanced raw mode controls.

Current orchestration flow:

```text
Provisioning -> Proxmox template/cloud-init -> Inventory -> Profiles / Packages / Actions -> Jobs -> SSH adapter -> managed Linux host
```

Proxmox remains a provider/discovery layer. Inventory deletion or archival does
not destroy provider infrastructure. Remote execution intentionally runs through
Inventory-managed targets. Identity is Linux access orchestration and replication,
not centralized authentication; NexusOps does not implement LDAP, Kerberos,
FreeIPA, Active Directory, or SSSD.
