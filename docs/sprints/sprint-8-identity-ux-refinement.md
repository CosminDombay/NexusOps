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

NexusOps still does not implement LDAP, Kerberos, FreeIPA, Active Directory, SSSD, PAM rewriting, OAuth, or login federation.

## Status

Implemented as a guided UX and preset layer on top of the existing Identity replication foundation.
