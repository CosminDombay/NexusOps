import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Eye, KeyRound, Lock, Play, Shield, Trash2, Unlock, Users } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import type { BulkExecutionResponse } from '../jobs/types/job';
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
  discoverGroupMembers,
  discoverGroups,
  discoverUserGroups,
  discoverUsers,
  listAccessProfiles,
  listGroupPresets,
  listLinuxGroups,
  listLinuxUsers,
  listPermissionPresets,
  listPermissionTemplates,
  listSSHKeys,
  lockLinuxUser,
  replicateLinuxGroup,
  replicateLinuxUser,
  revokeSSHKey,
  unlockLinuxUser,
  updateLinuxGroup,
  updateLinuxUser,
} from './api/identityApi';
import type {
  AccessProfile,
  DiscoveredGroup,
  DiscoveredUser,
  GroupPreset,
  GroupMembership,
  LinuxGroup,
  LinuxUser,
  PermissionPreset,
  PermissionTemplate,
  SSHKey,
  UserGroupMembership,
} from './types/identity';

type Tab = 'access' | 'groups' | 'ssh' | 'permissions';
type PermissionScope = 'owner' | 'group' | 'other';
type PermissionBit = 'read' | 'write' | 'execute';

const shellOptions = [
  { id: 'standard', label: 'Standard Shell (bash)', value: '/bin/bash' },
  { id: 'zsh', label: 'ZSH', value: '/bin/zsh' },
  { id: 'restricted', label: 'Restricted Shell', value: '/bin/rbash' },
  { id: 'nologin', label: 'No Login', value: '/usr/sbin/nologin' },
  { id: 'custom', label: 'Custom', value: 'custom' },
];

const sudoOptions = [
  { id: 'none', label: 'No elevated access', sudo: false, nopasswd: false },
  { id: 'password', label: 'Require password for sudo', sudo: true, nopasswd: false },
  { id: 'nopasswd', label: 'Passwordless admin access', sudo: true, nopasswd: true },
];

