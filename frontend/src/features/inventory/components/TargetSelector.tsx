import { Search } from 'lucide-react';

import type { Server } from '../types/server';
import type { TargetFilters, TargetSelection } from '../types/targetSelection';
import { useFilteredTargets } from '../hooks/useTargetSelection';

type TargetSelectorProps = {
  servers: Server[];
  selection: TargetSelection;
  filters: TargetFilters;
  title?: string;
  description?: string;
  allowBulk?: boolean;
  eligibility?: 'jobs' | 'deployments' | 'profiles' | 'identity' | 'shell' | 'all';
  onSelectionChange: (selection: TargetSelection) => void;
  onFiltersChange: (filters: TargetFilters) => void;
};

export function TargetSelector({
  servers,
  selection,
  filters,
  title = 'Targets',
  description = 'Select inventory-managed hosts for this operation.',
  allowBulk = true,
  eligibility = 'all',
  onSelectionChange,
  onFiltersChange,
}: TargetSelectorProps) {
  const eligibleServers = servers.filter((server) => isEligibleTarget(server, eligibility));
  const filteredTargets = useFilteredTargets(eligibleServers, filters);
  const environments = unique(eligibleServers.map((server) => server.environment));
  const providers = unique(eligibleServers.map((server) => server.provider));
  const selectedCount = selection.mode === 'bulk' ? selection.selectedIds.length : selection.selectedId ? 1 : 0;

  function updateSelection(patch: Partial<TargetSelection>) {
    onSelectionChange({ ...selection, ...patch });
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
          <p className="mt-1 text-sm text-zinc-500">{description}</p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-normal text-zinc-500">
            {selectedCount} selected
          </p>
        </div>
        {allowBulk ? (
          <div className="inline-flex w-fit rounded-md border border-zinc-300 bg-zinc-50 p-1">
            {(['single', 'bulk'] as const).map((mode) => (
              <button
                key={mode}
                className={`rounded px-3 py-1.5 text-sm font-semibold transition ${
                  selection.mode === mode ? 'bg-cyan-400 text-zinc-950' : 'text-zinc-600 hover:text-zinc-950'
                }`}
                type="button"
                onClick={() => updateSelection({ mode })}
              >
                {mode === 'single' ? 'Single' : 'Bulk'}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_180px_160px]">
        <label className="relative block">
          <span className="sr-only">Search targets</span>
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-zinc-400" aria-hidden="true" />
          <input
            className="h-10 w-full rounded-md border border-zinc-300 bg-white pl-9 pr-3 text-sm text-zinc-950 outline-none focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
            placeholder="Search hostname, IP, provider..."
            value={filters.search}
            onChange={(event) => onFiltersChange({ ...filters, search: event.target.value })}
          />
        </label>
        <SelectFilter
          label="Environment"
          value={filters.environment}
          options={environments}
          onChange={(environment) => onFiltersChange({ ...filters, environment })}
        />
        <SelectFilter
          label="Provider"
          value={filters.provider}
          options={providers}
          onChange={(provider) => onFiltersChange({ ...filters, provider })}
        />
        <label className="block">
          <span className="sr-only">Managed filter</span>
          <select
            className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
            value={filters.managed}
            onChange={(event) =>
              onFiltersChange({ ...filters, managed: event.target.value as TargetFilters['managed'] })
            }
          >
            <option value="all">All states</option>
            <option value="managed">Managed</option>
            <option value="unmanaged">Unmanaged</option>
          </select>
        </label>
      </div>

      {selection.mode === 'single' ? (
        <div className="mt-4">
          <select
            className="h-11 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
            value={selection.selectedId}
            onChange={(event) => updateSelection({ selectedId: event.target.value })}
          >
            <option value="">Select inventory host</option>
            {filteredTargets.map((server) => (
              <option key={server.id} value={server.id}>
                {server.hostname} - {server.ip_address} - {server.environment} - {server.lifecycle_state}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="mt-4 grid max-h-72 gap-2 overflow-auto sm:grid-cols-2 xl:grid-cols-3">
          {filteredTargets.map((server) => {
            const checked = selection.selectedIds.includes(server.id);
            return (
              <label
                key={server.id}
                className={`flex min-h-16 items-start gap-3 rounded-md border px-3 py-2 text-sm transition ${
                  checked ? 'border-cyan-400/70 bg-cyan-400/10 shadow-sm shadow-cyan-950/20' : 'border-zinc-200 bg-white'
                }`}
              >
                <input
                  checked={checked}
                  className="mt-1 h-4 w-4 rounded border-zinc-300 text-cyan-500 focus:ring-cyan-400"
                  type="checkbox"
                  onChange={(event) =>
                    updateSelection({
                      selectedIds: event.target.checked
                        ? [...selection.selectedIds, server.id]
                        : selection.selectedIds.filter((serverId) => serverId !== server.id),
                    })
                  }
                />
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-zinc-950">{server.hostname}</span>
                  <span className="block truncate font-mono text-xs text-zinc-500">{server.ip_address}</span>
                  <span className="mt-1 flex flex-wrap gap-1">
                    <TargetBadge label={server.environment} />
                    <TargetBadge label={server.provider} />
                    <TargetBadge label={server.managed ? 'managed' : 'unmanaged'} />
                    <TargetBadge label={server.lifecycle_state} />
                  </span>
                </span>
              </label>
            );
          })}
          {filteredTargets.length === 0 ? (
            <p className="rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-500">
              No hosts match the current filters.
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}

function isEligibleTarget(server: Server, eligibility: TargetSelectorProps['eligibility']): boolean {
  if (eligibility === 'all') {
    return true;
  }
  const flags = server.runtime_state?.eligibility;
  if (!flags) {
    return server.managed && !['archived', 'decommissioned', 'deleted'].includes(server.lifecycle_state);
  }
  if (eligibility === 'jobs') {
    return flags.can_run_jobs;
  }
  if (eligibility === 'deployments') {
    return flags.can_deploy;
  }
  if (eligibility === 'profiles') {
    return flags.can_apply_profiles;
  }
  if (eligibility === 'identity') {
    return flags.can_manage_identity;
  }
  if (eligibility === 'shell') {
    return flags.can_open_shell;
  }
  return true;
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <select
        className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">All {label.toLowerCase()}s</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function TargetBadge({ label }: { label: string | boolean }) {
  return (
    <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600 ring-1 ring-zinc-200">
      {String(label)}
    </span>
  );
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}
