import { useEffect, useMemo, useState } from 'react';
import { Activity, ExternalLink, RefreshCw, Server, ShieldCheck, Signal, TriangleAlert } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, StatusPill } from '../../components/operations/OperationalComponents';
import { SearchField } from '../../components/search/SearchField';
import { getApiErrorMessage } from '../../lib/api/client';
import { matchesSearch } from '../../lib/search/match';
import { getMonitoringOverview, validateMonitoring } from './api/monitoringApi';
import type { MonitoringOverview, MonitoringProviderStatus, ServerMetrics } from './types/monitoring';

export function MonitoringPage() {
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [search, setSearch] = useState('');
  const filteredServers = useMemo(
    () =>
      (overview?.servers ?? []).filter((server) =>
        matchesSearch(search, [
          server.hostname,
          server.ip_address,
          server.monitoring_state,
          server.monitoring_status,
          server.monitoring_targets,
          server.node_exporter_status,
          server.promtail_status,
          server.cadvisor_status,
          server.readiness_reasons,
          server.component_failure_reasons,
        ]),
      ),
    [overview?.servers, search],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      setOverview(await getMonitoringOverview());
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function runValidation() {
    setIsValidating(true);
    setError(null);
    try {
      await validateMonitoring();
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsValidating(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Monitoring Validation"
        description="Persisted operational checks for exporter reachability, monitoring availability, stale state, and Grafana handoff links."
        actions={
          <div className="flex flex-wrap gap-2">
            <PageActionButton icon={RefreshCw} tone="secondary" disabled={isLoading} onClick={() => void refresh()}>
              Reload
            </PageActionButton>
            <PageActionButton icon={Activity} tone="primary" disabled={isValidating} onClick={() => void runValidation()}>
              Validate
            </PageActionButton>
          </div>
        }
      />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <section className="grid gap-4 md:grid-cols-5">
        <MetricCard icon={Server} label="Nodes" value={overview?.total_servers ?? 0} />
        <MetricCard icon={ShieldCheck} label="Monitored" value={overview?.monitored_servers ?? 0} />
        <MetricCard icon={Signal} label="Partial" value={overview?.partial_servers ?? 0} />
        <MetricCard icon={TriangleAlert} label="Stale" value={overview?.stale_servers ?? 0} />
        <MetricCard icon={Activity} label="Unmonitored" value={overview?.unmonitored_servers ?? 0} />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {(overview?.providers ?? []).map((provider) => (
          <ProviderCard key={provider.provider_type} provider={provider} />
        ))}
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Node Monitoring State</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Snapshot-only view of node_exporter, promtail, and cAdvisor validation.
          </p>
          <SearchField
            className="mt-3"
            placeholder="Search nodes, targets, readiness..."
            value={search}
            onChange={setSearch}
          />
        </div>
        <div className="divide-y divide-zinc-100">
          {filteredServers.map((server) => (
            <MonitoringRow key={server.server_id} server={server} />
          ))}
          {isLoading ? <p className="p-5 text-sm text-zinc-500">Loading monitoring snapshots...</p> : null}
          {!isLoading && filteredServers.length === 0 ? (
            <p className="p-5 text-sm text-zinc-500">
              {search ? 'No monitoring nodes match this search.' : 'No managed nodes available.'}
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function ProviderCard({ provider }: { provider: MonitoringProviderStatus }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium capitalize text-zinc-500">{provider.provider_type}</p>
          <div className="mt-2">
            <RuntimeBadge value={provider.reachable ? 'ready' : provider.configured ? 'unavailable' : 'not_configured'} />
          </div>
          {provider.error ? <p className="mt-2 text-xs text-rose-700">{provider.error}</p> : null}
        </div>
        {provider.url ? <IconLink href={provider.url} label={`Open ${provider.provider_type}`} /> : null}
      </div>
    </div>
  );
}

function MonitoringRow({ server }: { server: ServerMetrics }) {
  return (
    <article className="px-5 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-zinc-950">{server.hostname}</h4>
            <StatusPill tone={stateTone(server.monitoring_state)}>{server.monitoring_status}</StatusPill>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span className="font-mono">{server.ip_address}</span>
            <span>{server.monitoring_targets[0] ?? 'no target'}</span>
            <span>validated {formatDate(server.last_validated_at)}</span>
            <span>last success {formatDate(server.last_successful_check_at)}</span>
          </div>
        </div>
        {server.open_grafana_url ? <IconTextLink href={server.open_grafana_url} label="Open Grafana" /> : null}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <SignalCard title="node_exporter" status={server.node_exporter_status} />
        <SignalCard title="promtail" status={server.promtail_status} />
        <SignalCard title="cAdvisor" status={server.cadvisor_status} />
      </div>

      {server.readiness_reasons.length ? (
        <p className="mt-3 text-xs text-zinc-500">{server.readiness_reasons.slice(0, 3).map(formatLabel).join(' / ')}</p>
      ) : null}
      {Object.keys(server.component_failure_reasons).length ? (
        <p className="mt-2 text-xs text-zinc-500">
          {Object.entries(server.component_failure_reasons)
            .slice(0, 3)
            .map(([component, reason]) => `${formatLabel(component)}: ${formatLabel(reason)}`)
            .join(' / ')}
        </p>
      ) : null}
    </article>
  );
}

function SignalCard({ title, status }: { title: string; status: string }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-zinc-500">{title}</span>
        <StatusPill tone={componentTone(status)}>{formatLabel(status)}</StatusPill>
      </div>
    </div>
  );
}

function IconLink({ href, label }: { href: string; label: string }) {
  return (
    <a className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 hover:bg-zinc-50" href={href} rel="noreferrer" target="_blank" title={label}>
      <ExternalLink className="h-4 w-4" aria-hidden="true" />
    </a>
  );
}

function IconTextLink({ href, label }: { href: string; label: string }) {
  return (
    <a className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" href={href} rel="noreferrer" target="_blank">
      {label}
      <ExternalLink className="h-4 w-4" aria-hidden="true" />
    </a>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-950">{value}</p>
        </div>
        <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
      </div>
    </div>
  );
}

function stateTone(state: string): 'success' | 'warning' | 'danger' | 'muted' {
  if (state === 'monitored') return 'success';
  if (state === 'partial' || state === 'stale') return 'warning';
  if (state === 'unmonitored') return 'danger';
  return 'muted';
}

function componentTone(status: string): 'success' | 'warning' | 'danger' | 'muted' {
  if (status === 'healthy') return 'success';
  if (status === 'unavailable') return 'danger';
  if (status === 'not_configured') return 'warning';
  return 'muted';
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ');
}

function formatDate(value: string | null): string {
  if (!value) {
    return 'never';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}
