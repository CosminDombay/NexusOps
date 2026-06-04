import { Play } from 'lucide-react';

import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import type { Credential } from '../../credentials/types/credential';

type RunCommandPanelProps = {
  command: string;
  credentials: Credential[];
  error: string | null;
  executionCredentialRef: string;
  isExecuting: boolean;
  operationType: string;
  selectedServerId: string;
  selectedServerIds: string[];
  servers: Server[];
  onCommandChange: (value: string) => void;
  onExecutionCredentialChange: (value: string) => void;
  onOperationTypeChange: (value: string) => void;
  onSelectedServerChange: (value: string) => void;
  onSelectedServersChange: (value: string[]) => void;
  onSubmit: () => void;
};

export function RunCommandPanel({
  command,
  credentials,
  error,
  executionCredentialRef,
  isExecuting,
  operationType,
  selectedServerId,
  selectedServerIds,
  servers,
  onCommandChange,
  onExecutionCredentialChange,
  onOperationTypeChange,
  onSelectedServerChange,
  onSelectedServersChange,
  onSubmit,
}: RunCommandPanelProps) {
  const targetSelector = useTargetSelection(selectedServerIds.length ? 'bulk' : 'single');
  const canSubmit = Boolean((selectedServerId || selectedServerIds.length) && command.trim()) && !isExecuting;

  return (
    <section>
      <div className="mb-4">
        <TargetSelector
          servers={servers}
          selection={{
            mode: targetSelector.selection.mode,
            selectedId: selectedServerId,
            selectedIds: selectedServerIds,
          }}
          filters={targetSelector.filters}
          eligibility="jobs"
          title="Command targets"
          description="Run a raw command against one host or a selected group of hosts."
          onFiltersChange={targetSelector.setFilters}
          onSelectionChange={(nextSelection) => {
            targetSelector.setMode(nextSelection.mode);
            onSelectedServerChange(nextSelection.selectedId);
            onSelectedServersChange(nextSelection.selectedIds);
          }}
        />
      </div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        <div className="grid flex-1 gap-4 md:grid-cols-[1fr_160px]">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Operation</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={operationType}
              onChange={(event) => onOperationTypeChange(event.target.value)}
            />
          </label>

          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-zinc-950">Command</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              placeholder="uptime"
              value={command}
              onChange={(event) => onCommandChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && canSubmit) {
                  onSubmit();
                }
              }}
            />
          </label>

          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-zinc-950">Execution / sudo credential</span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={executionCredentialRef}
              onChange={(event) => onExecutionCredentialChange(event.target.value)}
            >
              <option value="">Use target saved credential or passwordless access</option>
              {credentials
                .filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password')
                .map((credential) => (
                  <option key={credential.id} value={credential.id}>
                    {credential.name} ({credential.credential_type.replace('_', ' ')})
                  </option>
                ))}
            </select>
          </label>
        </div>

        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!canSubmit}
          type="button"
          onClick={onSubmit}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {isExecuting ? 'Running' : 'Execute'}
        </button>
      </div>

      {error ? <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}
