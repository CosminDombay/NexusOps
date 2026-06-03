# NexusOps Deployment Notes

These notes cover the two deployment paths currently worth evaluating: Docker Compose and an on-prem LXC/VM install. Docker is the recommended first testing path because it gives repeatable builds, a bundled PostgreSQL service, and a consistent migration path. LXC remains a good on-prem option when you want direct service control and host-level inspection.

## Docker Compose Deployment

1. Copy `.env.example` to `.env`.
2. Set strong local values:
   - `SECRET_KEY`
   - `NEXUSOPS_MASTER_KEY`
   - `NEXUSOPS_ADMIN_USER`
   - `NEXUSOPS_ADMIN_EMAIL`
   - `NEXUSOPS_ADMIN_PASSWORD`
   - `POSTGRES_PASSWORD`
3. For production-like testing, set:
   - `ENVIRONMENT=production`
   - `DEBUG=false`
   - `ENABLE_OPENAPI=false`
   - `ALLOW_INSECURE_DEV_SECRETS=false`
   - `ALLOW_INSECURE_DEV_TLS=false`
   - `PROXMOX_VERIFY_SSL=true`
4. Start the stack:

```powershell
.\scripts\start-docker.ps1 -Build
```

or:

```bash
docker compose up -d --build
```

5. Open the frontend at `http://localhost:5173`.
6. Check backend health at `http://localhost:8000/api/v1/health`.

The backend container runs Alembic migrations during startup through `backend/docker-entrypoint.sh`.

## Docker Update Flow

Use an operator-triggered update until backup and rollback automation are formalized.

```bash
git pull
docker compose build
docker compose up -d
docker compose ps
```

Before production use, add a database backup step before rebuilding:

```bash
docker compose exec postgres pg_dump -U nexusops nexusops > nexusops-backup.sql
```

After updating, verify:

- `/api/v1/health`
- login/logout
- inventory list
- `/api/v1/jobs` and `/api/v1/jobs/actions`
- `/api/v1/proxmox/dashboard` when Proxmox is configured
- monitoring page when monitoring integrations are configured
- Identity discovery, adopt/create, group membership sync, and sudo credential-backed replication on a known test node
- Docker deployment create/deploy/runtime refresh/log visibility on a known Docker-capable node
- deployment/runtime status is recent, includes checked timestamps/errors, and does not show stale "running" state without an observed runtime refresh

Fully automated container updates are possible, but they should wait until image tagging, backup retention, rollback, migration checks, and post-update smoke tests are scripted.

## Staging Runner Notes

The current GitHub staging workflow validates backend and frontend scripts on a self-hosted runner before deploying. Because the runner checkout may preserve files for speed, keep generated logs, screenshots, frontend `dist`, local SQLite files, and other local artifacts out of commits and periodically clean stale runner artifacts.

Recommended smoke-test priority during V1 stabilization:

1. Auth login/session restore/logout.
2. Inventory import/re-import and stale-record self-sanitize.
3. Node SSH connectivity and Host Tools.
4. Docker deployment deploy/redeploy/runtime refresh/logs.
5. Identity user/group discovery, adoption, modification, and sudo credential-backed sync.
6. Jobs/actions, packages, profiles, workflows, and automations.

## On-Prem LXC Or VM Deployment

Use this path when you want the application installed directly on a local LXC or VM.

1. Install system dependencies:
   - Python 3.12 or newer
   - Node.js 22
   - PostgreSQL 16
   - Nginx
   - Git
2. Create a PostgreSQL database and user for NexusOps.
3. Clone the repository into an application directory such as `/opt/nexusops`.
4. Create a backend virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

5. Create a backend environment file outside source control with the same production-oriented values listed above.
6. Run database migrations:

```bash
python -m alembic upgrade head
```

7. Start the backend with Uvicorn behind a systemd service:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

8. Build the frontend:

```bash
cd frontend
npm ci
npm run build
```

9. Serve `frontend/dist` through Nginx and proxy `/api/v1` to `127.0.0.1:8000`.

## On-Prem Update Flow

1. Stop or drain the backend service.
2. Back up PostgreSQL.
3. Pull the new Git revision.
4. Install changed Python dependencies.
5. Run `python -m alembic upgrade head`.
6. Rebuild the frontend with `npm ci && npm run build`.
7. Restart backend and reload Nginx.
8. Run the same smoke checks listed in the Docker update flow.

## Choosing Between The Two

Choose Docker when you want repeatable testing, easy rebuilds, and fewer host-level differences. Choose LXC/VM when you want direct control over PostgreSQL, Nginx, logs, backups, and systemd services.

For the next testing phase, start with Docker Compose to validate the release shape, then use the LXC path if you want the app to behave like a normal on-prem service.
