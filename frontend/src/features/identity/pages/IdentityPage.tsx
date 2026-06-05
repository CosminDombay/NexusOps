import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Eye,
  FileKey2,
  KeyRound,
  Lock,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  ShieldOff,
  Trash2,
  Unlock,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react';

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
import type { IdentityActionForm, IdentityActionMode } from '../components/actions/IdentityActionsDrawer';
import { IconButton, MetricTile, PermissionChip, SectionCard, SelectInput, TextInput } from '../components/common/IdentityPrimitives';
import { IdentityExplorer } from '../components/explorer/IdentityExplorer';
import { GroupDetailsPanel } from '../components/groups/GroupDetailsPanel';
import { UserDetailsPanel } from '../components/users/UserDetailsPanel';
import type {
  DiscoveredGroup,
  DiscoveredUser,
  GroupMembership,
  LinuxGroup,
  LinuxUser,
  PermissionPreset,
  PermissionTemplate,
  SSHKey,
  UserGroupMembership,
} from '../types/identity';
import { buildIdentityEntities, type IdentityEntity } from '../utils/entityModel';

type ModalMode = IdentityActionMode | 'discovery' | 'replication' | null;

const initialForm: IdentityActionForm = {
  username: 'deploy',
  shell: '/bin/bash',
  passwordCredentialId: '',
  executionCredentialId: '',
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
  const [permissionPresets, setPermissionPresets] = useState<PermissionPreset[]>([]);
  const [discoveredGroups, setDiscoveredGroups] = useState<DiscoveredGroup[]>([]);
  const [discoveredUsers, setDiscoveredUsers] = useState<DiscoveredUser[]>([]);
  const [userMembership, setUserMembership] = useState<UserGroupMembership | null>(null);
  const [groupMembership, setGroupMembership] = useState<GroupMembership | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [explorerSearch, setExplorerSearch] = useState('');
  const [form, setForm] = useState<IdentityActionForm>(initialForm);
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [modalIntent, setModalIntent] = useState<'create' | 'edit'>('edit');
  const [groupMemberOperation, setGroupMemberOperation] = useState<'add' | 'remove'>('add');
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
  const passwordCredentials = credentials.filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password');

  const entities = useMemo(
    () => buildIdentityEntities({ users, groups, discoveredUsers, discoveredGroups, sshKeys, permissions }),
    [users, groups, discoveredUsers, discoveredGroups, sshKeys, permissions],
  );
  const selectedEntity = entities.find((entity) => entity.id === selectedEntityId) ?? entities[0] ?? null;
  const selectedUser = selectedEntity?.kind === 'user' ? selectedEntity.user : null;
  const selectedGroup = selectedEntity?.kind === 'group' ? selectedEntity.group : null;
  const selectedDiscoveredUser = selectedEntity?.kind === 'discovered-user'
    ? selectedEntity.user
    : selectedUser
      ? discoveredUsers.find((user) => user.username === selectedUser.username)
      : undefined;
  const selectedDiscoveredGroup = selectedEntity?.kind === 'discovered-group' ? selectedEntity.group : undefined;
  const selectedKey = selectedEntity?.kind === 'ssh-key' ? selectedEntity.keyRecord : null;
  const selectedPermission = selectedEntity?.kind === 'permission' ? selectedEntity.permission : null;

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextServers, nextCredentials, nextUsers, nextGroups, nextKeys, nextPermissions, nextPermissionPresets] = await Promise.all([
        listServers(),
        listCredentials(),
        listLinuxUsers(),
        listLinuxGroups(),
        listSSHKeys(),
        listPermissionTemplates(),
        listPermissionPresets(),
      ]);
      setServers(nextServers);
      setCredentials(nextCredentials);
      setUsers(nextUsers);
      setGroups(nextGroups);
      setSshKeys(nextKeys);
      setPermissions(nextPermissions);
      setPermissionPresets(nextPermissionPresets);
      setSelectedEntityId((current) => current ?? (nextUsers[0] ? `user:${nextUsers[0].id}` : nextGroups[0] ? `group:${nextGroups[0].id}` : null));
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
      setModalMode(null);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function selectEntity(entity: IdentityEntity) {
    setSelectedEntityId(entity.id);
    setResult(null);
    if (entity.kind === 'user') {
      setForm((current) => ({
        ...current,
        username: entity.user.username,
        shell: entity.user.shell,
        sudoMode: entity.user.sudo_enabled ? (entity.user.sudo_nopasswd ? 'nopasswd' : 'password') : 'none',
        groups: current.groups,
        passwordCredentialId: '',
        executionCredentialId: current.executionCredentialId,
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
    if (entity.kind === 'ssh-key') {
      setForm((current) => ({ ...current, keyName: entity.keyRecord.name, publicKey: entity.keyRecord.public_key }));
    }
    if (entity.kind === 'permission') {
      setForm((current) => ({
        ...current,
        permissionPath: entity.permission.path,
        permissionOwner: entity.permission.owner ?? '',
        permissionGroup: entity.permission.group ?? '',
        permissionMode: entity.permission.mode ?? '0755',
        permissionRecursive: entity.permission.recursive,
      }));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader title="Identity" description="Inventory-first Linux identity management for discovery, inspection, replication, and controlled account operations." />

      {error ? (
        <div className="flex items-center gap-2 rounded-md border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          {error}
        </div>
      ) : null}
      {isLoading ? <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300">Loading identity dashboard...</div> : null}

      <QuickCreateBar
        users={users.length}
        groups={groups.length}
        keys={sshKeys.length}
        permissions={permissions.length}
        onCreateUser={() => openCreate('user')}
        onCreateGroup={() => openCreate('group')}
        onCreateKey={() => openCreate('ssh-key')}
        onCreatePermission={() => openCreate('permission')}
        onDiscovery={() => setModalMode('discovery')}
      />

      <div className="grid gap-4 2xl:grid-cols-[340px_minmax(0,1fr)_320px]">
        <IdentityExplorer entities={entities} selectedEntityId={selectedEntity?.id ?? null} search={explorerSearch} onSearchChange={setExplorerSearch} onSelect={selectEntity} />
        <main className="min-w-0 space-y-4">
          <ObjectSummary users={users} groups={groups} discoveredUsers={discoveredUsers} discoveredGroups={discoveredGroups} targets={selectedTargetIds.length} />
          <ObjectDetails
            entity={selectedEntity}
            user={selectedUser ?? undefined}
            discoveredUser={selectedDiscoveredUser}
            group={selectedGroup ?? undefined}
            discoveredGroup={selectedDiscoveredGroup}
            keyRecord={selectedKey ?? undefined}
            permission={selectedPermission ?? undefined}
            userMembership={userMembership}
            groupMembership={groupMembership}
            users={users}
            sshKeys={sshKeys}
            credentials={credentials}
          />
          {result ? <ExecutionResult result={result} /> : null}
        </main>
        <ContextActions
          entity={selectedEntity}
          targetsReady={targetsReady}
          targetCount={selectedTargetIds.length}
          isWorking={isWorking}
          onEdit={() => {
            setModalIntent('edit');
            setModalMode(kindToMode(selectedEntity));
          }}
          onReplicate={() => setModalMode('replication')}
          onInspectUserGroups={() => void inspectUserGroups()}
          onInspectGroupMembers={() => void inspectGroupMembers()}
          onLockUser={() => void work(async () => selectedUser ? lockLinuxUser(selectedUser.id, selectedTargetIds, executionCredentialRef()) : null)}
          onUnlockUser={() => void work(async () => selectedUser ? unlockLinuxUser(selectedUser.id, selectedTargetIds, executionCredentialRef()) : null)}
          onDisableShell={() => void work(async () => selectedUser ? disableLinuxUserShell(selectedUser.id, selectedTargetIds, executionCredentialRef()) : null)}
          onExpirePassword={() => void work(async () => selectedUser ? expireLinuxUserPassword(selectedUser.id, selectedTargetIds, executionCredentialRef()) : null)}
          onDelete={() => void deleteSelectedObject()}
        />
      </div>

      {modalMode && modalMode !== 'discovery' && modalMode !== 'replication' ? (
        <ActionModal
          mode={modalMode}
          form={form}
          users={users}
          groups={groups}
          selectedEntity={modalIntent === 'edit' ? selectedEntity : null}
          permissionPresets={permissionPresets}
          passwordCredentials={passwordCredentials}
          groupMemberOperation={groupMemberOperation}
          isWorking={isWorking}
          targetsReady={targetsReady}
          onClose={() => setModalMode(null)}
          onFormChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          onGroupMemberOperationChange={setGroupMemberOperation}
          onPresetSelect={applyPermissionPreset}
          onSubmit={() => void submitActionModal(modalMode)}
        />
      ) : null}

      {modalMode === 'discovery' ? (
        <DiscoveryModal
          servers={servers}
          targetSelector={targetSelector}
          discoveredUsers={discoveredUsers}
          discoveredGroups={discoveredGroups}
          isWorking={isWorking}
          onClose={() => setModalMode(null)}
          onDiscoverUsers={() => void discoverUsersNow()}
          onDiscoverGroups={() => void discoverGroupsNow()}
        />
      ) : null}

      {modalMode === 'replication' ? (
        <ReplicationModal
          entity={selectedEntity}
          servers={servers}
          targetSelector={targetSelector}
          credentialId={form.executionCredentialId}
          passwordCredentials={passwordCredentials}
          isWorking={isWorking}
          onCredentialChange={(executionCredentialId) => setForm((current) => ({ ...current, executionCredentialId }))}
          onClose={() => setModalMode(null)}
          onExecute={() => void replicateSelectedObject()}
        />
      ) : null}
    </div>
  );

  function openCreate(mode: IdentityActionMode) {
    setForm((current) => ({
      ...initialForm,
      passwordCredentialId: current.passwordCredentialId,
      executionCredentialId: current.executionCredentialId,
    }));
    setModalIntent('create');
    setGroupMemberOperation('add');
    setModalMode(mode);
  }

  function kindToMode(entity: IdentityEntity | null): IdentityActionMode {
    if (entity?.kind === 'group' || entity?.kind === 'discovered-group') return 'group';
    if (entity?.kind === 'ssh-key') return 'ssh-key';
    if (entity?.kind === 'permission') return 'permission';
    return 'user';
  }

  function applyPermissionPreset(presetId: string) {
    const preset = permissionPresets.find((item) => item.id === presetId);
    if (!preset) return;
    setForm((current) => ({
      ...current,
      permissionMode: preset.mode,
      permissionOwner: preset.owner ?? current.permissionOwner,
      permissionGroup: preset.group ?? current.permissionGroup,
      permissionRecursive: preset.recursive,
    }));
  }

  async function submitActionModal(mode: IdentityActionMode) {
    if (mode === 'user') await work(createOrUpdateOrAdoptUser);
    if (mode === 'group') await work(createOrUpdateOrAdoptGroup);
    if (mode === 'ssh-key') await work(saveOrDeployKey);
    if (mode === 'permission') await work(applyPermissionNow);
  }

  async function createOrUpdateOrAdoptUser() {
    const payload = {
      username: form.username,
      shell: form.shell,
      password_credential_ref: form.passwordCredentialId || null,
      execution_credential_ref: executionCredentialRef(),
      sudo_enabled: form.sudoMode !== 'none',
      sudo_nopasswd: form.sudoMode === 'nopasswd',
      locked: selectedUser?.locked ?? false,
      managed: true,
      supplementary_groups: splitCsv(form.groups),
      target_server_ids: selectedTargetIds,
    };
    if (modalIntent === 'edit' && selectedUser) {
      const response = await updateLinuxUser(selectedUser.id, {
        shell: form.shell,
        home_directory: selectedUser.home_directory || `/home/${form.username}`,
        password_credential_ref: form.passwordCredentialId || null,
        execution_credential_ref: executionCredentialRef(),
        sudo_enabled: form.sudoMode !== 'none',
        sudo_nopasswd: form.sudoMode === 'nopasswd',
        locked: selectedUser.locked,
        managed: true,
        supplementary_groups: splitCsv(form.groups),
        target_server_ids: selectedTargetIds,
      });
      return response.replication;
    }
    const response = modalIntent === 'edit' && selectedEntity?.kind === 'discovered-user'
      ? await adoptLinuxUser({ ...payload, target_server_ids: [] })
      : await createLinuxUser(payload);
    setSelectedEntityId(`user:${response.item.id}`);
    if (modalIntent === 'edit' && selectedEntity?.kind === 'discovered-user' && selectedTargetIds.length) {
      const syncResponse = await updateLinuxUser(response.item.id, {
        shell: form.shell,
        home_directory: response.item.home_directory || `/home/${form.username}`,
        password_credential_ref: form.passwordCredentialId || null,
        execution_credential_ref: executionCredentialRef(),
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

  async function createOrUpdateOrAdoptGroup() {
    const payload = {
      name: form.groupName,
      description: form.groupDescription || null,
      managed: true,
      target_server_ids: selectedTargetIds,
      credential_ref: executionCredentialRef(),
    };
    if (modalIntent === 'edit' && selectedGroup) {
      const response = await updateLinuxGroup(selectedGroup.id, payload);
      return await addMembersIfRequested(selectedGroup.id, response.replication);
    }
    const response = modalIntent === 'edit' && selectedEntity?.kind === 'discovered-group'
      ? await adoptLinuxGroup({ ...payload, target_server_ids: [] })
      : await createLinuxGroup(payload);
    setSelectedEntityId(`group:${response.item.id}`);
    if (modalIntent === 'edit' && selectedEntity?.kind === 'discovered-group' && selectedTargetIds.length) {
      const replication = await replicateLinuxGroup(response.item.id, selectedTargetIds, executionCredentialRef());
      return await addMembersIfRequested(response.item.id, replication);
    }
    return await addMembersIfRequested(response.item.id, response.replication);
  }

  async function addMembersIfRequested(groupId: string, fallback: BulkExecutionResponse | null) {
    const members = splitCsv(form.memberNames);
    if (!members.length || !targetsReady) return fallback;
    if (groupMemberOperation === 'remove') {
      return removeGroupMembers(groupId, members, selectedTargetIds, executionCredentialRef());
    }
    return addGroupMembers(groupId, members, selectedTargetIds, executionCredentialRef());
  }

  async function saveOrDeployKey() {
    if (modalIntent === 'create' || !selectedKey) {
      await createSSHKey({ name: form.keyName, public_key: form.publicKey });
      return null;
    }
    if (!targetsReady) return null;
    return deploySSHKey(selectedKey.id, form.keyUsername, selectedTargetIds);
  }

  async function applyPermissionNow() {
    return applyPermission({
      path: form.permissionPath,
      owner: form.permissionOwner || null,
      group: form.permissionGroup || null,
      mode: form.permissionMode || null,
      recursive: form.permissionRecursive,
      target_server_ids: selectedTargetIds,
    });
  }

  async function replicateSelectedObject() {
    if (!targetsReady) return;
    await work(async () => {
      if (selectedUser) return replicateLinuxUser(selectedUser.id, selectedTargetIds, executionCredentialRef());
      if (selectedGroup) return replicateLinuxGroup(selectedGroup.id, selectedTargetIds, executionCredentialRef());
      if (selectedKey) return deploySSHKey(selectedKey.id, form.keyUsername, selectedTargetIds);
      if (selectedPermission) return applyPermissionNow();
      return null;
    });
  }

  function executionCredentialRef() {
    return form.executionCredentialId || form.passwordCredentialId || null;
  }

  async function deleteSelectedObject() {
    if (selectedUser) {
      if (!window.confirm(`Delete managed user ${selectedUser.username}?`)) return;
      await work(async () => { await deleteLinuxUser(selectedUser.id, selectedTargetIds); setSelectedEntityId(null); return null; });
    }
    if (selectedGroup) {
      if (!window.confirm(`Delete managed group ${selectedGroup.name}?`)) return;
      await work(async () => { await deleteLinuxGroup(selectedGroup.id, selectedTargetIds); setSelectedEntityId(null); return null; });
    }
    if (selectedKey) {
      if (!targetsReady || !window.confirm(`Revoke SSH key ${selectedKey.name} from selected hosts?`)) return;
      await work(() => revokeSSHKey(selectedKey.id, form.keyUsername, selectedTargetIds));
    }
  }

  async function inspectUserGroups() {
    const username = selectedUser?.username ?? selectedDiscoveredUser?.username ?? form.username;
    if (!targetsReady || !username.trim()) return;
    setIsWorking(true);
    setError(null);
    try {
      setUserMembership(await discoverUserGroups(username, selectedTargetIds));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function inspectGroupMembers() {
    const groupName = selectedGroup?.name ?? selectedDiscoveredGroup?.name ?? form.groupName;
    if (!targetsReady || !groupName.trim()) return;
    setIsWorking(true);
    setError(null);
    try {
      setGroupMembership(await discoverGroupMembers(groupName, selectedTargetIds));
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

function QuickCreateBar({
  users,
  groups,
  keys,
  permissions,
  onCreateUser,
  onCreateGroup,
  onCreateKey,
  onCreatePermission,
  onDiscovery,
}: {
  users: number;
  groups: number;
  keys: number;
  permissions: number;
  onCreateUser: () => void;
  onCreateGroup: () => void;
  onCreateKey: () => void;
  onCreatePermission: () => void;
  onDiscovery: () => void;
}) {
  return (
    <section className="rounded-md border border-slate-700 bg-slate-900/80 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-2 sm:grid-cols-4">
          <MiniStat label="Users" value={users} />
          <MiniStat label="Groups" value={groups} />
          <MiniStat label="SSH keys" value={keys} />
          <MiniStat label="Permissions" value={permissions} />
        </div>
        <div className="flex flex-wrap gap-2">
          <IconButton icon={Plus} label="New User" onClick={onCreateUser} />
          <IconButton icon={Plus} label="New Group" onClick={onCreateGroup} />
          <IconButton icon={KeyRound} label="New SSH Key" onClick={onCreateKey} variant="secondary" />
          <IconButton icon={FileKey2} label="New Permission" onClick={onCreatePermission} variant="secondary" />
          <IconButton icon={Eye} label="Discovery" onClick={onDiscovery} variant="secondary" />
        </div>
      </div>
    </section>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-28 rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function ObjectSummary({
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
      <MetricTile label="Active users" value={users.filter((user) => !user.locked).length} detail={`${users.filter((user) => user.locked).length} disabled`} />
      <MetricTile label="Groups" value={groups.length} detail={`${groups.filter((group) => group.managed).length} synced`} />
      <MetricTile label="Pending imports" value={discoveredUsers.length + discoveredGroups.length} detail="from discovery review" />
      <MetricTile label="Selected hosts" value={targets} detail="used in modals" />
    </section>
  );
}

function ObjectDetails({
  entity,
  user,
  discoveredUser,
  group,
  discoveredGroup,
  keyRecord,
  permission,
  userMembership,
  groupMembership,
  users,
  sshKeys,
  credentials,
}: {
  entity: IdentityEntity | null;
  user?: LinuxUser;
  discoveredUser?: DiscoveredUser;
  group?: LinuxGroup;
  discoveredGroup?: DiscoveredGroup;
  keyRecord?: SSHKey;
  permission?: PermissionTemplate;
  userMembership: UserGroupMembership | null;
  groupMembership: GroupMembership | null;
  users: LinuxUser[];
  sshKeys: SSHKey[];
  credentials: Credential[];
}) {
  if (!entity) {
    return <SectionCard title="No Selection"><p className="text-sm text-slate-400">Create or discover an identity object to inspect details.</p></SectionCard>;
  }
  if (entity.kind === 'group' || entity.kind === 'discovered-group') {
    return <GroupDetailsPanel group={group} discoveredGroup={discoveredGroup} membership={groupMembership} users={users} userMembership={userMembership} />;
  }
  if (entity.kind === 'ssh-key') return <SshKeyDetails keyRecord={keyRecord} />;
  if (entity.kind === 'permission') return <PermissionDetails permission={permission} />;
  return <UserDetailsPanel user={user} discoveredUser={discoveredUser} membership={userMembership} sshKeys={sshKeys} credentials={credentials} />;
}

function SshKeyDetails({ keyRecord }: { keyRecord?: SSHKey }) {
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-cyan-400/15 text-cyan-100">
            <KeyRound className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">{keyRecord?.name ?? 'No SSH key selected'}</h2>
            <p className="text-sm text-slate-400">Managed public key record</p>
          </div>
        </div>
      </section>
      <SectionCard title="Key Information">
        <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-xs text-slate-300">{keyRecord?.public_key || 'No public key available.'}</pre>
      </SectionCard>
      <SectionCard title="Deployment Status">
        <p className="text-sm text-slate-400">Use Deploy or Revoke from context actions to apply this key to selected hosts.</p>
      </SectionCard>
    </div>
  );
}

function PermissionDetails({ permission }: { permission?: PermissionTemplate }) {
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-cyan-400/15 text-cyan-100">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">{permission?.path ?? 'No permission selected'}</h2>
            <p className="text-sm text-slate-400">{permission?.description ?? 'Filesystem permission template'}</p>
          </div>
        </div>
      </section>
      <section className="grid gap-3 md:grid-cols-4">
        <MetricTile label="Owner" value={permission?.owner ?? 'Unknown'} />
        <MetricTile label="Group" value={permission?.group ?? 'Unknown'} />
        <MetricTile label="Mode" value={permission?.mode ?? 'Unknown'} />
        <MetricTile label="Applied hosts" value="Unknown" detail="last operation shows remote results" />
      </section>
    </div>
  );
}

function ContextActions({
  entity,
  targetsReady,
  targetCount,
  isWorking,
  onEdit,
  onReplicate,
  onInspectUserGroups,
  onInspectGroupMembers,
  onLockUser,
  onUnlockUser,
  onDisableShell,
  onExpirePassword,
  onDelete,
}: {
  entity: IdentityEntity | null;
  targetsReady: boolean;
  targetCount: number;
  isWorking: boolean;
  onEdit: () => void;
  onReplicate: () => void;
  onInspectUserGroups: () => void;
  onInspectGroupMembers: () => void;
  onLockUser: () => void;
  onUnlockUser: () => void;
  onDisableShell: () => void;
  onExpirePassword: () => void;
  onDelete: () => void;
}) {
  const kind = entity?.kind;
  const isUser = kind === 'user' || kind === 'discovered-user';
  const isGroup = kind === 'group' || kind === 'discovered-group';
  const isKey = kind === 'ssh-key';
  const isPermission = kind === 'permission';
  const managed = kind === 'user' || kind === 'group' || kind === 'ssh-key' || kind === 'permission';
  return (
    <aside className="space-y-4 rounded-md border border-slate-700 bg-slate-900/85 p-4">
      <div>
        <p className="text-sm font-semibold text-white">Context Actions</p>
        <p className="mt-1 text-xs text-slate-400">{targetCount} host{targetCount === 1 ? '' : 's'} selected for remote operations.</p>
      </div>
      {!entity ? <p className="rounded-md border border-dashed border-slate-700 p-4 text-sm text-slate-500">Select an object to show available actions.</p> : null}
      {entity ? (
        <div className="grid gap-2">
          <IconButton icon={Pencil} label={managed ? 'Edit' : 'Import'} disabled={isWorking} onClick={onEdit} />
          <IconButton icon={RefreshCw} label="Replicate To Hosts" disabled={!targetsReady || isWorking || (!managed && !isPermission)} onClick={onReplicate} variant="secondary" />
        </div>
      ) : null}
      {isUser ? (
        <SectionCard title="User">
          <div className="grid gap-2">
            <IconButton icon={Eye} label="Inspect groups" disabled={!targetsReady || isWorking} onClick={onInspectUserGroups} variant="secondary" />
            <IconButton icon={Lock} label="Lock" disabled={!targetsReady || isWorking || kind !== 'user'} onClick={onLockUser} variant="secondary" />
            <IconButton icon={Unlock} label="Unlock" disabled={!targetsReady || isWorking || kind !== 'user'} onClick={onUnlockUser} variant="secondary" />
            <IconButton icon={ShieldOff} label="Disable shell" disabled={!targetsReady || isWorking || kind !== 'user'} onClick={onDisableShell} variant="secondary" />
            <IconButton icon={RotateCcw} label="Expire password" disabled={!targetsReady || isWorking || kind !== 'user'} onClick={onExpirePassword} variant="secondary" />
            <IconButton icon={Trash2} label="Delete" disabled={isWorking || kind !== 'user'} onClick={onDelete} variant="danger" />
          </div>
        </SectionCard>
      ) : null}
      {isGroup ? (
        <SectionCard title="Group">
          <div className="grid gap-2">
            <IconButton icon={Eye} label="Inspect members" disabled={!targetsReady || isWorking} onClick={onInspectGroupMembers} variant="secondary" />
            <IconButton icon={UsersRound} label="Edit members" disabled={isWorking || kind !== 'group'} onClick={onEdit} variant="secondary" />
            <IconButton icon={Trash2} label="Delete" disabled={isWorking || kind !== 'group'} onClick={onDelete} variant="danger" />
          </div>
        </SectionCard>
      ) : null}
      {isKey ? (
        <SectionCard title="SSH Key">
          <div className="grid gap-2">
            <IconButton icon={KeyRound} label="Deploy" disabled={!targetsReady || isWorking} onClick={onReplicate} variant="secondary" />
            <IconButton icon={RotateCcw} label="Rotate" disabled={isWorking} onClick={onEdit} variant="secondary" />
            <IconButton icon={Trash2} label="Revoke" disabled={!targetsReady || isWorking} onClick={onDelete} variant="danger" />
          </div>
        </SectionCard>
      ) : null}
      {isPermission ? (
        <SectionCard title="Permission">
          <div className="grid gap-2">
            <IconButton icon={ShieldCheck} label="Apply" disabled={!targetsReady || isWorking} onClick={onReplicate} variant="secondary" />
            <IconButton icon={Pencil} label="Modify" disabled={isWorking} onClick={onEdit} variant="secondary" />
          </div>
        </SectionCard>
      ) : null}
    </aside>
  );
}

function ActionModal({
  mode,
  form,
  users,
  groups,
  selectedEntity,
  permissionPresets,
  passwordCredentials,
  groupMemberOperation,
  isWorking,
  targetsReady,
  onClose,
  onFormChange,
  onGroupMemberOperationChange,
  onPresetSelect,
  onSubmit,
}: {
  mode: IdentityActionMode;
  form: IdentityActionForm;
  users: LinuxUser[];
  groups: LinuxGroup[];
  selectedEntity: IdentityEntity | null;
  permissionPresets: PermissionPreset[];
  passwordCredentials: Credential[];
  groupMemberOperation: 'add' | 'remove';
  isWorking: boolean;
  targetsReady: boolean;
  onClose: () => void;
  onFormChange: (patch: Partial<IdentityActionForm>) => void;
  onGroupMemberOperationChange: (operation: 'add' | 'remove') => void;
  onPresetSelect: (presetId: string) => void;
  onSubmit: () => void;
}) {
  const title = selectedEntity ? actionTitle(mode, selectedEntity) : createTitle(mode);
  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-4">
        {mode === 'user' ? (
          <div className="space-y-3">
            <TextInput label="Username" value={form.username} onChange={(value) => onFormChange({ username: value })} />
            <SelectInput label="Shell" value={form.shell} onChange={(value) => onFormChange({ shell: value })}>
              <option value="/bin/bash">Standard bash</option>
              <option value="/bin/zsh">ZSH</option>
              <option value="/bin/rbash">Restricted shell</option>
              <option value="/usr/sbin/nologin">No login shell</option>
              <option value="/bin/false">False shell</option>
            </SelectInput>
            <SelectInput label="Sudo access" value={form.sudoMode} onChange={(value) => onFormChange({ sudoMode: value })}>
              <option value="none">No elevated access</option>
              <option value="password">Require password for sudo</option>
              <option value="nopasswd">Passwordless sudo</option>
            </SelectInput>
            <SelectInput label="Account password credential" value={form.passwordCredentialId} onChange={(value) => onFormChange({ passwordCredentialId: value })}>
              <option value="">Do not set account password</option>
              {passwordCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
            </SelectInput>
            <SelectInput label="Execution / sudo credential" value={form.executionCredentialId} onChange={(value) => onFormChange({ executionCredentialId: value })}>
              <option value="">Use account password or target saved credential</option>
              {passwordCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
            </SelectInput>
            <TextInput label="Groups" value={form.groups} onChange={(value) => onFormChange({ groups: value })} placeholder="docker,www-data" />
          </div>
        ) : null}
        {mode === 'group' ? (
          <div className="space-y-3">
            <TextInput label="Group name" value={form.groupName} onChange={(value) => onFormChange({ groupName: value })} />
            <TextInput label="Description" value={form.groupDescription} onChange={(value) => onFormChange({ groupDescription: value })} />
            {selectedEntity ? (
              <div className="grid grid-cols-2 gap-2 rounded-md border border-slate-700 bg-slate-950/50 p-2">
                <button
                  className={`h-9 rounded-md border text-sm font-semibold transition ${groupMemberOperation === 'add' ? 'border-cyan-300 bg-cyan-400 text-slate-950' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500 hover:text-white'}`}
                  type="button"
                  onClick={() => onGroupMemberOperationChange('add')}
                >
                  Add members
                </button>
                <button
                  className={`h-9 rounded-md border text-sm font-semibold transition ${groupMemberOperation === 'remove' ? 'border-cyan-300 bg-cyan-400 text-slate-950' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500 hover:text-white'}`}
                  type="button"
                  onClick={() => onGroupMemberOperationChange('remove')}
                >
                  Remove members
                </button>
              </div>
            ) : null}
            <TextInput
              label={selectedEntity ? `Members to ${groupMemberOperation}` : 'Members to add'}
              value={form.memberNames}
              onChange={(value) => onFormChange({ memberNames: value })}
              placeholder="deploy,cerberus"
            />
            <SelectInput label="Execution / sudo credential" value={form.executionCredentialId} onChange={(value) => onFormChange({ executionCredentialId: value })}>
              <option value="">Use target saved credential</option>
              {passwordCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
            </SelectInput>
          </div>
        ) : null}
        {mode === 'ssh-key' ? (
          <div className="space-y-3">
            <TextInput label="Key name" value={form.keyName} onChange={(value) => onFormChange({ keyName: value })} />
            <TextInput label="Assigned user" value={form.keyUsername} onChange={(value) => onFormChange({ keyUsername: value })} />
            <label className="block">
              <span className="text-xs font-semibold uppercase text-slate-400">Public key</span>
              <textarea className="mt-2 min-h-36 w-full rounded-md border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-white outline-none focus:border-cyan-300" value={form.publicKey} onChange={(event) => onFormChange({ publicKey: event.target.value })} />
            </label>
          </div>
        ) : null}
        {mode === 'permission' ? (
          <div className="space-y-3">
            <SelectInput label="Permission preset" value="" onChange={onPresetSelect}>
              <option value="">Select template...</option>
              {permissionPresets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name} ({preset.mode})</option>)}
            </SelectInput>
            <TextInput label="Path" value={form.permissionPath} onChange={(value) => onFormChange({ permissionPath: value })} />
            <TextInput label="Owner" value={form.permissionOwner} onChange={(value) => onFormChange({ permissionOwner: value })} />
            <TextInput label="Group" value={form.permissionGroup} onChange={(value) => onFormChange({ permissionGroup: value })} />
            <TextInput label="Mode" value={form.permissionMode} onChange={(value) => onFormChange({ permissionMode: value })} />
            <label className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <input checked={form.permissionRecursive} className="h-4 w-4 rounded border-slate-700" type="checkbox" onChange={(event) => onFormChange({ permissionRecursive: event.target.checked })} />
              Recursive
            </label>
          </div>
        ) : null}
        <div className="rounded-md border border-slate-700 bg-slate-950/50 p-3 text-xs text-slate-400">
          Remote execution uses selected hosts from Replicate To Hosts or Discovery. Current target state: {targetsReady ? 'ready' : 'no hosts selected'}.
          {mode === 'group' ? ' Empty member lists only save the group record; member add/remove requires selected hosts.' : null}
          {users.length || groups.length ? null : null}
        </div>
        <div className="flex justify-end gap-2">
          <IconButton icon={X} label="Cancel" onClick={onClose} variant="secondary" />
          <IconButton icon={Plus} label={selectedEntity ? 'Save' : 'Create'} disabled={isWorking} onClick={onSubmit} />
        </div>
      </div>
    </Modal>
  );
}

function DiscoveryModal({
  servers,
  targetSelector,
  discoveredUsers,
  discoveredGroups,
  isWorking,
  onClose,
  onDiscoverUsers,
  onDiscoverGroups,
}: {
  servers: Server[];
  targetSelector: ReturnType<typeof useTargetSelection>;
  discoveredUsers: DiscoveredUser[];
  discoveredGroups: DiscoveredGroup[];
  isWorking: boolean;
  onClose: () => void;
  onDiscoverUsers: () => void;
  onDiscoverGroups: () => void;
}) {
  return (
    <Modal title="Discovery" onClose={onClose} wide>
      <div className="space-y-4">
        <TargetSelector
          servers={servers}
          selection={targetSelector.selection}
          filters={targetSelector.filters}
          title="Discovery hosts"
          description="Select hosts, discover Linux identities, then import discovered records from the explorer."
          onFiltersChange={targetSelector.setFilters}
          onSelectionChange={(selection) => {
            targetSelector.setMode(selection.mode);
            targetSelector.setSelectedId(selection.selectedId);
            targetSelector.setSelectedIds(selection.selectedIds);
          }}
        />
        <div className="flex flex-wrap gap-2">
          <IconButton icon={UserRound} label="Discover users" disabled={isWorking} onClick={onDiscoverUsers} />
          <IconButton icon={UsersRound} label="Discover groups" disabled={isWorking} onClick={onDiscoverGroups} variant="secondary" />
        </div>
        <section className="grid gap-3 md:grid-cols-2">
          <DiscoveryList title="Users" items={discoveredUsers.map((user) => `${user.username} on ${user.hosts.join(', ') || 'unknown'}`)} />
          <DiscoveryList title="Groups" items={discoveredGroups.map((group) => `${group.name} on ${group.hosts.join(', ') || 'unknown'}`)} />
        </section>
      </div>
    </Modal>
  );
}

function ReplicationModal({
  entity,
  servers,
  targetSelector,
  credentialId,
  passwordCredentials,
  isWorking,
  onCredentialChange,
  onClose,
  onExecute,
}: {
  entity: IdentityEntity | null;
  servers: Server[];
  targetSelector: ReturnType<typeof useTargetSelection>;
  credentialId: string;
  passwordCredentials: Credential[];
  isWorking: boolean;
  onCredentialChange: (value: string) => void;
  onClose: () => void;
  onExecute: () => void;
}) {
  const targetCount = targetSelector.selection.mode === 'bulk'
    ? targetSelector.selection.selectedIds.length
    : targetSelector.selection.selectedId
      ? 1
      : 0;
  return (
    <Modal title="Replicate To Hosts" onClose={onClose} wide>
      <div className="space-y-4">
        <TargetSelector
          servers={servers}
          selection={targetSelector.selection}
          filters={targetSelector.filters}
          title="Replication targets"
          description="Select hosts before executing this identity operation."
          onFiltersChange={targetSelector.setFilters}
          onSelectionChange={(selection) => {
            targetSelector.setMode(selection.mode);
            targetSelector.setSelectedId(selection.selectedId);
            targetSelector.setSelectedIds(selection.selectedIds);
          }}
        />
        <SelectInput label="Execution / sudo credential" value={credentialId} onChange={onCredentialChange}>
          <option value="">Use target saved credential</option>
          {passwordCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
        </SelectInput>
        <SectionCard title="Replication preview">
          <div className="space-y-2 text-sm text-slate-300">
            <p><span className="text-slate-500">Object:</span> {entity?.name ?? 'No object selected'}</p>
            <p><span className="text-slate-500">Operation:</span> {previewOperation(entity)}</p>
            <p><span className="text-slate-500">Targets:</span> {targetCount}</p>
          </div>
        </SectionCard>
        <div className="flex justify-end gap-2">
          <IconButton icon={X} label="Cancel" onClick={onClose} variant="secondary" />
          <IconButton icon={RefreshCw} label="Execute replication" disabled={!targetCount || isWorking} onClick={onExecute} />
        </div>
      </div>
    </Modal>
  );
}

function DiscoveryList({ title, items }: { title: string; items: string[] }) {
  return (
    <SectionCard title={title}>
      <div className="max-h-64 space-y-2 overflow-auto">
        {items.map((item) => <p key={item} className="rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-200">{item}</p>)}
        {!items.length ? <p className="text-sm text-slate-400">No discovery results loaded.</p> : null}
      </div>
    </SectionCard>
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

function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-slate-950/80 px-4 py-8">
      <section className={`w-full rounded-md border border-slate-700 bg-slate-900 shadow-2xl ${wide ? 'max-w-5xl' : 'max-w-2xl'}`}>
        <header className="flex items-center justify-between border-b border-slate-700 px-5 py-4">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <button className="rounded-md border border-slate-700 p-2 text-slate-300 hover:bg-slate-800" type="button" onClick={onClose}>
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>
        <div className="p-5">{children}</div>
      </section>
    </div>
  );
}

function actionTitle(mode: IdentityActionMode, entity: IdentityEntity) {
  if (entity.kind === 'discovered-user' || entity.kind === 'discovered-group') return `Import ${entity.name}`;
  if (mode === 'user') return `Edit user ${entity.name}`;
  if (mode === 'group') return `Edit group ${entity.name}`;
  if (mode === 'ssh-key') return `SSH key ${entity.name}`;
  return `Permission ${entity.name}`;
}

function createTitle(mode: IdentityActionMode) {
  if (mode === 'user') return 'New User';
  if (mode === 'group') return 'New Group';
  if (mode === 'ssh-key') return 'New SSH Key';
  return 'New Permission';
}

function previewOperation(entity: IdentityEntity | null) {
  if (!entity) return 'none';
  if (entity.kind === 'user') return 'Replicate user account, groups, shell, sudo state';
  if (entity.kind === 'group') return 'Replicate group record';
  if (entity.kind === 'ssh-key') return 'Deploy SSH key';
  if (entity.kind === 'permission') return 'Apply filesystem permission template';
  return 'Import first, then replicate';
}

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}
