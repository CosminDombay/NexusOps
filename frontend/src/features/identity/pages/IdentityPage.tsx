import { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listCredentials } from '../../credentials/api/credentialsApi';
import type { Credential } from '../../credentials/types/credential';
import { listServers } from '../../inventory/api/serversApi';
import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import type { BulkExecutionResponse } from '../../jobs/types/job';
import {
  addGroupMembers,
  adoptLinuxGroup,
  adoptLinuxUser,
  applyPermission,
  createLinuxGroup,
  createLinuxUser,
  createSSHKey,
  deleteLinuxGroup,
  deleteLinuxUser,
  deploySSHKey,
  disableLinuxUserShell,
  discoverGroupMembers,
  discoverGroups,
  discoverUserGroups,
  discoverUsers,
  expireLinuxUserPassword,
  listAccessProfiles,
  listGroupPresets,
  listLinuxGroups,
  listLinuxUsers,
  listPermissionPresets,
  listPermissionTemplates,
  listSSHKeys,
  lockLinuxUser,
  removeGroupMembers,
  replicateLinuxGroup,
  replicateLinuxUser,
  revokeSSHKey,
  unlockLinuxUser,
  updateLinuxGroup,
  updateLinuxUser,
} from '../api/identityApi';
import { IdentityActionsDrawer, type IdentityActionForm } from '../components/actions/IdentityActionsDrawer';
import { MetricTile, PermissionChip, SectionCard } from '../components/common/IdentityPrimitives';
import { IdentityExplorer } from '../components/explorer/IdentityExplorer';
import { GroupDetailsPanel } from '../components/groups/GroupDetailsPanel';
import { PermissionsWorkspace } from '../components/permissions/PermissionsWorkspace';
import { SshKeysWorkspace } from '../components/ssh/SshKeysWorkspace';
import { UserDetailsPanel } from '../components/users/UserDetailsPanel';
import type {
  AccessProfile,
  DiscoveredGroup,
  DiscoveredUser,
  GroupMembership,
  GroupPreset,
  LinuxGroup,
  LinuxUser,
  PermissionPreset,
  PermissionTemplate,
  SSHKey,
  UserGroupMembership,
} from '../types/identity';
import { buildIdentityEntities, type IdentityEntity } from '../utils/entityModel';

const initialForm: IdentityActionForm = {
  username: 'deploy',
  shell: '/bin/bash',
  passwordCredentialId: '',
  sudoMode: 'password',
  groups: 'docker,www-data',
  groupName: 'deploy',
  groupDescription: '',
  memberNames: 'deploy',
  keyName: 'deploy-key',
  publicKey: '',
  keyUsername: 'deploy',
  permissionPath: '/opt/app',
  permissionOwner: 'deploy',
  permissionGroup: 'deploy',
  permissionMode: '0755',
  permissionRecursive: false,
};

