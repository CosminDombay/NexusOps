import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Eye, KeyRound, Lock, Play, Search, Shield, Unlock, Users } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import type { BulkExecutionResponse } from '../jobs/types/job';
import {
  addGroupMembers,
  applyPermission,
  createLinuxGroup,
  createLinuxUser,
  createSSHKey,
  deploySSHKey,
  discoverGroups,
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
} from './api/identityApi';
import type {
  AccessProfile,
  DiscoveredGroup,
  GroupPreset,
  LinuxGroup,
  LinuxUser,
  PermissionPreset,
  PermissionTemplate,
  SSHKey,
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
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [targetSearch, setTargetSearch] = useState('');
  const [users, setUsers] = useState<LinuxUser[]>([]);
  const [groups, setGroups] = useState<LinuxGroup[]>([]);
  const [sshKeys, setSshKeys] = useState<SSHKey[]>([]);
  const [permissions, setPermissions] = useState<PermissionTemplate[]>([]);
  const [accessProfiles, setAccessProfiles] = useState<AccessProfile[]>([]);
  const [groupPresets, setGroupPresets] = useState<GroupPreset[]>([]);
  const [permissionPresets, setPermissionPresets] = useState<PermissionPreset[]>([]);
  const [discoveredGroups, setDiscoveredGroups] = useState<DiscoveredGroup[]>([]);
  const [result, setResult] = useState<BulkExecutionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [advanced, setAdvanced] = useState(false);

  const [profileId, setProfileId] = useState('deployment-operator');
  const [username, setUsername] = useState('deploy');
  const [shellPreset, setShellPreset] = useState('standard');
  const [customShell, setCustomShell] = useState('/bin/bash');
  const [sudoMode, setSudoMode] = useState('password');
  const [selectedGroups, setSelectedGroups] = useState<string[]>(['docker', 'www-data']);
  const [groupName, setGroupName] = useState('deploy');
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
  const selectedUser = users[0] ?? null;
  const selectedGroup = groups[0] ?? null;
  const selectedKey = sshKeys[0] ?? null;
  const selectedTargets = servers.filter((server) => selectedTargetIds.includes(server.id));
  const filteredServers = servers.filter((server) =>
    `${server.hostname} ${server.ip_address} ${server.environment}`.toLowerCase().includes(targetSearch.toLowerCase()),
  );
  const shell = shellPreset === 'custom' ? customShell : shellOptions.find((option) => option.id === shellPreset)?.value ?? '/bin/bash';
  const sudo = sudoOptions.find((option) => option.id === sudoMode) ?? sudoOptions[0];

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
        nextUsers,
        nextGroups,
        nextKeys,
        nextPermissions,
        nextProfiles,
        nextGroupPresets,
        nextPermissionPresets,
      ] = await Promise.all([
        listServers(),
        listLinuxUsers(),
        listLinuxGroups(),
        listSSHKeys(),
        listPermissionTemplates(),
        listAccessProfiles(),
        listGroupPresets(),
        listPermissionPresets(),
      ]);
      setServers(nextServers);
      setUsers(nextUsers);
      setGroups(nextGroups);
      setSshKeys(nextKeys);
      setPermissions(nextPermissions);
      setAccessProfiles(nextProfiles);
      setGroupPresets(nextGroupPresets);
      setPermissionPresets(nextPermissionPresets);
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

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Replication targets</h3>
            <p className="mt-1 text-sm text-zinc-500">Select managed inventory hosts for identity propagation.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTargets.length ? (
                selectedTargets.map((server) => (
                  <span key={server.id} className="rounded-full bg-zinc-950 px-2.5 py-1 text-xs font-semibold text-white">
                    {server.hostname}
                  </span>
                ))
              ) : (
                <span className="text-sm text-zinc-500">No targets selected</span>
              )}
            </div>
          </div>
          <div className="w-full xl:max-w-3xl">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-zinc-400" aria-hidden="true" />
                <input
                  className="h-10 w-full rounded-md border border-zinc-300 pl-9 pr-3 text-sm"
                  placeholder="Search hosts"
                  value={targetSearch}
                  onChange={(event) => setTargetSearch(event.target.value)}
                />
              </div>
              <button className="rounded-md border border-zinc-300 px-3 text-sm font-semibold" type="button" onClick={() => setSelectedTargetIds(filteredServers.map((server) => server.id))}>
                Select all
              </button>
              <button className="rounded-md border border-zinc-300 px-3 text-sm font-semibold" type="button" onClick={() => setSelectedTargetIds([])}>
                Clear
              </button>
            </div>
            <div className="mt-3 grid max-h-52 gap-2 overflow-auto sm:grid-cols-2 xl:grid-cols-3">
              {filteredServers.map((server) => (
                <label key={server.id} className="flex min-h-12 items-center gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm">
                  <input
                    checked={selectedTargetIds.includes(server.id)}
                    className="h-4 w-4 rounded border-zinc-300"
                    type="checkbox"
                    onChange={(event) =>
                      setSelectedTargetIds((current) =>
                        event.target.checked ? [...current, server.id] : current.filter((serverId) => serverId !== server.id),
                      )
                    }
                  />
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-zinc-950">{server.hostname}</span>
                    <span className="block truncate font-mono text-xs text-zinc-500">{server.ip_address} | {server.environment}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        {[
          ['access', 'Access'],
          ['groups', 'Groups'],
          ['ssh', 'SSH Keys'],
          ['permissions', 'Permissions'],
        ].map(([value, label]) => (
          <button
            key={value}
            className={`rounded-md px-3 py-2 text-sm font-semibold ${tab === value ? 'bg-zinc-950 text-white' : 'border border-zinc-300 bg-white text-zinc-700'}`}
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
                <TextInput label="Username" value={username} onChange={setUsername} />
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
                <Action disabled={!selectedUser || !targetsReady || isWorking} label="Replicate first user" onClick={() => void work(() => replicateLinuxUser(selectedUser!.id, selectedTargetIds))} />
                <Action icon={Lock} disabled={!selectedUser || !targetsReady || isWorking} label="Lock" onClick={() => void work(() => lockLinuxUser(selectedUser!.id, selectedTargetIds))} />
                <Action icon={Unlock} disabled={!selectedUser || !targetsReady || isWorking} label="Unlock" onClick={() => void work(() => unlockLinuxUser(selectedUser!.id, selectedTargetIds))} />
              </div>
            </div>
            <Preview commands={commandPreview.access} title="Generated access operations" />
          </div>
          <IdentityList items={users.map((user) => `${user.username} | ${user.shell} | sudo ${user.sudo_enabled ? 'yes' : 'no'}`)} empty="No users yet." />
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
                <TextInput label="Create group" value={groupName} onChange={setGroupName} />
                <TextInput label="Members" value={memberNames} onChange={setMemberNames} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Action disabled={!targetsReady || isWorking} label="Create and replicate group" onClick={() => void work(async () => (await createLinuxGroup({ name: groupName, managed: true, target_server_ids: selectedTargetIds })).replication)} />
                <Action disabled={!selectedGroup || !targetsReady || isWorking} label="Replicate first group" onClick={() => void work(() => replicateLinuxGroup(selectedGroup!.id, selectedTargetIds))} />
                <Action disabled={!selectedGroup || !targetsReady || isWorking} label="Add members" onClick={() => void work(() => addGroupMembers(selectedGroup!.id, splitCsv(memberNames), selectedTargetIds))} />
                <Action icon={Eye} disabled={!targetsReady || isWorking} label="Discover groups" onClick={() => void handleDiscoverGroups()} />
              </div>
            </div>
            <Preview commands={commandPreview.groups} title="Group operation preview" />
          </div>
          <IdentityList items={[...groups.map((group) => group.name), ...discoveredGroups.slice(0, 12).map((group) => `${group.name} discovered on ${group.hosts.length} host(s)`)]} empty="No groups yet." />
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
              <button className="text-sm font-semibold text-zinc-700 underline" type="button" onClick={() => setAdvanced((current) => !current)}>
                {advanced ? 'Hide advanced permission options' : 'Show advanced permission options'}
              </button>
              <Action disabled={!targetsReady || isWorking} label="Apply permissions" onClick={() => void work(() => applyPermission({ path, owner, group: permissionGroup, mode, recursive, target_server_ids: selectedTargetIds }))} />
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

function Action({ icon: Icon = Play, label, disabled, onClick }: { icon?: typeof Play; label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button className="inline-flex h-10 items-center gap-2 rounded-md bg-zinc-950 px-3 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={disabled} type="button" onClick={onClick}>
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

function IdentityList({ items, empty }: { items: string[]; empty: string }) {
  return (
    <div className="mt-5 divide-y divide-zinc-100 rounded-md border border-zinc-200">
      {items.length ? items.map((item) => <p key={item} className="px-3 py-2 text-sm text-zinc-700">{item}</p>) : <p className="px-3 py-2 text-sm text-zinc-500">{empty}</p>}
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
