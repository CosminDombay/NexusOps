import { Users } from 'lucide-react';

import type { DiscoveredGroup, GroupMembership, LinuxGroup, UserGroupMembership, LinuxUser } from '../../types/identity';
import { MetricTile, PermissionChip, SectionCard, StatusBadge } from '../common/IdentityPrimitives';

export function GroupDetailsPanel({
  group,
  discoveredGroup,
  membership,
  users,
  userMembership,
}: {
  group?: LinuxGroup;
  discoveredGroup?: DiscoveredGroup;
  membership: GroupMembership | null;
  users: LinuxUser[];
  userMembership: UserGroupMembership | null;
}) {
  const name = group?.name ?? discoveredGroup?.name ?? 'No group selected';
  const allMembers = [...new Set(membership?.hosts.flatMap((host) => host.members) ?? discoveredGroup?.members ?? [])].sort();
  const memberCards = allMembers.map((username) => {
    const managedUser = users.find((user) => user.username === username);
    const inspectedGroups = userMembership?.username === username ? [...new Set(userMembership.hosts.flatMap((host) => host.groups))] : [];
    return { username, managedUser, inspectedGroups };
  });

  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-cyan-400/15 text-cyan-100">
              <Users className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">{name}</h2>
              <p className="text-sm text-slate-400">{group?.description || (group ? 'Managed Linux group' : 'Discovered Linux group')}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge state={group ? (group.managed ? 'synced' : 'unmanaged') : 'discovered'} />
            {membership ? <StatusBadge state="pending" label="live inspected" /> : null}
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <MetricTile label="Members" value={allMembers.length} detail="effective users" />
          <MetricTile label="Hosts" value={membership?.hosts.length ?? discoveredGroup?.hosts.length ?? 0} detail="observed targets" />
          <MetricTile label="GID" value={discoveredGroup?.gid ?? 'Unknown'} />
          <MetricTile label="State" value={group ? 'Managed' : 'Discovered'} />
        </div>
      </section>

      <SectionCard title="Linux Mappings">
        <div className="flex flex-wrap gap-2">
          {permissionModelFor(name).map((permission) => <PermissionChip key={permission.label} label={permission.label} tone={permission.tone} />)}
        </div>
      </SectionCard>

      <SectionCard title="Members">
        {memberCards.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {memberCards.map((member) => (
              <div key={member.username} className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-white">{member.username}</p>
                    <p className="mt-1 text-xs text-slate-400">{member.managedUser ? 'managed user' : 'discovered member'}</p>
                  </div>
                  {member.managedUser?.locked ? <StatusBadge state="failed" label="locked" /> : <StatusBadge state="synced" label="active" />}
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {member.managedUser?.sudo_enabled ? <PermissionChip label="sudo" tone="privileged" /> : null}
                  {(member.inspectedGroups.length ? member.inspectedGroups : [name]).slice(0, 4).map((groupName) => <PermissionChip key={groupName} label={groupName} />)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">Run Inspect members or Discover groups to load effective group membership.</p>
        )}
      </SectionCard>

      {membership ? (
        <SectionCard title="Live Member Inspection">
          <div className="grid gap-3 md:grid-cols-2">
            {membership.hosts.map((host) => (
              <div key={host.target_server_id} className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
                <p className="text-sm font-semibold text-white">{host.target_hostname ?? host.target_server_id}</p>
                <p className="mt-2 text-sm text-slate-300">{host.members.join(', ') || host.error || 'No members returned.'}</p>
                <p className="mt-2 text-xs text-slate-500">Primary: {host.primary_members.join(', ') || 'none'} | Supplementary: {host.supplementary_members.join(', ') || 'none'}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}

function permissionModelFor(name: string): Array<{ label: string; tone: 'neutral' | 'privileged' | 'runtime' | 'observe' }> {
  const normalized = name.toLowerCase();
  const permissions = [];
  if (normalized.includes('docker')) {
    permissions.push({ label: 'docker socket', tone: 'runtime' as const }, { label: 'compose management', tone: 'runtime' as const }, { label: 'runtime logs', tone: 'observe' as const });
  }
  if (normalized.includes('sudo') || normalized.includes('wheel') || normalized.includes('admin')) {
    permissions.push({ label: 'privileged execution', tone: 'privileged' as const });
  }
  if (normalized.includes('journal') || normalized === 'adm') {
    permissions.push({ label: 'systemd journal access', tone: 'observe' as const });
  }
  if (normalized.includes('www') || normalized.includes('web')) {
    permissions.push({ label: 'web runtime paths', tone: 'runtime' as const });
  }
  if (normalized.includes('libvirt') || normalized.includes('virt')) {
    permissions.push({ label: 'virtualization management', tone: 'runtime' as const });
  }
  return permissions.length ? permissions : [{ label: 'standard group membership', tone: 'neutral' as const }];
}
