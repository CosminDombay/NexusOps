# Universal Trash

NexusOps uses a soft-delete lifecycle for operator-managed configuration records that can be referenced by other workflows. Deleting these records moves them to the universal Trash instead of immediately removing database rows, so stale references are visible and recoverable.

## Covered Records

- Credentials
- Custom package definitions
- Custom infrastructure profiles
- Docker Compose deployments
- Automations
- Integrations
- Provisioning blueprints and requests
- Custom operational actions
- Archived, decommissioned, and deleted inventory records are shown in Trash through the existing inventory lifecycle.

Runtime and audit history, such as Jobs and workflow runs, remain historical records and are not treated as Trash items.

## API Shape

The admin-only `/api/v1/trash` API returns deleted records grouped by item type. Each item includes reference counts and metadata that helps operators decide whether the item can be restored or permanently deleted.

Trash actions are:

- `GET /api/v1/trash`: list grouped deleted records.
- `GET /api/v1/trash/{item_type}/{item_id}/references`: inspect active references.
- `POST /api/v1/trash/{item_type}/{item_id}/restore`: restore a deleted record to normal lists.
- `DELETE /api/v1/trash/{item_type}/{item_id}/purge`: permanently delete a trashed record when no active references remain.

Permanent deletion is blocked when active references still exist. Operators should change or remove the referencing profiles, automations, provisioning bootstrap lists, deployment targets, inventory links, or credential consumers first.

## Normal Runtime Behavior

Repositories hide soft-deleted rows by default, so normal list, edit, and execution paths do not reuse trashed records. Services that need Trash behavior explicitly opt into `include_deleted` or `only_deleted`.

## Current Manual Test Note

The Trash lifecycle was manually retested on 2026-06-18 and worked generally in the remote test environment. Credentials now use the universal Trash page for restore and purge instead of a second Credentials-specific Trash surface.