export function IdentityPage() {
  const [tab, setTab] = useState<Tab>('access');
  const [servers, setServers] = useState<Server[]>([]);
  const targetSelector = useTargetSelection('bulk');
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
  const [result, setResult] = useState<BulkExecutionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedGroupId, setSelectedGroupId] = useState('');

  const [profileId, setProfileId] = useState('deployment-operator');
  const [username, setUsername] = useState('deploy');
  const [passwordCredentialId, setPasswordCredentialId] = useState('');
  const [shellPreset, setShellPreset] = useState('standard');
  const [customShell, setCustomShell] = useState('/bin/bash');
  const [sudoMode, setSudoMode] = useState('password');
  const [selectedGroups, setSelectedGroups] = useState<string[]>(['docker', 'www-data']);
  const [groupName, setGroupName] = useState('deploy');
  const [groupDescription, setGroupDescription] = useState('');
  const [memberNames, setMemberNames] = useState('deploy');
  const [keyName, setKeyName] = useState('deploy-key');
  const [publicKey, setPublicKey] = useState('');
  const [keyUsername, setKeyUsername] = useState('deploy');
  const [permissionPresetId, setPermissionPresetId] = useState('application-directory');
  const [path, setPath] = useState('/opt/app');
  const [owner, setOwner] = useState('deploy');
  const [permissionGroup, setPermissionGroup] = useState('deploy');
  const [mode, setMode] = useState('0755');
  const [recursive, setRecursive] = useState(false);
  const [matrix, setMatrix] = useState({
    owner: { read: true, write: true, execute: true },
    group: { read: true, write: false, execute: true },
    other: { read: true, write: false, execute: true },
  });

  const selectedProfile = accessProfiles.find((profile) => profile.id === profileId);
  const selectedUser = users.find((user) => user.id === selectedUserId) ?? users[0] ?? null;
  const selectedGroup = groups.find((group) => group.id === selectedGroupId) ?? groups[0] ?? null;
  const selectedKey = sshKeys[0] ?? null;
  const selectedTargetIds = targetSelector.selection.mode === 'bulk'
    ? targetSelector.selection.selectedIds
    : targetSelector.selection.selectedId
      ? [targetSelector.selection.selectedId]
      : [];
  const shell = shellPreset === 'custom' ? customShell : shellOptions.find((option) => option.id === shellPreset)?.value ?? '/bin/bash';
  const sudo = sudoOptions.find((option) => option.id === sudoMode) ?? sudoOptions[0];
  const passwordCredentials = credentials.filter((credential) => ['password', 'ssh_password'].includes(credential.credential_type));

  const commandPreview = useMemo(
    () => buildCommandPreview({
      username,
      shell,
      sudoMode,
      groups: selectedGroups,
      path,
      owner,
      permissionGroup,
      mode,
      recursive,
    }),
    [username, shell, sudoMode, selectedGroups, path, owner, permissionGroup, mode, recursive],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [
        nextServers,
        nextCredentials,
        nextUsers,
        nextGroups,
        nextKeys,
        nextPermissions,
        nextProfiles,
        nextGroupPresets,
        nextPermissionPresets,
      ] = await Promise.all([
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
      setSelectedUserId((current) => current || nextUsers[0]?.id || '');
      setSelectedGroupId((current) => current || nextGroups[0]?.id || '');
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
      if (nextResult) {
        setResult(nextResult);
      }
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function applyAccessProfile(nextProfileId: string) {
    setProfileId(nextProfileId);
    const profile = accessProfiles.find((candidate) => candidate.id === nextProfileId);
    if (!profile) {
      return;
    }
    setShellPreset(shellOptions.find((option) => option.value === profile.shell)?.id ?? 'custom');
    setCustomShell(profile.shell);
    setSudoMode(profile.sudo_enabled ? (profile.sudo_nopasswd ? 'nopasswd' : 'password') : 'none');
    setSelectedGroups(profile.supplementary_groups);
    setAdvanced(profile.advanced);
  }

  function applyPermissionPreset(nextPresetId: string) {
    setPermissionPresetId(nextPresetId);
    const preset = permissionPresets.find((candidate) => candidate.id === nextPresetId);
    if (!preset) {
      return;
    }
    setMode(preset.mode);
    setRecursive(preset.recursive);
    setMatrix(modeToMatrix(preset.mode));
  }

  function togglePermission(scope: PermissionScope, bit: PermissionBit) {
    const nextMatrix = {
      ...matrix,
      [scope]: { ...matrix[scope], [bit]: !matrix[scope][bit] },
    };
    setMatrix(nextMatrix);
    setMode(matrixToMode(nextMatrix));
  }

  async function handleDiscoverGroups() {
    if (!selectedTargetIds.length) {
      setError('Select target hosts before discovering groups.');
      return;
    }
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

  async function handleInspectGroupMembers() {
    if (!groupName.trim()) {
      setError('Select or enter a group before inspecting members.');
      return;
    }
    if (!selectedTargetIds.length) {
      setError('Select target hosts before inspecting group members.');
      return;
    }
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

  async function handleDiscoverUsers() {
    if (!selectedTargetIds.length) {
      setError('Select target hosts before discovering users.');
      return;
    }
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

  async function handleInspectUserGroups() {
    if (!username.trim()) {
      setError('Select or enter a username before inspecting groups.');
      return;
    }
    if (!selectedTargetIds.length) {
      setError('Select target hosts before inspecting user groups.');
      return;
    }
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

  function loadUser(user: LinuxUser) {
    setSelectedUserId(user.id);
    setUsername(user.username);
    setShellPreset(shellOptions.find((option) => option.value === user.shell)?.id ?? 'custom');
    setCustomShell(user.shell);
    setSudoMode(user.sudo_enabled ? (user.sudo_nopasswd ? 'nopasswd' : 'password') : 'none');
    setPasswordCredentialId('');
    setUserMembership(null);
  }

  function loadDiscoveredUser(user: DiscoveredUser) {
    setUsername(user.username);
    setShellPreset(shellOptions.find((option) => option.value === user.shell)?.id ?? 'custom');
    setCustomShell(user.shell ?? '/bin/bash');
    setUserMembership(null);
  }

  function loadGroup(group: LinuxGroup) {
    setSelectedGroupId(group.id);
    setGroupName(group.name);
    setGroupDescription(group.description ?? '');
    setGroupMembership(null);
  }

  function loadDiscoveredGroup(group: DiscoveredGroup) {
    setGroupName(group.name);
    setMemberNames(group.members.join(','));
    setGroupMembership(null);
  }

  useEffect(() => {
    void refresh();
  }, []);

  const targetsReady = selectedTargetIds.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Identity"
        description="Guided Linux access orchestration and replication across managed infrastructure."
      />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
      {isLoading ? <div className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-600">Loading identity workspace...</div> : null}

      <TargetSelector
        servers={servers}
        selection={targetSelector.selection}
        filters={targetSelector.filters}
        title="Replication targets"
        description="Select managed inventory hosts for identity propagation."
        onFiltersChange={targetSelector.setFilters}
        onSelectionChange={(selection) => {
          targetSelector.setMode(selection.mode);
          targetSelector.setSelectedId(selection.selectedId);
          targetSelector.setSelectedIds(selection.selectedIds);
        }}
      />

      <div className="flex flex-wrap gap-2">
        {[
          ['access', 'Access'],
          ['groups', 'Groups'],
          ['ssh', 'SSH Keys'],
          ['permissions', 'Permissions'],
        ].map(([value, label]) => (
          <button
            key={value}
            className={`rounded-md px-3 py-2 text-sm font-semibold transition ${tab === value ? 'bg-cyan-400 text-zinc-950' : 'border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'}`}
            type="button"
            onClick={() => setTab(value as Tab)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'access' ? (
        <Panel icon={Users} title="Access profile">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-zinc-950">Profile</span>
                <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={profileId} onChange={(event) => applyAccessProfile(event.target.value)}>
                  {accessProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>{profile.name}</option>
                  ))}
                </select>
                <p className="mt-2 text-sm text-zinc-500">{selectedProfile?.description}</p>
              </label>
              <div className="grid gap-4 lg:grid-cols-3">
                <label className="block lg:col-span-3">
                  <span className="text-sm font-medium text-zinc-950">Existing managed user</span>
                  <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={selectedUser?.id ?? ''} onChange={(event) => {
                    const user = users.find((candidate) => candidate.id === event.target.value);
                    if (user) loadUser(user);
                  }}>
                    <option value="">Select user</option>
                    {users.map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}
                  </select>
                </label>
                <TextInput label="Username" value={username} onChange={setUsername} />
                <label className="block">
                  <span className="text-sm font-medium text-zinc-950">Password credential</span>
                  <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={passwordCredentialId} onChange={(event) => setPasswordCredentialId(event.target.value)}>
                    <option value="">Do not set password</option>
                    {passwordCredentials.map((credential) => (
                      <option key={credential.id} value={credential.id}>{credential.name}</option>
                    ))}
                  </select>
                  <p className="mt-2 text-xs text-zinc-500">Optional; applies the Credential Manager secret with chpasswd during create or update.</p>
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-zinc-950">Shell</span>
                  <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={shellPreset} onChange={(event) => setShellPreset(event.target.value)}>
                    {shellOptions.map((option) => (
                      <option key={option.id} value={option.id}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-zinc-950">Sudo access</span>
                  <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={sudoMode} onChange={(event) => setSudoMode(event.target.value)}>
                    {sudoOptions.map((option) => (
                      <option key={option.id} value={option.id}>{option.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              {advanced ? (
                <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <TextInput label="Raw shell path" value={customShell} onChange={setCustomShell} />
                    <TextInput label="Raw groups" value={selectedGroups.join(',')} onChange={(value) => setSelectedGroups(splitCsv(value))} />
                  </div>
                  <p className="mt-3 text-xs text-zinc-500">Sudoers snippet preview: nexusops-{username} with {sudoMode === 'nopasswd' ? 'NOPASSWD' : sudoMode === 'password' ? 'password-required sudo' : 'no sudo'}.</p>
                </div>
              ) : null}
              <button className="text-sm font-semibold text-zinc-700 underline" type="button" onClick={() => setAdvanced((current) => !current)}>
                {advanced ? 'Hide advanced Linux options' : 'Show advanced Linux options'}
              </button>
              <div className="flex flex-wrap gap-2">
                <Action
                  disabled={!targetsReady || isWorking}
                  label="Create and replicate access"
                  onClick={() =>
                    void work(async () => {
                      const response = await createLinuxUser({
                        username,
                        shell,
                        password_credential_ref: passwordCredentialId || null,
                        sudo_enabled: sudo.sudo,
                        sudo_nopasswd: sudo.nopasswd,
                        locked: false,
                        managed: true,
                        supplementary_groups: selectedGroups,
                        target_server_ids: selectedTargetIds,
                      });
                      return response.replication;
                    })
                  }
                />
                <Action
                  disabled={!selectedUser || !targetsReady || isWorking}
                  label="Update selected user"
                  onClick={() =>
                    void work(async () => {
                      const response = await updateLinuxUser(selectedUser!.id, {
                        shell,
                        home_directory: `/home/${username}`,
                        password_credential_ref: passwordCredentialId || null,
                        sudo_enabled: sudo.sudo,
                        sudo_nopasswd: sudo.nopasswd,
                        locked: selectedUser!.locked,
                        managed: true,
                        supplementary_groups: selectedGroups,
                        target_server_ids: selectedTargetIds,
                      });
                      return response.replication;
                    })
                  }
                />
                <Action disabled={!selectedUser || !targetsReady || isWorking} label="Replicate selected user" onClick={() => void work(() => replicateLinuxUser(selectedUser!.id, selectedTargetIds))} />
                <Action icon={Lock} disabled={!selectedUser || !targetsReady || isWorking} label="Lock" onClick={() => void work(() => lockLinuxUser(selectedUser!.id, selectedTargetIds))} />
                <Action icon={Unlock} disabled={!selectedUser || !targetsReady || isWorking} label="Unlock" onClick={() => void work(() => unlockLinuxUser(selectedUser!.id, selectedTargetIds))} />
                <Action icon={Eye} disabled={!targetsReady || isWorking} label="Discover users" onClick={() => void handleDiscoverUsers()} />
                <Action icon={Eye} disabled={!targetsReady || isWorking || !username.trim()} label="Inspect user groups" onClick={() => void handleInspectUserGroups()} />
                <Action
                  icon={Trash2}
                  disabled={!selectedUser || isWorking}
                  label="Delete selected user"
                  variant="danger"
                  onClick={() => {
                    if (!selectedUser || !window.confirm(`Delete managed user ${selectedUser.username}? Select targets first if you also want it removed from Linux hosts.`)) return;
                    void work(async () => {
                      await deleteLinuxUser(selectedUser.id, selectedTargetIds);
                      setSelectedUserId('');
                      return null;
                    });
                  }}
                />
              </div>
            </div>
            <Preview commands={commandPreview.access} title="Generated access operations" />
          </div>
          {userMembership ? (
            <div className="mt-5 rounded-md border border-zinc-200 p-3">
              <h4 className="text-sm font-semibold text-zinc-950">Live groups for {userMembership.username}</h4>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                {userMembership.hosts.map((host) => (
                  <div key={host.target_server_id} className="rounded-md bg-zinc-50 px-3 py-2 text-sm">
                    <p className="font-semibold text-zinc-950">{host.target_hostname ?? host.target_server_id}</p>
                    <p className="mt-1 text-zinc-600">{host.groups.length ? host.groups.join(', ') : host.error || 'No groups returned.'}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <IdentityList
            items={[
              ...users.map((user) => `${user.username} | ${user.shell} | sudo ${user.sudo_enabled ? 'yes' : 'no'}`),
              ...discoveredUsers.slice(0, 12).map((user) => `${user.username} discovered on ${user.hosts.length} host(s) | ${user.shell ?? 'unknown shell'}`),
            ]}
            empty="No users yet."
            actions={discoveredUsers.slice(0, 8).map((user) => ({
              label: `Use ${user.username}`,
              onClick: () => loadDiscoveredUser(user),
            })).concat(discoveredUsers.slice(0, 8).map((user) => ({
              label: `Adopt ${user.username}`,
              onClick: () => void work(async () => {
                const response = await adoptLinuxUser({
                  username: user.username,
                  shell: user.shell ?? '/bin/bash',
                  home_directory: user.home_directory,
                  sudo_enabled: false,
                  sudo_nopasswd: false,
                  locked: false,
                  managed: false,
                  supplementary_groups: [],
                  target_server_ids: [],
                });
                setSelectedUserId(response.item.id);
                return null;
              }),
            })))}
          />
        </Panel>
      ) : null}

      {tab === 'groups' ? (
        <Panel icon={Users} title="Operational groups">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {groupPresets.map((preset) => (
                  <label key={preset.id} className="rounded-md border border-zinc-200 p-3 text-sm">
                    <div className="flex items-start gap-2">
                      <input
                        checked={selectedGroups.includes(preset.group)}
                        className="mt-1 h-4 w-4 rounded border-zinc-300"
                        type="checkbox"
                        onChange={(event) =>
                          setSelectedGroups((current) =>
                            event.target.checked ? [...current, preset.group] : current.filter((group) => group !== preset.group),
                          )
                        }
                      />
                      <span>
                        <span className="block font-semibold text-zinc-950">{preset.name}</span>
                        <span className="mt-1 block text-xs text-zinc-500">{preset.description}</span>
                      </span>
                    </div>
                  </label>
                ))}
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <label className="block lg:col-span-2">
                  <span className="text-sm font-medium text-zinc-950">Existing managed group</span>
                  <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={selectedGroup?.id ?? ''} onChange={(event) => {
                    const group = groups.find((candidate) => candidate.id === event.target.value);
                    if (group) loadGroup(group);
                  }}>
                    <option value="">Select group</option>
                    {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                  </select>
                </label>
                <TextInput label="Group name" value={groupName} onChange={setGroupName} />
                <TextInput label="Description" value={groupDescription} onChange={setGroupDescription} />
                <TextInput label="Members" value={memberNames} onChange={setMemberNames} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Action disabled={!targetsReady || isWorking} label="Create and replicate group" onClick={() => void work(async () => (await createLinuxGroup({ name: groupName, description: groupDescription || null, managed: true, target_server_ids: selectedTargetIds })).replication)} />
                <Action disabled={!selectedGroup || isWorking} label="Update selected group" onClick={() => void work(async () => (await updateLinuxGroup(selectedGroup!.id, { name: groupName, description: groupDescription || null, managed: true, target_server_ids: selectedTargetIds })).replication)} />
                <Action disabled={!selectedGroup || !targetsReady || isWorking} label="Replicate selected group" onClick={() => void work(() => replicateLinuxGroup(selectedGroup!.id, selectedTargetIds))} />
                <Action disabled={!selectedGroup || !targetsReady || isWorking} label="Add members" onClick={() => void work(() => addGroupMembers(selectedGroup!.id, splitCsv(memberNames), selectedTargetIds))} />
                <Action icon={Eye} disabled={!targetsReady || isWorking} label="Discover groups" onClick={() => void handleDiscoverGroups()} />
                <Action icon={Eye} disabled={!targetsReady || isWorking || !groupName.trim()} label="Inspect members" onClick={() => void handleInspectGroupMembers()} />
                <Action
                  icon={Trash2}
                  disabled={!selectedGroup || isWorking}
                  label="Delete selected group"
                  variant="danger"
                  onClick={() => {
                    if (!selectedGroup || !window.confirm(`Delete managed group ${selectedGroup.name}? Select targets first if you also want it removed from Linux hosts.`)) return;
                    void work(async () => {
                      await deleteLinuxGroup(selectedGroup.id, selectedTargetIds);
                      setSelectedGroupId('');
                      return null;
                    });
                  }}
                />
              </div>
            </div>
            <Preview commands={commandPreview.groups} title="Group operation preview" />
          </div>
          {groupMembership ? (
            <div className="mt-5 rounded-md border border-zinc-200 p-3">
              <h4 className="text-sm font-semibold text-zinc-950">Live members for {groupMembership.group}</h4>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                {groupMembership.hosts.map((host) => (
                  <div key={host.target_server_id} className="rounded-md bg-zinc-50 px-3 py-2 text-sm">
                    <p className="font-semibold text-zinc-950">{host.target_hostname ?? host.target_server_id}</p>
                    <p className="mt-1 text-zinc-700">{host.members.length ? host.members.join(', ') : host.error || 'No members returned.'}</p>
                    {host.primary_members.length || host.supplementary_members.length ? (
                      <p className="mt-1 text-xs text-zinc-500">
                        Primary: {host.primary_members.join(', ') || 'none'} | Supplementary: {host.supplementary_members.join(', ') || 'none'}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <IdentityList
            items={[
              ...groups.map((group) => `${group.name}${group.description ? ` | ${group.description}` : ''}`),
              ...discoveredGroups.slice(0, 12).map((group) => `${group.name} discovered on ${group.hosts.length} host(s)${group.members.length ? ` | members: ${group.members.join(', ')}` : ''}`),
            ]}
            empty="No groups yet."
            actions={discoveredGroups.slice(0, 8).map((group) => ({
              label: `Use ${group.name}`,
              onClick: () => loadDiscoveredGroup(group),
            })).concat(discoveredGroups.slice(0, 8).map((group) => ({
              label: `Adopt ${group.name}`,
              onClick: () => void work(async () => {
                const response = await adoptLinuxGroup({ name: group.name, description: `Discovered on ${group.hosts.join(', ')}`, managed: false, target_server_ids: [] });
                setSelectedGroupId(response.item.id);
                return null;
              }),
            })))}
          />
        </Panel>
      ) : null}

      {tab === 'ssh' ? (
        <Panel icon={KeyRound} title="SSH access">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div>
              <div className="grid gap-4 lg:grid-cols-2">
                <TextInput label="Key name" value={keyName} onChange={setKeyName} />
                <TextInput label="Target username" value={keyUsername} onChange={setKeyUsername} />
              </div>
              <label className="mt-4 block">
                <span className="text-sm font-medium text-zinc-950">Public key</span>
                <textarea className="mt-2 min-h-24 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm" value={publicKey} onChange={(event) => setPublicKey(event.target.value)} />
              </label>
              <div className="mt-4 flex flex-wrap gap-2">
                <Action disabled={!publicKey.trim() || isWorking} label="Save key" onClick={() => void work(async () => { await createSSHKey({ name: keyName, public_key: publicKey }); return null; })} />
                <Action disabled={!selectedKey || !targetsReady || isWorking} label="Deploy first key" onClick={() => void work(() => deploySSHKey(selectedKey!.id, keyUsername, selectedTargetIds))} />
                <Action disabled={!selectedKey || !targetsReady || isWorking} label="Revoke first key" onClick={() => void work(() => revokeSSHKey(selectedKey!.id, keyUsername, selectedTargetIds))} />
              </div>
            </div>
            <Preview commands={commandPreview.ssh} title="SSH operation preview" />
          </div>
          <IdentityList items={sshKeys.map((key) => key.name)} empty="No SSH keys yet." />
        </Panel>
      ) : null}

      {tab === 'permissions' ? (
        <Panel icon={Shield} title="Filesystem permissions">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-zinc-950">Permission preset</span>
                <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={permissionPresetId} onChange={(event) => applyPermissionPreset(event.target.value)}>
                  {permissionPresets.map((preset) => (
                    <option key={preset.id} value={preset.id}>{preset.name}</option>
                  ))}
                </select>
                <p className="mt-2 text-sm text-zinc-500">{permissionPresets.find((preset) => preset.id === permissionPresetId)?.description}</p>
              </label>
              <div className="grid gap-4 lg:grid-cols-3">
                <TextInput label="Path" value={path} onChange={setPath} />
                <TextInput label="Owner" value={owner} onChange={setOwner} />
                <TextInput label="Group" value={permissionGroup} onChange={setPermissionGroup} />
              </div>
              <PermissionMatrix matrix={matrix} onToggle={togglePermission} />
              <div className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700">Generated chmod: <span className="font-mono font-semibold">{mode}</span></div>
              {advanced ? (
                <div className="grid gap-4 rounded-md border border-zinc-200 bg-zinc-50 p-4 lg:grid-cols-2">
                  <TextInput label="Raw octal mode" value={mode} onChange={(value) => { setMode(value); setMatrix(modeToMatrix(value)); }} />
                  <Toggle label="Recursive" checked={recursive} onChange={setRecursive} />
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-3">
                <button className="text-sm font-semibold text-zinc-700 underline" type="button" onClick={() => setAdvanced((current) => !current)}>
                  {advanced ? 'Hide advanced permission options' : 'Show advanced permission options'}
                </button>
                <Action disabled={!targetsReady || isWorking} label="Apply permissions" onClick={() => void work(() => applyPermission({ path, owner, group: permissionGroup, mode, recursive, target_server_ids: selectedTargetIds }))} />
              </div>
            </div>
            <Preview commands={commandPreview.permissions} title="Permission command preview" />
          </div>
          <IdentityList items={permissions.map((permission) => `${permission.path} ${permission.owner ?? ''}:${permission.group ?? ''} ${permission.mode ?? ''}`)} empty="No saved permission templates yet." />
        </Panel>
      ) : null}

      {result ? <ExecutionResult result={result} /> : null}
    </div>
  );
}

function Panel({ icon: Icon, title, children }: { icon: typeof Users; title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
        <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-950">{label}</span>
      <input className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 self-end text-sm font-medium text-zinc-950">
      <input checked={checked} className="h-4 w-4 rounded border-zinc-300" type="checkbox" onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function PermissionMatrix({
  matrix,
  onToggle,
}: {
  matrix: Record<PermissionScope, Record<PermissionBit, boolean>>;
  onToggle: (scope: PermissionScope, bit: PermissionBit) => void;
}) {
  const scopes: Array<[PermissionScope, string]> = [['owner', 'Owner'], ['group', 'Group'], ['other', 'Others']];
  const bits: Array<[PermissionBit, string]> = [['read', 'Read'], ['write', 'Write'], ['execute', 'Execute']];
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200">
      <div className="grid grid-cols-4 bg-zinc-50 text-xs font-semibold uppercase text-zinc-500">
        <div className="px-3 py-2">Scope</div>
        {bits.map(([, label]) => <div key={label} className="px-3 py-2">{label}</div>)}
      </div>
      {scopes.map(([scope, label]) => (
        <div key={scope} className="grid grid-cols-4 border-t border-zinc-100 text-sm">
          <div className="px-3 py-2 font-medium text-zinc-950">{label}</div>
          {bits.map(([bit]) => (
            <label key={bit} className="px-3 py-2">
              <input checked={matrix[scope][bit]} className="h-4 w-4 rounded border-zinc-300" type="checkbox" onChange={() => onToggle(scope, bit)} />
            </label>
          ))}
        </div>
      ))}
    </div>
  );
}

function Action({
  icon: Icon = Play,
  label,
  disabled,
  onClick,
  variant = 'primary',
}: {
  icon?: typeof Play;
  label: string;
  disabled: boolean;
  onClick: () => void;
  variant?: 'primary' | 'danger';
}) {
  const className = variant === 'danger'
    ? 'inline-flex h-10 items-center gap-2 rounded-md border border-rose-300 px-3 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-400'
    : 'inline-flex h-10 items-center gap-2 rounded-md bg-cyan-400 px-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400';
  return (
    <button className={className} disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}

function Preview({ commands, title }: { commands: string[]; title: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-950 p-4 text-zinc-50">
      <h4 className="text-sm font-semibold">{title}</h4>
      <pre className="mt-3 whitespace-pre-wrap text-xs leading-5">{commands.join('\n') || 'No operations selected.'}</pre>
    </div>
  );
}

function IdentityList({ items, empty, actions = [] }: { items: string[]; empty: string; actions?: Array<{ label: string; onClick: () => void }> }) {
  return (
    <div className="mt-5 rounded-md border border-zinc-200">
      <div className="divide-y divide-zinc-100">
        {items.length ? items.map((item) => <p key={item} className="px-3 py-2 text-sm text-zinc-700">{item}</p>) : <p className="px-3 py-2 text-sm text-zinc-500">{empty}</p>}
      </div>
      {actions.length ? (
        <div className="flex flex-wrap gap-2 border-t border-zinc-200 p-3">
          {actions.map((action) => (
            <button key={action.label} className="rounded-md border border-zinc-300 px-2 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={action.onClick}>
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ExecutionResult({ result }: { result: BulkExecutionResponse }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Replication result</h3>
      <p className="mt-1 text-sm text-zinc-500">{result.success_count} succeeded, {result.failure_count} failed</p>
      <div className="mt-4 divide-y divide-zinc-100 rounded-md border border-zinc-200">
        {result.results.map((row) => (
          <div key={row.target_server_id} className="px-3 py-2 text-sm">
            <span className={row.success ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'}>{row.success ? 'Success' : 'Failed'}</span>
            <span className="ml-2 text-zinc-700">{row.target_hostname ?? row.target_server_id}</span>
            {row.error ? <p className="mt-1 font-mono text-xs text-zinc-500">{row.error}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function buildCommandPreview(input: {
  username: string;
  shell: string;
  sudoMode: string;
  groups: string[];
  path: string;
  owner: string;
  permissionGroup: string;
  mode: string;
  recursive: boolean;
}) {
  const adminGroup = input.groups.includes('__admin__') ? ['admin_group=$(debian/ubuntu ? sudo : wheel)', `usermod -aG "$admin_group" ${input.username}`] : [];
  const normalGroups = input.groups.filter((group) => group !== '__admin__').map((group) => `usermod -aG ${group} ${input.username}`);
  const sudo = input.sudoMode === 'nopasswd'
    ? [`write /etc/sudoers.d/nexusops-${input.username}: ${input.username} ALL=(ALL) NOPASSWD:ALL`, 'visudo -cf snippet']
    : input.sudoMode === 'password'
      ? [`write /etc/sudoers.d/nexusops-${input.username}: ${input.username} ALL=(ALL) ALL`, 'visudo -cf snippet']
      : [];
  const recursive = input.recursive ? '-R ' : '';
  return {
    access: [`useradd -m -d /home/${input.username} -s ${input.shell} ${input.username}`, ...adminGroup, ...normalGroups, ...sudo],
    groups: [...adminGroup, ...normalGroups],
    ssh: [`install -d -m 700 /home/${input.username}/.ssh`, 'append public key if missing', 'chmod 600 authorized_keys'],
    permissions: [`chown ${recursive}${input.owner}:${input.permissionGroup} ${input.path}`, `chmod ${recursive}${input.mode} ${input.path}`],
  };
}

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function matrixToMode(matrix: Record<PermissionScope, Record<PermissionBit, boolean>>): string {
  const scopes: PermissionScope[] = ['owner', 'group', 'other'];
  return `0${scopes.map((scope) => (
    (matrix[scope].read ? 4 : 0) + (matrix[scope].write ? 2 : 0) + (matrix[scope].execute ? 1 : 0)
  )).join('')}`;
}

function modeToMatrix(mode: string): Record<PermissionScope, Record<PermissionBit, boolean>> {
  const digits = mode.padStart(4, '0').slice(-3).split('').map((digit) => Number(digit));
  const scopes: PermissionScope[] = ['owner', 'group', 'other'];
  return scopes.reduce(
    (next, scope, index) => ({
      ...next,
      [scope]: {
        read: Boolean(digits[index] & 4),
        write: Boolean(digits[index] & 2),
        execute: Boolean(digits[index] & 1),
      },
    }),
    {} as Record<PermissionScope, Record<PermissionBit, boolean>>,
  );
}
