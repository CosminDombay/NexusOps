import { KeyRound, Search, Shield, Users } from 'lucide-react';

import type { IdentityEntity } from '../../utils/entityModel';
import { PermissionChip, StatusBadge } from '../common/IdentityPrimitives';

const kindLabels: Record<IdentityEntity['kind'], string> = {
  user: 'User',
  group: 'Group',
  'discovered-user': 'User',
  'discovered-group': 'Group',
  'ssh-key': 'SSH key',
  permission: 'Permission',
};

export function IdentityExplorer({
  entities,
  selectedEntityId,
  search,
  onSearchChange,
  onSelect,
}: {
  entities: IdentityEntity[];
  selectedEntityId: string | null;
  search: string;
  onSearchChange: (value: string) => void;
  onSelect: (entity: IdentityEntity) => void;
}) {
  const normalized = search.trim().toLowerCase();
  const filtered = entities.filter((entity) => entity.name.toLowerCase().includes(normalized) || entity.kind.includes(normalized));
  const grouped = {
    Groups: filtered.filter((entity) => entity.kind === 'group' || entity.kind === 'discovered-group'),
    Users: filtered.filter((entity) => entity.kind === 'user' || entity.kind === 'discovered-user'),
    Access: filtered.filter((entity) => entity.kind === 'ssh-key' || entity.kind === 'permission'),
  };

  return (
    <aside className="flex min-h-[720px] flex-col rounded-md border border-slate-700 bg-slate-900/80">
      <div className="border-b border-slate-700 p-4">
        <p className="text-sm font-semibold text-white">Identity Explorer</p>
        <p className="mt-1 text-xs text-slate-400">Managed and discovered Linux identity objects.</p>
        <div className="relative mt-3">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" aria-hidden="true" />
          <input
            className="h-10 w-full rounded-md border border-slate-700 bg-slate-950 pl-9 pr-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300"
            placeholder="Search users, groups, keys..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-auto p-3">
        {Object.entries(grouped).map(([label, items]) => (
          <details key={label} className="group" open={label !== 'Groups'}>
            <summary className="mb-2 flex cursor-pointer list-none items-center justify-between rounded-md px-1 py-1 hover:bg-slate-800/70">
              <h3 className="text-xs font-semibold uppercase text-slate-400">{label}</h3>
              <span className="text-xs text-slate-500">{items.length}</span>
            </summary>
            <div className="space-y-2">
              {items.map((entity) => (
                <EntityCard
                  key={entity.id}
                  entity={entity}
                  selected={entity.id === selectedEntityId}
                  onClick={() => onSelect(entity)}
                />
              ))}
              {!items.length ? <p className="rounded-md border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-500">No {label.toLowerCase()} found.</p> : null}
            </div>
          </details>
        ))}
      </div>
    </aside>
  );
}

function EntityCard({ entity, selected, onClick }: { entity: IdentityEntity; selected: boolean; onClick: () => void }) {
  const Icon = entity.kind.includes('user') || entity.kind.includes('group') ? Users : entity.kind === 'ssh-key' ? KeyRound : Shield;
  const permissions = permissionBadgesFor(entity);
  const memberCount = 'memberCount' in entity ? entity.memberCount : entity.kind === 'discovered-user' ? entity.user.hosts.length : undefined;
  return (
    <button
      className={`w-full rounded-md border p-3 text-left transition ${selected ? 'border-cyan-300 bg-cyan-400/10' : 'border-slate-700 bg-slate-950/40 hover:border-slate-500 hover:bg-slate-900'}`}
      type="button"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="truncate text-sm font-semibold text-white">{entity.name}</span>
          </div>
          <p className="mt-1 text-xs text-slate-400">{kindLabels[entity.kind]}</p>
        </div>
        <StatusBadge state={entity.state} />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {typeof memberCount === 'number' ? <PermissionChip label={`${memberCount} ${entity.kind.includes('user') ? 'host' : 'members'}`} /> : null}
        {permissions.map((permission) => (
          <PermissionChip key={permission.label} label={permission.label} tone={permission.tone} />
        ))}
      </div>
    </button>
  );
}

function permissionBadgesFor(entity: IdentityEntity): Array<{ label: string; tone: 'neutral' | 'privileged' | 'runtime' | 'observe' }> {
  const name = entity.name.toLowerCase();
  const badges: Array<{ label: string; tone: 'neutral' | 'privileged' | 'runtime' | 'observe' }> = [];
  if (name.includes('sudo') || name.includes('wheel') || (entity.kind === 'user' && entity.user.sudo_enabled)) badges.push({ label: 'sudo', tone: 'privileged' });
  if (name.includes('docker')) badges.push({ label: 'docker', tone: 'runtime' });
  if (name.includes('www') || name.includes('web')) badges.push({ label: 'web-runtime', tone: 'runtime' });
  if (name.includes('journal') || name === 'adm') badges.push({ label: 'monitoring', tone: 'observe' });
  if (name.includes('libvirt') || name.includes('virt')) badges.push({ label: 'virtualization', tone: 'runtime' });
  if (entity.kind === 'user' && entity.user.locked) badges.push({ label: 'locked', tone: 'privileged' });
  return badges.slice(0, 3);
}
