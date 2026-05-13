# NexusOps

NexusOps is a centralized infrastructure orchestration and automation platform for Linux environments.

This repository is scaffolded as a modular monolith:

- `backend/` contains the FastAPI application, domain modules, repositories, services, adapters, jobs, and database setup.
- `frontend/` contains the React/Vite/TypeScript application organized by features.
- `infra/` contains local development infrastructure such as Docker Compose and database initialization scripts.

The current implementation includes the platform foundation, inventory CRUD,
Proxmox visibility/lifecycle control, SSH-backed job execution, and reusable
operational actions.

## MVP Domains

- VM provisioning through Proxmox API
- Server inventory management
- SSH-based remote execution
- Operational action execution through Jobs
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
- Jobs execute SSH commands against inventory targets and persist status, stdout, stderr, exit code, and timestamps.
- Operational actions provide predefined workflows such as uptime, disk usage, memory usage, Docker checks, Docker restart, and simple installation actions.

Current orchestration flow:

```text
Inventory -> Jobs / Actions -> SSH adapter -> managed Linux host
```

Proxmox remains a provider/discovery layer. Remote execution intentionally runs
through Inventory-managed targets.
