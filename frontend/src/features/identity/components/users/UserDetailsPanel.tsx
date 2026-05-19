import { KeyRound, Lock, Shield, Terminal, Unlock, UserRound } from 'lucide-react';

import type { Credential } from '../../../credentials/types/credential';
import type { DiscoveredUser, LinuxUser, SSHKey, UserGroupMembership } from '../../types/identity';
import { MetricTile, PermissionChip, SectionCard, StatusBadge } from '../common/IdentityPrimitives';

export function UserDetailsPanel({
  user,
  discoveredUser,
  membership,
  sshKeys,
  credentials,
}: {
  user?: LinuxUser;
  discoveredUser?: DiscoveredUser;
  membership: UserGroupMembership | null;
  sshKeys: SSHKey[];
  credentials: Credential[];
}) {
  const username = user?.username ?? discoveredUser?.username ?? 'No user selected';
  const shell = user?.shell ?? discoveredUser?.shell ?? 'unknown';
  const home = user?.home_directory ?? discoveredUser?.home_directory ?? 'unknown';
  const groups = [...new Set(membership?.hosts.flatMap((host) => host.groups) ?? [])].sort();
  const status = user ? (user.locked ? 'locked' : 'active') : 'discovered';
  const passwordCredentials = credentials.filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password');

  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-md bg-cyan-400/15 text-cyan-100">
                <UserRound className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">{username}</h2>
                <p className="text-sm text-slate-400">{user ? 'Managed Linux account' : 'Discovered Linux account'}</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge state={user ? (user.managed ? 'synced' : 'unmanaged') : 'discovered'} />
            <StatusBadge state={user?.locked ? 'failed' : 'synced'} label={status} />
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <MetricTile label="Shell" value={<span className="text-sm">{shell}</span>} />
          <MetricTile label="Home" value={<span className="text-sm">{home}</span>} />
          <MetricTile label="Sudo" value={user?.sudo_enabled ? 'Enabled' : 'No'} detail={user?.sudo_nopasswd ? 'passwordless' : user?.sudo_enabled ? 'password required' : undefined} />
          <MetricTile label="Groups" value={groups.length || 'Unknown'} detail={membership ? `${membership.hosts.length} host inspection(s)` : 'inspect live state'} />
        </div>
      </section>

      <SectionCard title="Effective Permissions">
        <div className="flex flex-wrap gap-2">
          {user?.sudo_enabled ? <PermissionChip label="privileged execution" tone="privileged" /> : null}
          {groups.includes('docker') ? <PermissionChip label="docker socket" tone="runtime" /> : null}
          {groups.includes('docker') ? <PermissionChip label="compose management" tone="runtime" /> : null}
          {groups.includes('adm') || groups.includes('systemd-journal') ? <PermissionChip label="runtime logs" tone="observe" /> : null}
          {groups.includes('www-data') ? <PermissionChip label="web-runtime" tone="runtime" /> : null}
          {!groups.length && !user?.sudo_enabled ? <p className="text-sm text-slate-400">Inspect live groups to calculate effective permissions.</p> : null}
        </div>
      </SectionCard>

      <SectionCard title="Groups">
        {membership ? (
          <div className="grid gap-3 md:grid-cols-2">
            {membership.hosts.map((host) => (
              <div key={host.target_server_id} className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
                <p className="text-sm font-semibold text-white">{host.target_hostname ?? host.target_server_id}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {host.groups.map((group) => <PermissionChip key={group} label={group} />)}
                  {!host.groups.length ? <span className="text-xs text-slate-500">{host.error ?? 'No groups returned.'}</span> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">Run Inspect user groups to load per-host Linux group membership.</p>
        )}
      </SectionCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard title="SSH Keys">
          <div className="space-y-2">
            {sshKeys.map((key) => (
              <div key={key.id} className="flex items-center gap-2 rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-200">
                <KeyRound className="h-4 w-4 text-slate-500" aria-hidden="true" />
                {key.name}
              </div>
            ))}
            {!sshKeys.length ? <p className="text-sm text-slate-400">No SSH key records yet.</p> : null}
          </div>
        </SectionCard>
        <SectionCard title="Credential References">
          <div className="space-y-2">
            {passwordCredentials.slice(0, 5).map((credential) => (
              <div key={credential.id} className="flex items-center justify-between rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2">
                <span className="text-sm font-medium text-slate-100">{credential.name}</span>
                <PermissionChip label={credential.credential_type} tone="observe" />
              </div>
            ))}
            {!passwordCredentials.length ? <p className="text-sm text-slate-400">Create password credentials to enable reset workflows.</p> : null}
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Account Signals">
        <div className="grid gap-3 md:grid-cols-3">
          <Signal icon={user?.locked ? Lock : Unlock} label="Account status" value={user?.locked ? 'Locked' : 'Unlocked'} />
          <Signal icon={Terminal} label="Interactive shell" value={shell.includes('nologin') || shell.includes('false') ? 'Disabled' : 'Enabled'} />
          <Signal icon={Shield} label="Sync state" value={user ? 'Managed record' : 'Discovered only'} />
        </div>
      </SectionCard>
    </div>
  );
}

function Signal({ icon: Icon, label, value }: { icon: typeof Lock; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-slate-700 bg-slate-950/50 p-3">
      <Icon className="h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-xs uppercase text-slate-500">{label}</p>
        <p className="text-sm font-semibold text-white">{value}</p>
      </div>
    </div>
  );
}

