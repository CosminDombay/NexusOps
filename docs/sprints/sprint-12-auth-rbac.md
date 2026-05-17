# Sprint 12 - Authentication and RBAC Foundation

## Scope

Sprint 12 adds the local platform security foundation:

- local username/email and password login
- passlib/bcrypt password hashing
- JWT access and refresh tokens
- admin/operator/viewer RBAC dependencies
- protected backend API routers
- frontend login, logout, session restore, and route guards
- role-aware sidebar navigation
- environment-based initial admin bootstrap

## Architecture

Authentication and authorization remain separate:

- authentication answers who the current NexusOps platform user is
- authorization answers which platform areas that user can access

The backend auth module lives under `backend/app/modules/auth/` and is split into API, models, repositories, schemas, services, and security helpers. Future identity providers can be added behind this module without mixing local login with route authorization.

Platform users are not Linux infrastructure identities. Linux users, groups, SSH keys, sudo snippets, and permission templates remain owned by the Identity orchestration module.

## Tokens

Access tokens are short-lived and refresh tokens are longer-lived. JWT payloads include:

- `sub`
- `username`
- `role`
- `exp`

The current frontend stores access and refresh tokens in `localStorage` for the MVP. This is simple and survives refreshes, but it is exposed to browser JavaScript if an XSS flaw is introduced. A later hardening sprint should move toward an in-memory access token plus a safer refresh-token transport strategy.

For local development, `scripts/start-dev.ps1` can prompt for bootstrap admin values and save them to the ignored root `.env` file. This avoids committing a default account while keeping first startup easy.

## Roles

- `admin`: full platform access, including credentials, integrations, identity, and future auth settings
- `operator`: operational execution surfaces such as jobs, provisioning, deployments, packages, profiles, and automations
- `viewer`: read-oriented visibility surfaces such as inventory, monitoring, workflows, and dashboards

## Non-Goals

This sprint intentionally does not implement Google SSO, OIDC, LDAP, SAML, MFA, WebAuthn, API keys, fine-grained permissions, ABAC, audit persistence, or session federation.
