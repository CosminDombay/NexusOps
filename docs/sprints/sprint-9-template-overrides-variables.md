# Sprint 9: Editable Templates and Variables

## Goal

Make built-in packages and infrastructure profiles usable as operational templates instead of immutable presets, while keeping system defaults recoverable.

## Implemented

- Editable built-in package support through persisted override records.
- Editable built-in profile support through persisted override records.
- Clone workflow for packages and profiles.
- Restore-default workflow for built-in packages and profiles.
- Template metadata:
  - `is_builtin`
  - `is_modified`
  - `base_version`
  - `source_template_id`
  - `modified_at`
- Package support for:
  - install command
  - uninstall command
  - validation command
  - variables
  - tags
  - category
  - description
- Profile support for:
  - action steps
  - package steps
  - raw command steps
  - step reordering in the frontend editor
  - variables
- Simple variable substitution with `{{ variable_name }}`.
- Execution-time variable injection for package and profile execution.
- Required and sensitive variable metadata.
- Backend `VariableResolutionService` foundation in `backend/app/common/variables.py`.
- Integrations table and Settings page foundation for Proxmox, Prometheus, and Grafana connection records.
- Alembic migration chain fixed and advanced to `20260516_0010`.

## Template Rules

Built-in packages and profiles remain code-defined system templates. Editing one creates or updates a persisted working copy with the same slug. Listing and execution prefer the persisted override when one exists.

Cloned templates become user-managed records. They keep `source_template_id` for traceability but are no longer linked to future system template updates.

Resetting a built-in template removes the persisted override and restores the system default. Job history is preserved because execution records live in Jobs, not in template definitions.

## Variable Rules

Variables use simple placeholder substitution only:

```text
{{ variable_name }}
```

Resolution order:

1. Execution-time variable value.
2. Variable definition default value.
3. Required variable validation error.

This phase intentionally does not add:

- secrets vault
- encrypted secret storage
- Jinja
- arbitrary Python templating
- workflow engine
- Terraform runtime
- Ansible runtime
- remote Git template sync

## UX Notes

The current frontend exposes variable definitions as JSON and prompts for execution-time variables with simple browser prompts. This keeps the backend contract and data model stable while leaving room for a richer execution dialog and variable editor later.

Packages and profiles now show system, modified, and cloned states with badges. Profiles include a draggable execution-order preview tied to the compact step text editor.

## Validation

Validated with:

```text
cd frontend && npm run lint
cd frontend && npm run build
.venv\Scripts\python.exe -m pytest backend\tests
.venv\Scripts\python.exe -m alembic current
```
