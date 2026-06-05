# NexusOps Improvement Backlog

This backlog captures near-term product and engineering improvements from the May 2026 review. It is intentionally practical: each item should either reduce operator friction, improve safety, or make orchestration more reliable.

## UI/UX Improvements

### Highest Impact

- Rework navigation groups so Inventory, Infrastructure, Provisioning, and Credentials sit under a clearer Core area. Operations should contain Jobs, Packages, Profiles, Deployments, Identity, and Monitoring.
- Turn provisioning into a guided workflow: blueprint selection, identity/network fields, cloud-init credentials, bootstrap selection, review, then execution.
- Continue refining provisioning into a dedicated guided wizard. The large VM/LXC forms are now collapsible, but review/confirmation and step-by-step guidance still need polish.
- Add a provisioning review screen that shows VM name, VMID, template, node, IP/CIDR, disks, bootstrap profiles/packages, and destructive or long-running effects before submission.
- Replace raw JSON/text-heavy controls where possible with structured editors. Integrations, deployment env mappings, and blueprint disks should all prefer guided controls.
- Add first-class logs views:
  - provisioning task timeline
  - job stdout/stderr history
  - Docker Compose logs
  - Proxmox task status
  - bootstrap profile/package sequence
- Improve long-running operation feedback. Provisioning, profile application, package execution, health refresh, and Docker deployment should show progress and current step, not only a final response.
- Add empty states and next-action prompts on pages that depend on prerequisites, such as Credentials, Provisioning, Deployments, Monitoring, and Integrations.

### Workflow Clarity

- Make the difference between Proxmox VM templates and NexusOps provisioning blueprints explicit in labels and helper text.
- Show which fields come from a blueprint and which fields are per-machine overrides.
- Add blueprint clone/update flows. Current UI can save/delete but does not provide a polished edit/update path.
- Add deployment-as-profile-step execution so profiles can truly orchestrate VM setup plus app deployment.
- Add clearer success summaries after provisioning: Inventory link, bootstrap job links, Proxmox task IDs, and next recommended actions.
- Add explicit active-source status to Integrations, showing whether a record is config-only, actively consumed by a module, or falling back to environment settings.
- Continue enriching the unified managed-node page with deeper provider metadata, logs, and runtime drilldowns. The current page already converges Jobs, Deployments, Workflows, Identity, Metrics, Terminal, Files, and lifecycle/readiness context.
- Add a compact "operations queue" or "recent activity" panel on the dashboard.

### Usability Polish

- Add search/filter/sort to Credentials, Deployments, Profiles, Packages, Jobs, and Provisioning history.
- Add copy buttons for IDs, VMIDs, IP addresses, commands, stdout/stderr, and generated curl/API snippets.
- Add form-level validation summaries for provisioning and blueprints, especially IP/CIDR, gateway, disks, and required bootstrap inputs.
- Add credential type filtering in dropdowns, so API-token fields do not show SSH-only credentials unless explicitly allowed.
- Add storage target discovery for Proxmox disks instead of requiring operators to type `local-lvm`.
- Add confirmation dialogs for deployment stop/redeploy and any operation likely to disrupt services.
- Make job/deployment logs easier to read with wrapping, copy, search, timestamps, and stdout/stderr tabs.
- Add Docker Compose discovery/adoption UI so existing per-node Compose projects can be scanned, reviewed, adopted into NexusOps management, and then managed from Deployments or the node Deployment tab.
- Split Docker deployment record deletion from destructive machine-side removal. A future "Remove from machine" action should run Compose down and optionally clean remote compose/env files, while "Delete NexusOps record" should only remove the control-plane record.
- Turn Identity live discovery results into richer, filterable tables with per-host drilldowns for users, groups, memberships, and replication drift.
- Rework Identity around target-first workflows so selected hosts, discovered observations, managed desired state, and drift/reconciliation status are visible in one place.
- Split Identity password controls into "account password to set" and "execution/sudo credential" to reduce operator confusion during sync/replication.

## Backend Improvements

### Highest Impact

