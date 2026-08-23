# NexusOps Deployment Notes

These notes cover the deployment shape for the current product version. Docker Compose is the recommended path because it gives repeatable builds, a bundled PostgreSQL service, and a consistent migration path. A native LXC/VM install remains possible when direct service control and host-level inspection are more important than container repeatability.

## Branch And Environment Model

`main` is the stable release branch. Production deployment should be manually triggered from `main` after changes have already been validated on `development`.

`development` remains the active integration branch. When the `hds-lab` runner exists, pushes to `development` can validate and deploy to the lab environment, but the workflow is gated by the repository variable `ENABLE_HDS_LAB_DEPLOY=true` so it does not queue before the runner is online.

Production deployments are manual only. The production workflow runs only from `main` on a self-hosted runner labeled `nexusops-prod`. It validates the dispatched revision in the runner workspace, verifies that revision is the current `origin/main`, updates the persistent `/opt/nexusops` checkout to that exact commit, requires a host-managed `/opt/nexusops/.env` file with mode `0600`, validates the Compose config through `scripts/deploy.sh --config-only`, and then calls the shared deployment script from `/opt/nexusops`. Production secrets remain on the host rather than being copied into GitHub.

## Automated Setup Scripts

The root deployment scripts are the fastest way to prepare a local validation environment:

```bash
./setup.sh
./setup-docker.sh
```

`./setup.sh` targets a native local deployment. It verifies or installs PostgreSQL on Debian/Ubuntu, creates the NexusOps database and user, prepares `.env`, installs Python/npm dependencies, runs backend and frontend validation, applies Alembic migrations, and starts the local backend/frontend servers.

`./setup-docker.sh` targets the containerized deployment. It prepares `.env`, runs backend and frontend validation, validates and builds the Compose stack, and starts PostgreSQL/backend/frontend containers with `docker compose up -d`.

Both scripts write timestamped logs to `deployment-reports/`. The report directory is intentionally ignored by Git because it contains generated validation/deployment output. Use `--skip-tests` only for quick local iteration, not for release or staging evidence.

Database behavior depends on the selected deployment mode:

- Native local mode uses PostgreSQL on the host and writes a localhost `DATABASE_URL`.
- Docker mode uses the bundled `postgres` Compose service and connects from the backend container through the Compose network.
- Remote/on-prem database mode is supported by editing `.env` so `DATABASE_URL` points to an existing PostgreSQL server; in that case the operator is responsible for database/user creation, backups, and connectivity.

## Docker Compose Deployment

1. Copy `.env.production.example` to `.env` on the production host.
2. Replace every `CHANGE_ME` value:
   - `SECRET_KEY`
   - `NEXUSOPS_MASTER_KEY`
   - `NEXUSOPS_ADMIN_USER`
   - `NEXUSOPS_ADMIN_EMAIL`
   - `NEXUSOPS_ADMIN_PASSWORD`
   - `POSTGRES_PASSWORD`
3. Confirm production settings:
   - `ENVIRONMENT=production`
   - `DEBUG=false`
   - `ENABLE_OPENAPI=false`
   - `TRUSTED_PROXY_HOPS=1` (one reverse proxy: the frontend nginx)
   - `PROXMOX_VERIFY_SSL=true`
4. Set `CORS_ORIGINS` to the real browser origin, for example `["https://nexusops.example.com"]`.
5. Keep `BACKEND_PORT=127.0.0.1:8000` unless the backend API must be reachable directly. The frontend nginx container proxies `/api/v1`, `/api/ws`, and remote access websocket paths to the backend over the Compose network.
6. Start the stack:

```powershell
.\scripts\start-docker.ps1 -Build
```

or:

```bash
docker compose up -d --build
```

7. Open the frontend at `http://localhost` or the configured external hostname.
8. Check backend health locally at `http://127.0.0.1:8000/api/v1/health`.

The backend container runs Alembic migrations during startup through `backend/docker-entrypoint.sh`.

## Boot-Time Compose Service

The template systemd unit at `deploy/systemd/nexusops-compose.service` starts the Compose stack at boot. Install it on the production host after the repository has been placed at `/opt/nexusops` and `.env` has been created there.

```bash
sudo cp deploy/systemd/nexusops-compose.service /etc/systemd/system/nexusops-compose.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexusops-compose.service
```

The unit runs `docker compose up -d --remove-orphans` on start and `docker compose stop` on stop. Container-level `restart: unless-stopped` policies handle normal Docker restarts between system boots.

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
- Docker deployment create/edit/deploy/runtime refresh/log visibility on a known Docker-capable node
- Docker deployment execution/sudo credential selection on a node without Docker group access
- deployment preflight preview, Compose validation, redacted generated command preview, and credential-backed env separation
- deployment/runtime status is recent, includes checked timestamps/errors/stale age/failure reasons, and does not show stale "running" state without an observed runtime refresh
- Host Detail credential readiness for SSH, sudo fallback, and Docker operations
- Proxmox discovered-record sanitize preview before deletion

Fully automated container updates are possible, but they should wait until image tagging, backup retention, rollback, migration checks, and post-update smoke tests are scripted.

## HDS Lab Runner Notes

The hds-lab workflow validates backend and frontend scripts on a self-hosted runner before deploying. It expects the runner to have the label `hds-lab`. Because the runner checkout may preserve files for speed, keep generated logs, screenshots, frontend `dist`, local SQLite files, and other local artifacts out of commits and periodically clean stale runner artifacts.

Do not enable automatic development deployment until the host and runner are ready. Set the repository variable `ENABLE_HDS_LAB_DEPLOY=true` only after hds-lab is online and its environment secret has been configured.

Recommended smoke-test priority during V1 stabilization:

1. Auth login/session restore/logout.
2. Inventory import/re-import and stale-record self-sanitize dry-run/apply.
3. Node SSH connectivity and Host Tools.
4. Docker deployment preview/save/deploy/redeploy/runtime refresh/logs.
5. Execution/sudo credential selectors in Jobs, Packages, Profiles, Automations, and Deployments.
6. Identity user/group discovery, adoption, modification, and sudo credential-backed sync.
7. Jobs/actions, packages, profiles, workflows, and automations.

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
