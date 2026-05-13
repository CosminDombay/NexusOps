# NexusOps

NexusOps is a centralized infrastructure orchestration and automation platform for Linux environments.

This repository is scaffolded as a modular monolith:

- `backend/` contains the FastAPI application, domain modules, repositories, services, adapters, jobs, and database setup.
- `frontend/` contains the React/Vite/TypeScript application organized by features.
- `infra/` contains local development infrastructure such as Docker Compose and database initialization scripts.

The current implementation includes the platform foundation, inventory CRUD,
Proxmox visibility/lifecycle control, template-based VM provisioning,
SSH-backed job execution, reusable operational actions, package definitions,
and infrastructure profiles.

## MVP Domains

- VM provisioning through Proxmox API
- Proxmox template cloning with cloud-init configuration
- Static IP provisioning and inventory auto-registration
- Server inventory management
- SSH-based remote execution
- Operational action execution through Jobs
- Package definition catalog
- Reusable infrastructure profiles
- Docker Compose deployments
- Package installation automation
- Monitoring/statistics collection
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
- Proxmox integration discovers nodes, VMs/containers, cluster summary data, and supports guarded VM lifecycle actions.
- Provisioning clones cloud-init-capable Proxmox templates, configures static networking, starts VMs, waits for SSH, and registers inventory records.
- Jobs execute SSH commands against inventory targets and persist status, stdout, stderr, exit code, and timestamps.
- Operational actions provide predefined workflows such as uptime, disk usage, memory usage, Docker checks, Docker restart, and simple installation actions.
- Package definitions describe reusable install/validation commands for common infrastructure packages and can be extended with custom definitions.
- Infrastructure profiles orchestrate ordered package/action workflows through Jobs and can be built from built-in or custom steps.

Current orchestration flow:

```text
Provisioning -> Proxmox template/cloud-init -> Inventory -> Profiles / Packages / Actions -> Jobs -> SSH adapter -> managed Linux host
```

Proxmox remains a provider/discovery layer. Remote execution intentionally runs
through Inventory-managed targets.
