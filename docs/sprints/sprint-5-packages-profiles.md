# Sprint 5: Package Definitions and Infrastructure Profiles

## Goal

Introduce reusable infrastructure standardization workflows on top of the existing Jobs and SSH execution foundation.

## Backend Implementation

Package definitions were added as lightweight reusable metadata:

- id
- name
- category
- supported OS list
- install command
- validation command
- tags
- description

Initial packages:

- Docker Engine
- Tailscale
- Node Exporter
- Promtail
- Fail2Ban
- UFW

Infrastructure profiles were added as ordered orchestration templates. Applying a profile resolves each step to a command and executes it through `JobService`.

Package and profile definitions support built-in templates plus persisted custom definitions. Custom definitions can be created and deleted from the UI/API.

Initial profiles:

- Base Linux Server
- Docker Host
- Monitoring Node
- Development VM

## API Endpoints

```text
GET /api/v1/packages
POST /api/v1/packages
GET /api/v1/packages/{package_id}
PUT /api/v1/packages/{package_id}
DELETE /api/v1/packages/{package_id}
POST /api/v1/packages/{package_id}/execute
GET /api/v1/profiles
POST /api/v1/profiles
GET /api/v1/profiles/{profile_id}
PUT /api/v1/profiles/{profile_id}
DELETE /api/v1/profiles/{profile_id}
POST /api/v1/profiles/{profile_id}/apply
```

## Orchestration Flow

```text
Profile -> Package/Action step -> Job -> SSH -> managed Linux host
```

Every profile step creates a persisted job. Profile execution is synchronous and sequential in this MVP.

## Frontend Implementation

The Packages page now shows package definition cards with install and validation commands, custom package creation, custom package deletion, target host selection, and direct package execution.

The Profiles page now supports:

- profile cards
- custom profile builder
- ordered step display
- inventory target selection
- apply profile workflow
- generated job sequence visibility

## Non-Goals

Not implemented in this sprint:

- provisioning
- Docker Compose uploads
- realtime updates
- Ansible
- Terraform
- workflow DAG engine
- RBAC
- secret vaults
- rollback orchestration

## Status

Sprint 5 establishes reusable infrastructure standardization templates while preserving Jobs as the only execution path.
