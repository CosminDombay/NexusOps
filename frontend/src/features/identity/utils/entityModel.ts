import type { IdentityState } from '../components/common/IdentityPrimitives';
import type { DiscoveredGroup, DiscoveredUser, LinuxGroup, LinuxUser, PermissionTemplate, SSHKey } from '../types/identity';

export type IdentityEntity =
  | { id: string; kind: 'user'; state: IdentityState; name: string; user: LinuxUser }
  | { id: string; kind: 'group'; state: IdentityState; name: string; group: LinuxGroup; memberCount: number }
  | { id: string; kind: 'discovered-user'; state: IdentityState; name: string; user: DiscoveredUser }
  | { id: string; kind: 'discovered-group'; state: IdentityState; name: string; group: DiscoveredGroup; memberCount: number }
  | { id: string; kind: 'ssh-key'; state: IdentityState; name: string; keyRecord: SSHKey }
  | { id: string; kind: 'permission'; state: IdentityState; name: string; permission: PermissionTemplate };

export function buildIdentityEntities(input: {
  users: LinuxUser[];
  groups: LinuxGroup[];
  discoveredUsers: DiscoveredUser[];
  discoveredGroups: DiscoveredGroup[];
  sshKeys: SSHKey[];
  permissions: PermissionTemplate[];
}): IdentityEntity[] {
  return [
    ...input.groups.map((group) => ({
      id: `group:${group.id}`,
      kind: 'group' as const,
      state: group.managed ? 'synced' as const : 'unmanaged' as const,
      name: group.name,
      group,
      memberCount: input.discoveredGroups.find((candidate) => candidate.name === group.name)?.members.length ?? 0,
    })),
    ...input.discoveredGroups.map((group) => ({
      id: `discovered-group:${group.name}`,
      kind: 'discovered-group' as const,
      state: 'discovered' as const,
      name: group.name,
      group,
      memberCount: group.members.length,
    })),
    ...input.users.map((user) => ({
      id: `user:${user.id}`,
      kind: 'user' as const,
      state: user.managed ? 'synced' as const : 'unmanaged' as const,
      name: user.username,
      user,
    })),
    ...input.discoveredUsers.map((user) => ({
      id: `discovered-user:${user.username}`,
      kind: 'discovered-user' as const,
      state: 'discovered' as const,
      name: user.username,
      user,
    })),
    ...input.sshKeys.map((keyRecord) => ({
      id: `ssh-key:${keyRecord.id}`,
      kind: 'ssh-key' as const,
      state: 'synced' as const,
      name: keyRecord.name,
      keyRecord,
    })),
    ...input.permissions.map((permission) => ({
      id: `permission:${permission.id}`,
      kind: 'permission' as const,
      state: 'synced' as const,
      name: permission.path,
      permission,
    })),
  ];
}

