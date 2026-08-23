# Design Constraints and Non-Goals

NexusOps is deliberately narrower than the categories it borders on. This page
records the boundaries the implementation is held to, and the reasoning behind
them, so that a later change does not quietly cross one.

Detailed behaviour lives in the other architecture notes; this page is only the
list of things the platform will not become.

## Execution pipeline

Everything that touches a managed host resolves into a Job and runs through the
same `Jobs -> SSH -> persistence` pipeline. Packages, Profiles and Identity
operations are all producers of Jobs.

The reason is auditability: one execution path means one place where commands are
validated, credentials are injected and redacted, results are persisted, and
history is queryable. A module that shells out on its own would be invisible to
job history, runtime state, and the audit log.

Consequently, no module may implement standalone execution logic, and no adapter
logic may be duplicated outside `backend/app/adapters/`.

## Inventory is the orchestration boundary

Jobs and operational actions execute only against inventory-managed servers,
never against raw Proxmox VM records or arbitrary hosts and IPs.

Inventory is what makes a machine a known, owned, addressable object with
credentials, a pinned SSH host key and a lifecycle state. Executing against
anything else would mean executing against something the platform cannot
describe, authorise or clean up. Remote shell access is bound by the same rule.

## Identity is Linux orchestration, not authentication

The Identity module creates, replicates and inspects Linux users, groups and
permissions across managed hosts. It is not a directory service.

Out of scope: LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting and
login federation. Those replace the operating system's authentication stack;
NexusOps only drives the tools the operating system already has.

## Templating stays substitution-only

Package and profile templates support `{{ variable_name }}` substitution and
nothing else. No Jinja, no arbitrary expression evaluation, no embedded Python,
no general workflow engine.

Template content becomes a shell command on a managed host, so anything more
expressive turns a template into remote code execution with extra steps. The
limitation is the security control.

## Provisioning is template plus cloud-init

Virtual machines are provisioned by cloning a Proxmox template and configuring it
through cloud-init. ISO and raw-installer provisioning are out of scope.

Provisioning registers the machine in Inventory before any profile, package or
bootstrap step runs, so that everything which follows goes through the normal
managed-host path.

## Built-in definitions stay recoverable

Built-in package and profile definitions may be listed and executed, but only
persisted custom definitions are editable and deletable. Built-ins must always be
recoverable through reset-to-default.

Once a user clones a built-in, the clone is theirs: system template updates must
not implicitly rewrite it.

## Credentials are managed, not vaulted

The Credential Manager stores reusable secrets encrypted at rest and injects them
into execution with redaction in job history. Integration records may reference
credentials.

It is not a vault: there is no rotation, leasing, dynamic issuance or
break-glass workflow. Treat it as scoped secret storage for this platform's own
execution, not as infrastructure other systems should depend on.

## Destructive operations are explicit

Proxmox lifecycle control is limited to start, stop, reboot and shutdown. The
backend resolves node and guest type server-side and validates existence and
status before dispatching. The frontend requires confirmation for every
destructive action.

## Known intentional simplifications

These are accepted trade-offs rather than oversights, and are the places to look
first when the platform is scaled up:

- Job and workflow execution runs on an in-process async queue with no durable
  state. A restart reconciles anything left in flight.
- Some runtime metadata is stored in JSON columns pending promotion to typed
  columns.
- Runtime state is refreshed by polling rather than pushed in real time.
