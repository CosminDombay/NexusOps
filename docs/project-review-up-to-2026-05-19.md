# NexusOps Project Review up to 2026-05-19

> Historical snapshot: this review is kept for traceability. Current platform scope and validation status are tracked in `docs/architecture/current-state.md`, `docs/development.md`, and `docs/api.md`.

## Review Scope

This review covers the platform after the contextual workspace drawer refactor and before the next refinement cycle.

Reviewed areas:

- frontend operational workspace UX
- integrations and monitoring wiring
- provisioning and blueprint workflows
- profiles and automations as orchestration surfaces
- Proxmox VM/CT/LXC visibility and provisioning boundaries
- validation status

## Findings

### 1. Persisted monitoring integrations are not runtime source-of-truth yet

Severity: High

The Integrations page can create Prometheus, Grafana, Loki-like, and provider records, and those records can be tested. However, the Monitoring service still reads runtime URLs from environment-backed settings:

- `settings.prometheus_api_url`
- `settings.grafana_base_url`
- `settings.loki_base_url`

It does not resolve active persisted integration records for Prometheus, Grafana, or Loki when building monitoring health, metric queries, or dashboard links.

Impact:

- Adding integrations in the UI can appear to do nothing in Monitoring.
- Operators can reasonably think they misconfigured the platform even when the missing piece is runtime wiring.
- Integration records are useful for testing/configuration persistence, but not yet fully connected to Monitoring behavior.

Recommended next fix:

- Add an integration-aware monitoring configuration resolver.
- Prefer enabled persisted integrations by type/name for Prometheus, Grafana, and Loki.
- Keep environment variables as bootstrap/default fallback.
- Show the active source in the Monitoring UI: `integration record`, `environment`, or `not configured`.

### 2. Monitoring page is a foundation, not a complete observability workspace

Severity: Medium

The Monitoring page currently provides quick health, simple Prometheus API queries, per-host metric rows, and links to external Prometheus/Grafana/Loki tools. It does not collect metrics itself, manage scrape target registration, validate node exporter/promtail/cAdvisor deployment, or show service/log state beyond the current query/link model.

Impact:

- The page can look like a finished monitoring system, but it is closer to a monitoring summary and launcher.
- If Prometheus is not configured through environment variables, the page reports Prometheus unavailable even if an integration record exists.

Recommended next fix:

- Rename/copy-adjust Monitoring to clarify "External monitoring summary".
- Add operational status cards for configured integrations and active scrape/link sources.
- Add "what is missing" guidance when Prometheus/Grafana/Loki are configured as records but not active.

### 3. Provision VM still dominates the Provisioning page layout

Severity: Medium

Blueprint actions and batch provisioning now use contextual drawers, but the single VM provisioning wizard remains a full-width permanent section. That preserves the working wizard, but it still violates the newer operational workspace direction.

Impact:

- Provisioning is cleaner than before, but still visually weighted toward one large form.
- The blueprint explorer/list plus center wizard plus right drawer model is not fully realized yet.

Recommended next fix:

- Convert the Provision VM wizard into a contextual drawer or wizard workspace triggered by a primary action.
- Keep the current multi-step structure inside that workflow.
- Leave provisioning history and blueprint selection visible as operational context.

### 4. Provisioning blueprints are not profile steps

Severity: Medium

Profiles currently represent host configuration and deployment intent after an execution target exists. Provisioning blueprints represent machine creation intent before the target exists. The current ProfileService can execute packages, actions, commands, and deployment steps against existing Inventory targets; it cannot create machines.

Impact:

- It is correct that blueprints do not naturally fit as normal profile steps today.
- End-to-end "create machine, then configure/deploy" orchestration requires a workflow-level abstraction above profiles.

Recommended next fix:

- Add provisioning blueprint execution as a Workflow/Automation operation, not a Profile step.
- Model profile application as a downstream step after successful Inventory registration.
- Keep profiles as host configuration standards and blueprints as server-shape standards.

### 5. Automations cannot run provisioning or deployment operations yet

Severity: Medium

The automation model contains `deployment` and `command` operation enum values, but `AutomationService._validate_supported_operation` currently allows only:

- `action`
- `profile`
- `package`

Provisioning blueprint or batch provisioning operations are not currently supported.

Impact:

- Automations are useful for recurring operational checks/compliance runs.
- They are not yet a general orchestration engine for build/rebuild workflows.

Recommended next fix:

- Add `provisioning_blueprint` or `provisioning_batch` as an explicit automation/workflow operation.
- Require minimal runtime inputs such as VM name pattern, VMID/IP start, hostname pattern, and optional override variables.
- Persist each provisioning step into WorkflowRun/WorkflowStep for traceability.

### 6. CT/LXC support is partial

Severity: Medium

Proxmox discovery and lifecycle paths can represent guest `type` and the adapter can normalize `qemu` and `lxc` for status/actions. However, provisioning is hardwired to the QEMU template/cloud-init path:

- clone uses `nodes/{node}/qemu/{template_id}/clone`
- configure uses `nodes/{node}/qemu/{vm_id}/config`
- disk resize/add-disk logic assumes VM disk devices
- Inventory registration stores provider type as `qemu`

Impact:

- CT/LXC visibility may appear in Infrastructure, but provisioning and full operational lifecycle are not complete.
- CT/LXC shell and management should be treated as future execution-target work, not assumed done because templates exist.

Recommended next fix:

- Decide whether CT/LXC provisioning is a separate workflow or a variant of provisioning.
- Add `ExecutionTarget` thinking for `vm`, `host`, `lxc`, and Docker container operations.
- Keep QEMU and LXC provider adapters separate where Proxmox API semantics differ.

### 7. Integration status is config-centric rather than operational

Severity: Low

Integration cards can be enabled/disabled and tested, but they do not yet show whether a module is actively consuming that integration. For example, a Prometheus integration may test successfully while Monitoring still uses environment settings.

Recommended next fix:

- Add `consumed_by` or computed operational status in the integrations API/UI.
- Show "Used by Monitoring", "Available but not active", or "Config-only" states.

## Positive State

- Contextual drawer pattern is now standardized through `ContextDrawer`.
- Deployment page remains the strongest operational card/dashboard reference.
- Inventory manual onboarding is correctly secondary and labeled `Import Existing Host`.
- Automation cards now expose target hostnames.
- Credentials and Integrations have create/edit drawer workflows.
- Profiles and Packages have drawer-based authoring with explicit dismissal.
- Backend and frontend validation remain green.

## Validation

Validated on 2026-05-19 with:

```powershell
cd frontend
npm run lint
npm run build
```

Backend:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
```

Result:

```text
81 passed
```