export function IdentityPage() {
  const targetSelector = useTargetSelection('bulk');
  const [servers, setServers] = useState<Server[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [users, setUsers] = useState<LinuxUser[]>([]);
  const [groups, setGroups] = useState<LinuxGroup[]>([]);
  const [sshKeys, setSshKeys] = useState<SSHKey[]>([]);
  const [permissions, setPermissions] = useState<PermissionTemplate[]>([]);
  const [accessProfiles, setAccessProfiles] = useState<AccessProfile[]>([]);
  const [groupPresets, setGroupPresets] = useState<GroupPreset[]>([]);
  const [permissionPresets, setPermissionPresets] = useState<PermissionPreset[]>([]);
  const [discoveredGroups, setDiscoveredGroups] = useState<DiscoveredGroup[]>([]);
  const [discoveredUsers, setDiscoveredUsers] = useState<DiscoveredUser[]>([]);
  const [userMembership, setUserMembership] = useState<UserGroupMembership | null>(null);
  const [groupMembership, setGroupMembership] = useState<GroupMembership | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [explorerSearch, setExplorerSearch] = useState('');
  const [form, setForm] = useState<IdentityActionForm>(initialForm);
  const [result, setResult] = useState<BulkExecutionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);

  const selectedTargetIds = targetSelector.selection.mode === 'bulk'
    ? targetSelector.selection.selectedIds
    : targetSelector.selection.selectedId
      ? [targetSelector.selection.selectedId]
      : [];
  const targetsReady = selectedTargetIds.length > 0;

  const entities = useMemo(() => buildIdentityEntities({ users, groups, discoveredUsers, discoveredGroups, sshKeys, permissions }), [users, groups, discoveredUsers, discoveredGroups, sshKeys, permissions]);
  const selectedEntity = entities.find((entity) => entity.id === selectedEntityId) ?? entities[0] ?? null;
  const selectedUser = selectedEntity?.kind === 'user' ? selectedEntity.user : users.find((user) => user.username === form.username) ?? null;
  const selectedGroup = selectedEntity?.kind === 'group' ? selectedEntity.group : groups.find((group) => group.name === form.groupName) ?? null;
  const selectedDiscoveredUser = selectedEntity?.kind === 'discovered-user' ? selectedEntity.user : undefined;
  const selectedDiscoveredGroup = selectedEntity?.kind === 'discovered-group' ? selectedEntity.group : discoveredGroups.find((group) => group.name === form.groupName);
  const selectedKey = selectedEntity?.kind === 'ssh-key' ? selectedEntity.keyRecord : sshKeys[0] ?? null;

  const commandPreview = useMemo(() => {
    const groupList = splitCsv(form.groups);
    const adminGroup = groupList.includes('__admin__') ? ['resolve admin group: sudo/wheel'] : [];
    const groupCommands = groupList.filter((group) => group !== '__admin__').map((group) => `usermod -aG ${group} ${form.username}`);
    return selectedEntity?.kind?.includes('group')
      ? groupCommands.length ? groupCommands : [`groupadd ${form.groupName}`]
      : selectedEntity?.kind === 'permission'
        ? [`chown ${form.permissionOwner}:${form.permissionGroup} ${form.permissionPath}`, `chmod ${form.permissionMode} ${form.permissionPath}`]
        : [`useradd -m -d /home/${form.username} -s ${form.shell} ${form.username}`, ...adminGroup, ...groupCommands];
  }, [form, selectedEntity]);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextServers, nextCredentials, nextUsers, nextGroups, nextKeys, nextPermissions, nextProfiles, nextGroupPresets, nextPermissionPresets] = await Promise.all([
        listServers(),
        listCredentials(),
        listLinuxUsers(),
        listLinuxGroups(),
        listSSHKeys(),
        listPermissionTemplates(),
        listAccessProfiles(),
        listGroupPresets(),
        listPermissionPresets(),
      ]);
      setServers(nextServers);
      setCredentials(nextCredentials);
      setUsers(nextUsers);
      setGroups(nextGroups);
      setSshKeys(nextKeys);
      setPermissions(nextPermissions);
      setAccessProfiles(nextProfiles);
      setGroupPresets(nextGroupPresets);
      setPermissionPresets(nextPermissionPresets);
      setSelectedEntityId((current) => current ?? (nextGroups[0] ? `group:${nextGroups[0].id}` : nextUsers[0] ? `user:${nextUsers[0].id}` : null));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function work(action: () => Promise<BulkExecutionResponse | null | void>) {
    setIsWorking(true);
    setError(null);
    try {
      const nextResult = await action();
      if (nextResult) setResult(nextResult);
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function selectEntity(entity: IdentityEntity) {
    setSelectedEntityId(entity.id);
    if (entity.kind === 'user') {
      setForm((current) => ({
        ...current,
        username: entity.user.username,
        shell: entity.user.shell,
        sudoMode: entity.user.sudo_enabled ? (entity.user.sudo_nopasswd ? 'nopasswd' : 'password') : 'none',
        passwordCredentialId: '',
      }));
      setUserMembership(null);
    }
    if (entity.kind === 'discovered-user') {
      setForm((current) => ({ ...current, username: entity.user.username, shell: entity.user.shell ?? '/bin/bash' }));
      setUserMembership(null);
    }
    if (entity.kind === 'group') {
      setForm((current) => ({ ...current, groupName: entity.group.name, groupDescription: entity.group.description ?? '', memberNames: '' }));
      setGroupMembership(null);
    }
    if (entity.kind === 'discovered-group') {
      setForm((current) => ({ ...current, groupName: entity.group.name, groupDescription: `Discovered on ${entity.group.hosts.join(', ')}`, memberNames: entity.group.members.join(',') }));
      setGroupMembership(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader title="Identity" description="Operational Linux identity orchestration for users, groups, credentials, SSH keys, and filesystem access." />

      {error ? (
        <div className="flex items-center gap-2 rounded-md border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          {error}
        </div>
      ) : null}
      {isLoading ? <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300">Loading identity dashboard...</div> : null}

      <TargetSelector
        servers={servers}
        selection={targetSelector.selection}
        filters={targetSelector.filters}
        title="Replication targets"
        description="Target selection drives live discovery, replication, and account lifecycle actions."
        onFiltersChange={targetSelector.setFilters}
        onSelectionChange={(selection) => {
          targetSelector.setMode(selection.mode);
          targetSelector.setSelectedId(selection.selectedId);
          targetSelector.setSelectedIds(selection.selectedIds);
        }}
      />

      <div className="grid gap-4 2xl:grid-cols-[340px_minmax(0,1fr)_380px]">
        <IdentityExplorer entities={entities} selectedEntityId={selectedEntity?.id ?? null} search={explorerSearch} onSearchChange={setExplorerSearch} onSelect={selectEntity} />
        <main className="min-w-0 space-y-4">
          <DashboardSummary users={users} groups={groups} discoveredUsers={discoveredUsers} discoveredGroups={discoveredGroups} targets={selectedTargetIds.length} />
          {selectedEntity?.kind === 'group' || selectedEntity?.kind === 'discovered-group' ? (
            <GroupDetailsPanel group={selectedGroup ?? undefined} discoveredGroup={selectedDiscoveredGroup} membership={groupMembership} users={users} userMembership={userMembership} />
          ) : selectedEntity?.kind === 'ssh-key' ? (
            <SshKeysWorkspace keys={sshKeys} />
          ) : selectedEntity?.kind === 'permission' ? (
            <PermissionsWorkspace permissions={permissions} presets={permissionPresets} />
          ) : (
            <UserDetailsPanel user={selectedUser ?? undefined} discoveredUser={selectedDiscoveredUser} membership={userMembership} sshKeys={sshKeys} credentials={credentials} />
          )}
          {result ? <ExecutionResult result={result} /> : null}
        </main>
        <IdentityActionsDrawer
          selectedKind={selectedEntity?.kind ?? null}
          form={form}
          users={selectedUser ? [selectedUser] : users}
          groups={selectedGroup ? [selectedGroup] : groups}
          accessProfiles={accessProfiles}
          groupPresets={groupPresets}
          permissionPresets={permissionPresets}
          credentials={credentials}
          hasSelectedSshKey={selectedKey !== null}
          targetsReady={targetsReady}
          isWorking={isWorking}
          commandPreview={commandPreview}
          onFormChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          onCreateUser={() => void work(createOrAdoptUser)}
          onUpdateUser={() => void work(updateSelectedUser)}
          onReplicateUser={() => void work(async () => selectedUser ? replicateLinuxUser(selectedUser.id, selectedTargetIds) : null)}
          onLockUser={() => void work(async () => selectedUser ? lockLinuxUser(selectedUser.id, selectedTargetIds) : null)}
          onUnlockUser={() => void work(async () => selectedUser ? unlockLinuxUser(selectedUser.id, selectedTargetIds) : null)}
          onDisableShell={() => void work(async () => selectedUser ? disableLinuxUserShell(selectedUser.id, selectedTargetIds) : null)}
          onExpirePassword={() => void work(async () => selectedUser ? expireLinuxUserPassword(selectedUser.id, selectedTargetIds) : null)}
          onInspectUserGroups={() => void inspectUserGroups()}
          onDeleteUser={() => {
            if (!selectedUser || !window.confirm(`Delete managed user ${selectedUser.username}?`)) return;
            void work(async () => { await deleteLinuxUser(selectedUser.id, selectedTargetIds); setSelectedEntityId(null); return null; });
          }}
          onCreateGroup={() => void work(createOrAdoptGroup)}
          onUpdateGroup={() => void work(updateSelectedGroup)}
          onReplicateGroup={() => void work(async () => selectedGroup ? replicateLinuxGroup(selectedGroup.id, selectedTargetIds) : null)}
          onAddMembers={() => void work(async () => selectedGroup ? addGroupMembers(selectedGroup.id, splitCsv(form.memberNames), selectedTargetIds) : null)}
          onRemoveMembers={() => void work(async () => selectedGroup ? removeGroupMembers(selectedGroup.id, splitCsv(form.memberNames), selectedTargetIds) : null)}
          onInspectGroupMembers={() => void inspectGroupMembers()}
          onDeleteGroup={() => {
            if (!selectedGroup || !window.confirm(`Delete managed group ${selectedGroup.name}?`)) return;
            void work(async () => { await deleteLinuxGroup(selectedGroup.id, selectedTargetIds); setSelectedEntityId(null); return null; });
          }}
          onDiscoverUsers={() => void discoverUsersNow()}
          onDiscoverGroups={() => void discoverGroupsNow()}
          onSaveKey={() => void work(async () => { await createSSHKey({ name: form.keyName, public_key: form.publicKey }); return null; })}
          onDeployKey={() => void work(async () => selectedKey ? deploySSHKey(selectedKey.id, form.keyUsername, selectedTargetIds) : null)}
          onRevokeKey={() => void work(async () => selectedKey ? revokeSSHKey(selectedKey.id, form.keyUsername, selectedTargetIds) : null)}
          onApplyPermission={() => void work(() => applyPermission({ path: form.permissionPath, owner: form.permissionOwner, group: form.permissionGroup, mode: form.permissionMode, recursive: form.permissionRecursive, target_server_ids: selectedTargetIds }))}
        />
      </div>
    </div>
  );

  async function createOrAdoptUser() {
    const payload = {
      username: form.username,
      shell: form.shell,
      password_credential_ref: form.passwordCredentialId || null,
      sudo_enabled: form.sudoMode !== 'none',
      sudo_nopasswd: form.sudoMode === 'nopasswd',
      locked: false,
      managed: true,
      supplementary_groups: splitCsv(form.groups),
      target_server_ids: selectedTargetIds,
    };
    const response = selectedEntity?.kind === 'discovered-user'
      ? await adoptLinuxUser({ ...payload, target_server_ids: [] })
      : await createLinuxUser(payload);
    setSelectedEntityId(`user:${response.item.id}`);
    if (selectedEntity?.kind === 'discovered-user' && selectedTargetIds.length) {
      const syncResponse = await updateLinuxUser(response.item.id, {
        shell: form.shell,
        home_directory: response.item.home_directory || `/home/${form.username}`,
        password_credential_ref: form.passwordCredentialId || null,
        sudo_enabled: form.sudoMode !== 'none',
        sudo_nopasswd: form.sudoMode === 'nopasswd',
        locked: response.item.locked,
        managed: true,
        supplementary_groups: splitCsv(form.groups),
        target_server_ids: selectedTargetIds,
      });
      return syncResponse.replication;
    }
    return response.replication;
  }

  async function updateSelectedUser() {
    if (!selectedUser) return null;
    const response = await updateLinuxUser(selectedUser.id, {
      shell: form.shell,
      home_directory: `/home/${form.username}`,
      password_credential_ref: form.passwordCredentialId || null,
      sudo_enabled: form.sudoMode !== 'none',
      sudo_nopasswd: form.sudoMode === 'nopasswd',
      locked: selectedUser.locked,
      managed: true,
      supplementary_groups: splitCsv(form.groups),
      target_server_ids: selectedTargetIds,
    });
    return response.replication;
  }

  async function createOrAdoptGroup() {
    const payload = { name: form.groupName, description: form.groupDescription || null, managed: true, target_server_ids: selectedTargetIds };
    const response = selectedEntity?.kind === 'discovered-group'
      ? await adoptLinuxGroup({ ...payload, managed: true, target_server_ids: [] })
      : await createLinuxGroup(payload);
    setSelectedEntityId(`group:${response.item.id}`);
    if (selectedEntity?.kind === 'discovered-group' && selectedTargetIds.length) {
      const syncResponse = await replicateLinuxGroup(response.item.id, selectedTargetIds);
      return syncResponse;
    }
    return response.replication;
  }

  async function updateSelectedGroup() {
    if (!selectedGroup) return null;
    const response = await updateLinuxGroup(selectedGroup.id, { name: form.groupName, description: form.groupDescription || null, managed: true, target_server_ids: selectedTargetIds });
    return response.replication;
  }

  async function inspectUserGroups() {
    if (!targetsReady || !form.username.trim()) return;
    setIsWorking(true);
    setError(null);
    try {
      setUserMembership(await discoverUserGroups(form.username, selectedTargetIds));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function inspectGroupMembers() {
    if (!targetsReady || !form.groupName.trim()) return;
    setIsWorking(true);
    setError(null);
    try {
      setGroupMembership(await discoverGroupMembers(form.groupName, selectedTargetIds));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function discoverUsersNow() {
    if (!targetsReady) return;
    setIsWorking(true);
    setError(null);
    try {
      setDiscoveredUsers(await discoverUsers(selectedTargetIds));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function discoverGroupsNow() {
    if (!targetsReady) return;
    setIsWorking(true);
    setError(null);
    try {
      setDiscoveredGroups(await discoverGroups(selectedTargetIds));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }
}

function DashboardSummary({
  users,
  groups,
  discoveredUsers,
  discoveredGroups,
  targets,
}: {
  users: LinuxUser[];
  groups: LinuxGroup[];
  discoveredUsers: DiscoveredUser[];
  discoveredGroups: DiscoveredGroup[];
  targets: number;
}) {
  return (
    <section className="grid gap-3 md:grid-cols-4">
      <MetricTile label="Managed Users" value={users.length} detail={`${users.filter((user) => user.locked).length} locked`} />
      <MetricTile label="Managed Groups" value={groups.length} detail={`${groups.filter((group) => group.managed).length} managed`} />
      <MetricTile label="Discovered" value={discoveredUsers.length + discoveredGroups.length} detail="live inventory observations" />
      <MetricTile label="Targets" value={targets} detail="selected for operations" />
    </section>
  );
}

function ExecutionResult({ result }: { result: BulkExecutionResponse }) {
  return (
    <SectionCard title="Last Operation">
      <div className="flex flex-wrap gap-2">
        <PermissionChip label={`${result.success_count} succeeded`} tone="runtime" />
        <PermissionChip label={`${result.failure_count} failed`} tone={result.failure_count ? 'privileged' : 'neutral'} />
        <PermissionChip label={result.operation_type} tone="observe" />
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {result.results.map((row) => (
          <div key={row.target_server_id} className="rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-white">{row.target_hostname ?? row.target_server_id}</p>
              <span className="text-xs text-slate-400">exit {row.job?.exit_code ?? 'n/a'}</span>
            </div>
            <p className={row.success ? 'text-emerald-200' : 'text-rose-200'}>{row.success ? 'success' : row.error ?? 'failed'}</p>
            {row.job?.correlation_id ? <p className="mt-1 font-mono text-xs text-slate-500">{row.job.correlation_id}</p> : null}
            {row.job?.stderr ? <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-rose-200">{row.job.stderr}</pre> : null}
            {row.job?.stdout ? <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-slate-300">{row.job.stdout}</pre> : null}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}