- Preserve the runtime snapshot contract for monitoring overview reads. Ordinary page rendering should not run live Prometheus target discovery, Grafana dashboard search, or deep telemetry query chains; those belong behind explicit refresh actions that update snapshots.
- Continue moving long-running work out of request/response paths. Scheduled automations now create WorkflowRuns and dispatch through the in-process async queue; provisioning, direct profile/package execution, identity replication, bulk jobs, and deployments still need deeper workflow-backed async entrypoints.
- Expand Proxmox host replacement/failover workflows now that hosts are first-class `hypervisor` managed nodes. Discovery creates/reconciles hypervisors and lifecycle operations archive/decommission/restore them, but provider endpoint replacement and cluster failover UX need hardening.
- Add Proxmox integration endpoint replacement/failover workflows. Operators need to move from one Proxmox host/API endpoint to another or add a multi-node cluster without editing code or environment variables.
- Add realtime status updates through polling endpoints first, then WebSockets or server-sent events later.
- Expand the workflow domain into full orchestration chaining. WorkflowRun and WorkflowStep now expose runtime visibility, but provisioning, identity, and direct package/profile execution still need complete step-by-step workflow refactors.
- Deepen deployment/profile integration so profile steps can orchestrate deployments with full execution context and rollback-ready behavior.
- Add Docker Compose project discovery and adoption services. Discovery should inspect existing Compose labels/files where possible, map services/ports/containers to candidate deployment records, and allow operators to adopt rather than recreate existing services.
- Add machine-side deployment removal as an explicit destructive workflow with confirmation, audit, generated command preview, and optional cleanup of remote compose/env files.
- Expand audit reporting and filtering for infrastructure actions, provisioning tasks, deployment operations, identity replication, and destructive operations. Durable audit persistence is now present; the next step is operator-facing analysis and retention policy.
- Extend the persisted integration authority model to future providers. Proxmox discovery/synchronization now resolves through database integrations; new provider adapters should follow the same integration-owned discovery, state, and stale-resource model.
- Add provisioning blueprint or provisioning batch as a Workflow/Automation operation with minimal runtime inputs.
- Strengthen authentication and authorization before broadening destructive infrastructure capabilities: MFA/WebAuthn, API keys, scoped tokens, finer-grained permissions, and audit trails remain future work even though local auth/RBAC exists.

### Reliability and Safety

- Add idempotency keys for provisioning and deployment operations to prevent accidental duplicate VM creation or repeated deploys.
- Add idempotency keys for Identity replication, package/profile execution, and destructive operations as well as provisioning/deployments.
- Add stronger validation around Proxmox VMID availability, IP conflicts, blueprint compatibility, disk storage existence, and template cloud-init readiness before starting a clone.
- Poll Proxmox lifecycle tasks to completion for start/stop/reboot/shutdown, not only provisioning tasks.
- Store Proxmox task logs/status snapshots for later debugging.
- Add rollback/cleanup strategy for provisioning failures after clone but before inventory registration.
- Add stale/orphaned deployment reconciliation for records whose expected containers/files no longer exist on the target, and for unmanaged Compose projects found during discovery.
- Deepen CT/LXC readiness checks beyond the current discovery/provisioning/lifecycle foundation: interface detection, gateway reachability, DNS validation, SSH readiness polling, storage discovery, and richer template metadata.
- Add cancellation support for queued/running Jobs and long-running provisioning workflows where technically possible.
- Add distributed execution leases before running multiple backend workers or self-hosted deployment runners against the same queue/runtime tables.
- Add optimistic locking or version fields for editable definitions and blueprints to avoid accidental overwrite.
- Continue expanding structured error types for provider failures so the frontend can show actionable messages instead of generic API errors. Monitoring validation already exposes structured component failure reasons.

### Data and Secrets

- Convert inline inventory SSH passwords/private key paths into credential references where possible, leaving legacy fields only for migration/local MVP fallback.
- Add credential usage tracking for deployments, integrations, inventory records, packages, and profiles.
- Add credential usage tracking for Identity execution/sudo credentials and remote-access SSH credentials.
- Add credential rotation workflow and "last used" metadata.
- Avoid returning sensitive-ish config fields in integration/deployment reads unless redacted.
- Decide whether deployment plaintext `.env` content should remain supported or be split into explicit non-secret env vars plus credential-backed secret env vars.
- Decide whether Identity should persist per-host Linux user/group membership snapshots or keep membership inspection as live, on-demand host state.

### Testing and Tooling

- Add backend tests for provisioning blueprints, additional disks, deployment credential env injection, deployment execution credentials, deployment dry-run previews, integration credential refs, LXC provisioning, hypervisor reconciliation, deployment target executions, and monitoring readiness derivation.
- Add backend tests around monitoring snapshot refresh boundaries so overview reads remain database-bounded.
- Add frontend tests for provisioning blueprint fill/save/delete, inventory edit modal behavior, and deployment credential env rows.
- Add Playwright smoke tests for login, target selection, deployment deploy button visibility, Identity discovery/adopt/sync, credential edit, and inventory import.
- Add feature-specific staging smoke suites such as `smoke:identity`, `smoke:deployments`, `smoke:inventory`, and `smoke:auth`.
- Keep CI coverage healthy for lint, frontend build, backend tests, Alembic migration validation, and artifact hygiene.
- Add deeper migration tests against PostgreSQL beyond the current Alembic head/current/upgrade/downgrade CI smoke.
- Add contract tests around `VITE_API_BASE_URL`, CORS origins, and common local startup failures.
- Add code quality gates for generated artifacts, logs, screenshots, and local build output.

## Product Direction

- Treat Inventory as the persistent control plane and all execution as Inventory-targeted.
- Treat Proxmox as the provider layer, not the orchestration target.
- Treat provisioning blueprints as the reusable "server shape" abstraction.
- Treat profiles as host configuration standards.
- Treat deployments as application/service delivery.
- Treat monitoring/logging as operational readiness feedback loops attached to inventory hosts, runtime executions, and deployments.
- Avoid adding Terraform, Ansible, or a full workflow engine until the internal Jobs/Profile/Deployment workflow is stable enough to justify integration.
