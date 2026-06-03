import { Eye, KeyRound, Lock, Play, RefreshCw, RotateCcw, Save, ShieldOff, Trash2, Unlock, UserPlus, Users } from 'lucide-react';

import type { Credential } from '../../../credentials/types/credential';
import type { AccessProfile, GroupPreset, LinuxGroup, LinuxUser, PermissionPreset } from '../../types/identity';
import { IconButton, SectionCard, SelectInput, TextInput } from '../common/IdentityPrimitives';

export type IdentityActionMode = 'user' | 'group' | 'ssh-key' | 'permission';

export type IdentityActionForm = {
  username: string;
  shell: string;
  passwordCredentialId: string;
  sudoMode: string;
  groups: string;
  groupName: string;
  groupDescription: string;
  memberNames: string;
  keyName: string;
  publicKey: string;
  keyUsername: string;
  permissionPath: string;
  permissionOwner: string;
  permissionGroup: string;
  permissionMode: string;
  permissionRecursive: boolean;
};

export function IdentityActionsDrawer({
  selectedKind,
  actionMode,
  form,
  users,
  groups,
  accessProfiles,
  groupPresets,
  permissionPresets,
  credentials,
  hasSelectedSshKey,
  targetsReady,
  isWorking,
  commandPreview,
  onFormChange,
  onActionModeChange,
  onCreateUser,
  onUpdateUser,
  onReplicateUser,
  onLockUser,
  onUnlockUser,
  onDisableShell,
  onExpirePassword,
  onInspectUserGroups,
  onDeleteUser,
  onCreateGroup,
  onUpdateGroup,
  onReplicateGroup,
  onAddMembers,
  onRemoveMembers,
  onInspectGroupMembers,
  onDeleteGroup,
  onDiscoverUsers,
  onDiscoverGroups,
  onSaveKey,
  onDeployKey,
  onRevokeKey,
  onApplyPermission,
}: {
  selectedKind: string | null;
  actionMode: IdentityActionMode;
  form: IdentityActionForm;
  users: LinuxUser[];
  groups: LinuxGroup[];
  accessProfiles: AccessProfile[];
  groupPresets: GroupPreset[];
  permissionPresets: PermissionPreset[];
  credentials: Credential[];
  hasSelectedSshKey: boolean;
  targetsReady: boolean;
  isWorking: boolean;
  commandPreview: string[];
  onFormChange: (patch: Partial<IdentityActionForm>) => void;
  onActionModeChange: (mode: IdentityActionMode) => void;
  onCreateUser: () => void;
  onUpdateUser: () => void;
  onReplicateUser: () => void;
  onLockUser: () => void;
  onUnlockUser: () => void;
  onDisableShell: () => void;
  onExpirePassword: () => void;
  onInspectUserGroups: () => void;
  onDeleteUser: () => void;
  onCreateGroup: () => void;
  onUpdateGroup: () => void;
  onReplicateGroup: () => void;
  onAddMembers: () => void;
  onRemoveMembers: () => void;
  onInspectGroupMembers: () => void;
  onDeleteGroup: () => void;
  onDiscoverUsers: () => void;
  onDiscoverGroups: () => void;
  onSaveKey: () => void;
  onDeployKey: () => void;
  onRevokeKey: () => void;
  onApplyPermission: () => void;
}) {
  const passwordCredentials = credentials.filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password');
  const userSelected = actionMode === 'user';
  const groupSelected = actionMode === 'group';
  const sshSelected = actionMode === 'ssh-key';
  const permissionSelected = actionMode === 'permission';
  const discoveredUserSelected = selectedKind === 'discovered-user' && actionMode === 'user';
  const discoveredGroupSelected = selectedKind === 'discovered-group' && actionMode === 'group';
  const targetHint = targetsReady
    ? 'Selected targets will receive remote operations.'
    : 'No targets selected. Create/adopt saves a managed record; sync and discovery need target selection.';
  const modes: Array<{ id: IdentityActionMode; label: string }> = [
    { id: 'user', label: 'User' },
    { id: 'group', label: 'Group' },
    { id: 'ssh-key', label: 'SSH key' },
    { id: 'permission', label: 'Permission' },
  ];

  return (
    <aside className="space-y-4 rounded-md border border-slate-700 bg-slate-900/80 p-4">
      <div>
        <p className="text-sm font-semibold text-white">Context Actions</p>
        <p className="mt-1 text-xs text-slate-400">Actions use selected replication targets and existing Identity APIs.</p>
        <p className="mt-2 rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">{targetHint}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 rounded-md border border-slate-700 bg-slate-950/50 p-2">
        {modes.map((mode) => (
          <button
            key={mode.id}
            className={`h-9 rounded-md border text-xs font-semibold transition ${actionMode === mode.id ? 'border-cyan-300 bg-cyan-400 text-slate-950' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500 hover:text-white'}`}
            type="button"
            onClick={() => onActionModeChange(mode.id)}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {userSelected ? (
        <SectionCard title="User Administration">
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
            <SelectInput label="Password / sudo credential" value={form.passwordCredentialId} onChange={(value) => onFormChange({ passwordCredentialId: value })}>
              <option value="">Use target saved credential</option>
              {passwordCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
            </SelectInput>
            <p className="-mt-1 text-xs text-slate-400">
              Sync and Modify use this for sudo execution. Set selected password uses it as the account password.
            </p>
            <TextInput label="Groups" value={form.groups} onChange={(value) => onFormChange({ groups: value })} placeholder="docker,www-data" />
            <div className="grid gap-2">
              <IconButton icon={UserPlus} disabled={isWorking} label={discoveredUserSelected ? (targetsReady ? 'Adopt & sync' : 'Adopt') : 'Create'} onClick={onCreateUser} />
              <IconButton icon={Save} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Modify" onClick={onUpdateUser} />
              <IconButton icon={RotateCcw} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking || !form.passwordCredentialId} label="Set selected password" onClick={onUpdateUser} />
              <IconButton icon={RefreshCw} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Sync now" onClick={onReplicateUser} />
              <div className="grid grid-cols-2 gap-2">
                <IconButton icon={Lock} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Lock" onClick={onLockUser} variant="secondary" />
                <IconButton icon={Unlock} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Unlock" onClick={onUnlockUser} variant="secondary" />
              </div>
              <IconButton icon={ShieldOff} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Disable shell" onClick={onDisableShell} variant="secondary" />
              <IconButton icon={RotateCcw} disabled={discoveredUserSelected || !users.length || !targetsReady || isWorking} label="Expire password" onClick={onExpirePassword} variant="secondary" />
              <IconButton icon={Eye} disabled={!targetsReady || isWorking || !form.username.trim()} label="Inspect groups" onClick={onInspectUserGroups} variant="secondary" />
              <IconButton icon={Trash2} disabled={discoveredUserSelected || !users.length || isWorking} label="Delete" onClick={onDeleteUser} variant="danger" />
            </div>
          </div>
        </SectionCard>
      ) : null}

      {groupSelected ? (
        <SectionCard title="Group Administration">
          <div className="space-y-3">
            <TextInput label="Group name" value={form.groupName} onChange={(value) => onFormChange({ groupName: value })} />
            <TextInput label="Description" value={form.groupDescription} onChange={(value) => onFormChange({ groupDescription: value })} />
            <TextInput label="Members" value={form.memberNames} onChange={(value) => onFormChange({ memberNames: value })} placeholder="deploy,cerberus" />
            <div className="grid gap-2">
              <IconButton icon={Users} disabled={isWorking} label={discoveredGroupSelected ? (targetsReady ? 'Adopt & sync' : 'Adopt') : 'Create'} onClick={onCreateGroup} />
              <IconButton icon={Save} disabled={discoveredGroupSelected || !groups.length || isWorking} label="Update" onClick={onUpdateGroup} />
              <IconButton icon={RefreshCw} disabled={discoveredGroupSelected || !groups.length || !targetsReady || isWorking} label="Replicate" onClick={onReplicateGroup} />
              <IconButton icon={UserPlus} disabled={discoveredGroupSelected || !groups.length || !targetsReady || isWorking} label="Add members" onClick={onAddMembers} />
              <IconButton icon={Trash2} disabled={discoveredGroupSelected || !groups.length || !targetsReady || isWorking} label="Remove members" onClick={onRemoveMembers} variant="secondary" />
              <IconButton icon={Eye} disabled={!targetsReady || isWorking || !form.groupName.trim()} label="Inspect members" onClick={onInspectGroupMembers} variant="secondary" />
              <IconButton icon={Trash2} disabled={discoveredGroupSelected || !groups.length || isWorking} label="Delete" onClick={onDeleteGroup} variant="danger" />
            </div>
          </div>
        </SectionCard>
      ) : null}

      {sshSelected ? (
        <SectionCard title="SSH Keys">
          <div className="space-y-3">
            <TextInput label="Key name" value={form.keyName} onChange={(value) => onFormChange({ keyName: value })} />
            <TextInput label="Target username" value={form.keyUsername} onChange={(value) => onFormChange({ keyUsername: value })} />
            <label className="block">
              <span className="text-xs font-semibold uppercase text-slate-400">Public key</span>
              <textarea className="mt-2 min-h-28 w-full rounded-md border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-white outline-none focus:border-cyan-300" value={form.publicKey} onChange={(event) => onFormChange({ publicKey: event.target.value })} />
            </label>
            <IconButton icon={KeyRound} disabled={!form.publicKey.trim() || isWorking} label="Save key" onClick={onSaveKey} />
            <IconButton icon={Play} disabled={!hasSelectedSshKey || !targetsReady || isWorking} label="Deploy selected key" onClick={onDeployKey} variant="secondary" />
            <IconButton icon={Trash2} disabled={!hasSelectedSshKey || !targetsReady || isWorking} label="Revoke selected key" onClick={onRevokeKey} variant="danger" />
          </div>
        </SectionCard>
      ) : null}

      {permissionSelected ? (
        <SectionCard title="Permissions">
          <div className="space-y-3">
            <SelectInput label="Preset" value={form.permissionMode} onChange={(value) => onFormChange({ permissionMode: value })}>
              {permissionPresets.map((preset) => <option key={preset.id} value={preset.mode}>{preset.name} ({preset.mode})</option>)}
            </SelectInput>
            <TextInput label="Path" value={form.permissionPath} onChange={(value) => onFormChange({ permissionPath: value })} />
            <TextInput label="Owner" value={form.permissionOwner} onChange={(value) => onFormChange({ permissionOwner: value })} />
            <TextInput label="Group" value={form.permissionGroup} onChange={(value) => onFormChange({ permissionGroup: value })} />
            <TextInput label="Mode" value={form.permissionMode} onChange={(value) => onFormChange({ permissionMode: value })} />
            <label className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <input checked={form.permissionRecursive} className="h-4 w-4 rounded border-slate-700" type="checkbox" onChange={(event) => onFormChange({ permissionRecursive: event.target.checked })} />
              Recursive
            </label>
            <IconButton icon={Play} disabled={!targetsReady || isWorking} label="Apply permissions" onClick={onApplyPermission} />
          </div>
        </SectionCard>
      ) : null}

      <SectionCard title="Discovery">
        <div className="grid gap-2">
          <IconButton icon={Eye} disabled={!targetsReady || isWorking} label="Discover users" onClick={onDiscoverUsers} variant="secondary" />
          <IconButton icon={Eye} disabled={!targetsReady || isWorking} label="Discover groups" onClick={onDiscoverGroups} variant="secondary" />
        </div>
      </SectionCard>

      <details className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-white">Operation preview</summary>
        <pre className="mt-3 whitespace-pre-wrap text-xs leading-5 text-slate-300">{commandPreview.join('\n') || 'No operations selected.'}</pre>
      </details>

      <details className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-white">Presets</summary>
        <div className="mt-3 space-y-3">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Access</p>
            <p className="mt-1 text-xs text-slate-400">{accessProfiles.map((profile) => profile.name).join(', ') || 'No access profiles loaded.'}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Groups</p>
            <p className="mt-1 text-xs text-slate-400">{groupPresets.map((preset) => preset.group).join(', ') || 'No group presets loaded.'}</p>
          </div>
        </div>
      </details>
    </aside>
  );
}
