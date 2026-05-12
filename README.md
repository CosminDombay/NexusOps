# NexusOps

NexusOps is a centralized infrastructure orchestration and automation platform for Linux environments.

This repository is scaffolded as a modular monolith:

- `backend/` contains the FastAPI application, domain modules, repositories, services, adapters, jobs, and database setup.
- `frontend/` contains the React/Vite/TypeScript application organized by features.
- `infra/` contains local development infrastructure such as Docker Compose and database initialization scripts.

Business logic is intentionally not implemented yet. The current structure defines boundaries, contracts, configuration, and startup wiring.

## MVP Domains

- VM provisioning through Proxmox API
- Server inventory management
- SSH-based remote execution
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

