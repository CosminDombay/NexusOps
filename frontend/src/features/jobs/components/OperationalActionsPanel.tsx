import { Pencil, Play, Trash2 } from 'lucide-react';

import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import type { OperationalAction } from '../types/job';

type OperationalActionsPanelProps = {
  actions: OperationalAction[];
  error: string | null;
  isExecuting: boolean;
  selectedActionId: string;
  selectedServerId: string;
  servers: Server[];
  onExecute: () => void;
  onDeleteAction: (action: OperationalAction) => void;
  onEditAction: (action: OperationalAction) => void;
  onSelectedActionChange: (value: string) => void;
  onSelectedServerChange: (value: string) => void;
};

export function OperationalActionsPanel({
  actions,
  error,
  isExecuting,
  selectedActionId,
  selectedServerId,
  servers,
  onExecute,
  onDeleteAction,
  onEditAction,
  onSelectedActionChange,
  onSelectedServerChange,
}: OperationalActionsPanelProps) {
  const targetSelector = useTargetSelection('single');
  const selectedAction = actions.find((action) => action.id === selectedActionId) ?? null;
  const groupedActions = groupActions(actions);
  const canExecute = Boolean(selectedActionId && selectedServerId) && !isExecuting;

  return (
    <section>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end">
        <div className="grid flex-1 gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <TargetSelector
              allowBulk={false}
              servers={servers}
              selection={{ mode: 'single', selectedId: selectedServerId, selectedIds: [] }}
              filters={targetSelector.filters}
              eligibility="jobs"
              title="Action target"
              description="Operational actions run against one inventory-managed host."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(nextSelection) => onSelectedServerChange(nextSelection.selectedId)}
            />
          </div>

          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Operational action</span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={selectedActionId}
              onChange={(event) => onSelectedActionChange(event.target.value)}
            >
              <option value="">Select action</option>
              {Object.entries(groupedActions).map(([category, categoryActions]) => (
                <optgroup key={category} label={category}>
                  {categoryActions.map((action) => (
                    <option key={action.id} value={action.id}>
                      {action.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>

        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!canExecute}
          type="button"
          onClick={onExecute}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {isExecuting ? 'Running' : 'Run action'}
        </button>
      </div>

      {selectedAction ? (
        <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-zinc-950">{selectedAction.name}</h3>
              <p className="mt-1 text-sm text-zinc-500">{selectedAction.description}</p>
              <p className="mt-2 break-all font-mono text-xs text-zinc-700">{selectedAction.command}</p>
            </div>
            {selectedAction.destructive ? (
              <span className="inline-flex w-fit rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                Changes host
              </span>
            ) : null}
            {!selectedAction.is_builtin ? (
              <div className="flex shrink-0 gap-2">
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-semibold text-zinc-700 hover:bg-white" type="button" onClick={() => onEditAction(selectedAction)}>
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                  Edit
                </button>
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-rose-300 px-3 text-sm font-semibold text-rose-700 hover:bg-white" type="button" onClick={() => onDeleteAction(selectedAction)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}

function groupActions(actions: OperationalAction[]): Record<string, OperationalAction[]> {
  return actions.reduce<Record<string, OperationalAction[]>>((groups, action) => {
    groups[action.category] = [...(groups[action.category] ?? []), action];
    return groups;
  }, {});
}
