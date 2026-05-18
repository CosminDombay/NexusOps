# Sprint 14 - Secure Shell Access and File Browser Foundation

## Objective

Sprint 14 adds backend-mediated remote shell and file access for Inventory-managed Linux hosts. Remote access remains bounded by Inventory and NexusOps RBAC; the frontend never submits arbitrary hostnames, IP addresses, SSH passwords, or private key contents.

## Architecture

```text
Frontend Host Tools
  -> /api/v1/remote-access/hosts/{server_id}
  -> RemoteAccessService
  -> ServerRepository validates Inventory target
  -> CredentialService resolves SSH material server-side
  -> Paramiko SSH/SFTP
  -> managed Linux host
```

The new backend module lives under `backend/app/modules/remote_access/`:

- `router.py` exposes HTTP file endpoints and the shell WebSocket.
- `service.py` owns RBAC helpers, target validation, path normalization, SSH credential resolution, shell sessions, and SFTP file operations.
- `schemas.py` defines file listing/read/write contracts.
- `audit.py` emits lightweight structured audit hooks.

## RBAC

- `admin`: shell, file browsing, file reading, and file editing.
- `operator`: shell, file browsing, file reading, and file editing only under `/opt`, `/srv`, `/var/www`, and `/home`.
- `viewer`: no shell or file access in this sprint.

Role decisions are implemented as reusable helpers in `RemoteAccessService`, not hardcoded inside router handlers.

## Safety Rules

- All endpoints require a `server_id` that resolves to an Inventory server.
- Unmanaged and archived Inventory records are rejected.
- The frontend cannot provide raw SSH credentials or arbitrary SSH targets.
- File paths must be absolute and traversal attempts are rejected.
- File writes require `expected_hash` and fail with conflict semantics when the remote file has changed.
- Writes upload to a temporary sibling path and rename over the target where SFTP/server behavior permits.
- Audit hooks record shell open/close/failure and file list/read/write outcomes.
- File contents, shell input, and terminal transcripts are not logged or persisted.

## WebSocket Token Tradeoff

The shell MVP passes the current JWT access token as a WebSocket query parameter because browser WebSocket clients cannot set arbitrary authorization headers in the same way Axios can. This is acceptable for local MVP development but should be hardened.

Future hardening:

- mint short-lived remote-access session tokens
- bind remote-access tokens to `server_id`, operation type, role, and expiry
- revoke active shell sessions on logout or role change
- add optional per-session approval and audit persistence

## Frontend

The new frontend feature lives under `frontend/src/features/remote-access/`.

The Host Tools route is:

```text
/inventory/:id/tools
```

The page contains:

- Shell tab with xterm.js, explicit connect/disconnect, and manual reconnect only.
- Files tab with path navigation, directory listing, read-only file loading, textarea editing, dirty-state save button, and confirmation before write.

The UI intentionally avoids IDE features, arbitrary host connection forms, Proxmox consoles, Docker/container shell, and credential exposure.
