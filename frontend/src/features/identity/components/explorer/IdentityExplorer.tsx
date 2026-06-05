import { ChevronDown, FileKey2, FolderTree, KeyRound, Search, ShieldCheck, UserRound, UsersRound } from 'lucide-react';

import type { IdentityEntity } from '../../utils/entityModel';
import { PermissionChip, StatusBadge } from '../common/IdentityPrimitives';

const sectionConfig: Record<string, { icon: typeof UserRound; kinds: IdentityEntity['kind'][] }> = {
  Users: { icon: UserRound, kinds: ['user', 'discovered-user'] },
  Groups: { icon: UsersRound, kinds: ['group', 'discovered-group'] },
  'SSH Keys': { icon: KeyRound, kinds: ['ssh-key'] },
  Permissions: { icon: ShieldCheck, kinds: ['permission'] },
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
  const filtered = entities.filter((entity) => {
    const origin = hostSummary(entity).toLowerCase();
    return entity.name.toLowerCase().includes(normalized) || entity.kind.includes(normalized) || origin.includes(normalized);
  });

  return (
    <aside className="flex min-h-[760px] flex-col rounded-md border border-slate-700 bg-slate-900/85">
      <div className="border-b border-slate-700 p-4">
        <div className="flex items-center gap-2">
          <FolderTree className="h-4 w-4 text-cyan-200" aria-hidden="true" />
          <p className="text-sm font-semibold text-white">Identity Explorer</p>
        </div>
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
      <div className="min-h-0 flex-1 overflow-auto p-3">
        {Object.entries(sectionConfig).map(([label, config]) => {
          const items = filtered.filter((entity) => config.kinds.includes(entity.kind));
          const Icon = config.icon;
          return (
            <details key={label} className="group mb-3" open>
              <summary className="flex cursor-pointer list-none items-center justify-between rounded-md px-2 py-2 hover:bg-slate-800/80">
                <span className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-300">
                  <ChevronDown className="h-3.5 w-3.5 transition group-open:rotate-0" aria-hidden="true" />
                  <Icon className="h-4 w-4 text-slate-500" aria-hidden="true" />
                  {label}
                </span>
                <span className="text-xs text-slate-500">{items.length}</span>
              </summary>
              <div className="mt-1 space-y-1.5">
                {items.map((entity) => (
                  <TreeItem
                    key={entity.id}
                    entity={entity}
                    selected={entity.id === selectedEntityId}
                    onClick={() => onSelect(entity)}
                  />
                ))}
                {!items.length ? <p className="rounded-md border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-500">No {label.toLowerCase()} found.</p> : null}
              </div>
            </details>
          );
        })}
      </div>
    </aside>
  );
}

function TreeItem({ entity, selected, onClick }: { entity: IdentityEntity; selected: boolean; onClick: () => void }) {
  const Icon = iconFor(entity.kind);
  const status = simplifiedStatus(entity);
  const origin = hostSummary(entity);
  return (
    <button
      className={`w-full rounded-md border px-3 py-2 text-left transition ${selected ? 'border-cyan-300 bg-cyan-400/10' : 'border-transparent bg-transparent hover:border-slate-700 hover:bg-slate-950/50'}`}
      type="button"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">{entity.name}</p>
            {origin ? <p className="mt-1 truncate text-xs text-slate-400">{origin}</p> : null}
          </div>
        </div>
        <StatusBadge state={status.state} label={status.label} />
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {entity.kind === 'group' || entity.kind === 'discovered-group' ? <PermissionChip label={`${entity.memberCount} members`} /> : null}
        {entity.kind === 'user' && entity.user.sudo_enabled ? <PermissionChip label="sudo" tone="privileged" /> : null}
        {entity.kind === 'discovered-user' ? <PermissionChip label="importable" tone="observe" /> : null}
      </div>
    </button>
  );
}

function simplifiedStatus(entity: IdentityEntity): { state: 'synced' | 'pending' | 'unmanaged'; label: string } {
  if (entity.kind === 'discovered-user' || entity.kind === 'discovered-group') return { state: 'pending', label: 'Pending' };
  if (entity.kind === 'user') return { state: entity.user.locked ? 'unmanaged' : 'synced', label: entity.user.locked ? 'Disabled' : 'Active' };
  if (entity.kind === 'group' || entity.kind === 'ssh-key' || entity.kind === 'permission') return { state: 'synced', label: 'Synced' };
  return { state: 'unmanaged', label: 'Unknown' };
}

function iconFor(kind: IdentityEntity['kind']) {
  if (kind.includes('user')) return UserRound;
  if (kind.includes('group')) return UsersRound;
  if (kind === 'ssh-key') return KeyRound;
  return FileKey2;
}

function hostSummary(entity: IdentityEntity): string {
  if (entity.kind === 'discovered-user') return `Discovered on ${compactHosts(entity.user.hosts)}`;
  if (entity.kind === 'discovered-group') return `Discovered on ${compactHosts(entity.group.hosts)}`;
  if (entity.kind === 'user' && entity.discoveredHosts.length) return `Observed on ${compactHosts(entity.discoveredHosts)}`;
  return '';
}

function compactHosts(hosts: string[]): string {
  const uniqueHosts = [...new Set(hosts)].sort();
  if (!uniqueHosts.length) return 'unknown host';
  if (uniqueHosts.length <= 2) return uniqueHosts.join(', ');
  return `${uniqueHosts.slice(0, 2).join(', ')} +${uniqueHosts.length - 2}`;
}
