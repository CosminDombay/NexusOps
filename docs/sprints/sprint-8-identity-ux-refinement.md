# Sprint 8: Identity UX Refinement

## Goal

Turn Identity from a raw Linux-control surface into guided infrastructure access orchestration while preserving advanced Linux functionality.

## Implemented Work

- Access profile presets:
  - Standard User
  - Administrator
  - Deployment Operator
  - Docker Operator
  - Log Viewer
  - Read Only
  - Service Account
  - Custom
- Distro-aware administrator group abstraction:
  - Debian/Ubuntu-style hosts resolve to `sudo`
  - RHEL/CentOS/Fedora-style hosts resolve to `wheel`
- Operational group presets:
  - Docker Operators
  - Administrator Access
  - System Log Readers
  - Journal Readers
  - Web Runtime
  - Virtualization Operators
- Permission presets:
  - Private Directory
  - Application Directory
  - Shared Team Directory
  - Read Only File
  - Executable Script
  - Public Writable
  - Custom
- Permission matrix UI:
  - owner read/write/execute
  - group read/write/execute
  - others read/write/execute
  - live octal chmod generation
- Advanced mode:
  - raw shell path
  - raw group selection
  - recursive permission toggle
  - raw octal mode
  - sudoers.d preview
- Generated command previews for access, groups, SSH keys, and permissions.
- Group discovery endpoint backed by `getent group` through Jobs fanout.
- Existing Linux user discovery backed by `getent passwd` through Jobs fanout.
- Managed user adoption from discovered users.
- Managed group adoption from discovered groups.
- Managed user update and delete flows.
- Managed group update and delete flows.
- Optional Credential Manager password selector for Linux user create/update:
  - accepted credential types are `password` and `ssh_password`
  - remote password application uses `chpasswd`
  - persisted Job command history receives a redacted command
- Live user group inspection:
  - runs `id -nG <username>` against selected inventory hosts
  - shows groups per host in the Identity UI
- Live group member inspection:
  - combines `getent group <group>` supplementary members with `getent passwd` primary-GID membership
  - shows all effective members per host
  - separates primary members and supplementary members for operator clarity
- Improved replication target UX with search, select all, clear, and selected-host badges.

## Architecture

The feature remains orchestration, not authentication:

```text
Identity UI preset
  -> /api/v1/identity
  -> Identity service
  -> JobService bulk execution
  -> SSH adapter
  -> inventory-managed Linux host
```

Credential-backed password operations preserve the same execution boundary:

```text
Credential Manager
  -> LinuxUserService resolves secret server-side
  -> JobService receives real command plus redacted command
  -> SSH adapter applies password with chpasswd
  -> Job history stores masked command
```

NexusOps still does not implement LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, OAuth, or login federation.

## Status

Implemented as a guided UX, discovery, and edit layer on top of the existing Identity replication foundation.

Identity remains live Linux orchestration. It does not persist per-host user/group membership snapshots yet; membership inspection reads current host state through Jobs.
