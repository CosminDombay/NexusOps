import { Link2, Loader2, RefreshCcw, RotateCcw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { SearchField } from '../../../components/search/SearchField';
import { getApiErrorMessage } from '../../../lib/api/client';
import { matchesSearch } from '../../../lib/search/match';
import { getTrashReferences, listTrash, purgeTrashItem, restoreTrashItem } from '../api/trashApi';
import type { TrashGroup, TrashItem, TrashReference } from '../types/trash';

export function TrashPage() {
  const [groups, setGroups] = useState<TrashGroup[]>([]);
  const [referencesByItem, setReferencesByItem] = useState<Record<string, TrashReference[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const trash = await listTrash();
      setGroups(trash.groups);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRestore(item: TrashItem) {
    if (!item.restore_supported) return;
    if (!window.confirm(`Restore ${item.name}? It will return to normal NexusOps lists and workflows.`)) {
      return;
    }
    await runItemAction(item, async () => {
      await restoreTrashItem(item.item_type, item.item_id);
      setSuccess(`Restored ${item.name}.`);
      await load();
    });
  }

  async function handlePurge(item: TrashItem) {
    if (!item.purge_supported) return;
    if (
      !window.confirm(
        `Permanently delete ${item.name}? This cannot be undone and is blocked while references exist.`,
      )
    ) {
      return;
    }
    await runItemAction(item, async () => {
      await purgeTrashItem(item.item_type, item.item_id);
      setSuccess(`Permanently deleted ${item.name}.`);
      await load();
    });
  }

  async function handleReferences(item: TrashItem) {
    await runItemAction(item, async () => {
      const usage = await getTrashReferences(item.item_type, item.item_id);
      setReferencesByItem((current) => ({
        ...current,
        [itemKey(item)]: usage.references,
      }));
      setSuccess(
        usage.references.length
          ? `${item.name} has ${usage.references.length} active reference(s).`
          : `${item.name} has no active references.`,
      );
    });
  }

  async function runItemAction(item: TrashItem, action: () => Promise<void>) {
    setBusyKey(itemKey(item));
    setError(null);
    setSuccess(null);
    try {
      await action();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setBusyKey(null);
    }
  }

  const totalItems = groups.reduce((count, group) => count + group.items.length, 0);
  const filteredGroups = useMemo(
    () =>
      groups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) =>
            matchesSearch(search, [
              group.title,
              item.name,
              item.item_type,
              item.deleted_by,
              item.delete_reason,
              item.metadata,
            ]),
          ),
        }))
        .filter((group) => group.items.length > 0),
    [groups, search],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Trash"
        description="Recover deleted NexusOps records or permanently remove items once their references are cleared."
        actions={
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-2 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-800 disabled:opacity-60"
            disabled={isLoading}
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
            Refresh
          </button>
        }
      />

      {error && (
        <div className="rounded-md border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-100">
          {success}
        </div>
      )}

      <div className="rounded-md border border-slate-800 bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-slate-100">Deleted records</p>
            <p className="text-xs text-slate-400">
              {totalItems} item{totalItems === 1 ? '' : 's'} in Trash
            </p>
          </div>
        </div>
        <div className="border-b border-slate-800 px-4 py-3">
          <SearchField
            placeholder="Search Trash, item types, metadata..."
            value={search}
            onChange={setSearch}
          />
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 px-4 py-8 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading Trash...
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="px-4 py-8 text-sm text-slate-400">
            {search ? 'No Trash items match this search.' : 'Trash is empty.'}
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {filteredGroups.map((group) => (
              <section key={group.item_type}>
                <div className="border-b border-slate-800 bg-slate-900/80 px-4 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-sm font-semibold text-cyan-200">{group.title}</h2>
                    <span className="text-xs text-slate-400">{group.items.length}</span>
                  </div>
                </div>
                <div className="divide-y divide-slate-800">
                  {group.items.map((item) => (
                    <TrashRow
                      key={itemKey(item)}
                      item={item}
                      references={referencesByItem[itemKey(item)]}
                      isBusy={busyKey === itemKey(item)}
                      onReferences={handleReferences}
                      onRestore={handleRestore}
                      onPurge={handlePurge}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TrashRow({
  item,
  references,
  isBusy,
  onReferences,
  onRestore,
  onPurge,
}: {
  item: TrashItem;
  references?: TrashReference[];
  isBusy: boolean;
  onReferences: (item: TrashItem) => void | Promise<void>;
  onRestore: (item: TrashItem) => void | Promise<void>;
  onPurge: (item: TrashItem) => void | Promise<void>;
}) {
  return (
    <div className="px-4 py-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="break-words text-sm font-semibold text-slate-100">{item.name}</p>
            {item.reference_count > 0 && (
              <span className="rounded-md border border-amber-400/40 bg-amber-950/40 px-2 py-0.5 text-xs font-semibold text-amber-200">
                {item.reference_count} ref{item.reference_count === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-400">
            {item.deleted_at && <span>deleted {formatDate(item.deleted_at)}</span>}
            {item.deleted_by && <span>by {item.deleted_by}</span>}
            {Object.entries(item.metadata).map(([key, value]) =>
              value === null || value === undefined || value === '' ? null : (
                <span key={key}>{key.split('_').join(' ')}: {String(value)}</span>
              ),
            )}
          </div>
          {item.delete_reason && <p className="mt-2 text-xs text-slate-300">{item.delete_reason}</p>}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onReferences(item)}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-700 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-900 disabled:opacity-60"
            disabled={isBusy}
          >
            <Link2 className="h-4 w-4" />
            References
          </button>
          <button
            type="button"
            onClick={() => void onRestore(item)}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-emerald-500/50 px-3 text-xs font-semibold text-emerald-100 hover:bg-emerald-950/50 disabled:opacity-60"
            disabled={isBusy || !item.restore_supported}
          >
            <RotateCcw className="h-4 w-4" />
            Restore
          </button>
          <button
            type="button"
            onClick={() => void onPurge(item)}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-rose-500/50 px-3 text-xs font-semibold text-rose-100 hover:bg-rose-950/50 disabled:opacity-60"
            disabled={isBusy || !item.purge_supported}
          >
            {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Delete
          </button>
        </div>
      </div>

      {references && (
        <div className="mt-3 rounded-md border border-slate-800 bg-slate-900/70 p-3">
          {references.length === 0 ? (
            <p className="text-xs text-slate-400">No active references.</p>
          ) : (
            <div className="space-y-2">
              {references.map((reference) => (
                <div key={`${reference.reference_type}:${reference.reference_id}:${reference.field}`} className="text-xs text-slate-300">
                  <span className="font-semibold text-slate-100">{reference.reference_type}</span>
                  <span> · {reference.name}</span>
                  <span> · {reference.field}</span>
                  {reference.detail && <span> · {reference.detail}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function itemKey(item: TrashItem) {
  return `${item.item_type}:${item.item_id}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
