import { useEffect, useState } from 'react';
import { Activity, Database, ExternalLink, RefreshCw, Server, Signal, TriangleAlert } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, StatusPill } from '../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../lib/api/client';
import { getMonitoringOverview, getPrometheusHealth } from './api/monitoringApi';
import type { MonitoringOverview, MonitoringProviderStatus, PrometheusHealth, ServerMetrics } from './types/monitoring';

export function MonitoringPage() {
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [prometheus, setPrometheus] = useState<PrometheusHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextOverview, nextPrometheus] = await Promise.all([getMonitoringOverview(), getPrometheusHealth()]);
      setOverview(nextOverview);
      setPrometheus(nextPrometheus);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const providers = prometheus?.providers ?? overview?.providers ?? [];
  const degradedNodes = overview?.servers.filter((server) => server.monitoring_state !== 'monitoring_ready') ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Monitoring Readiness"
        description="Infrastructure observability readiness across telemetry providers, exporters, stale metrics, and log ingestion."
        actions={
          <PageActionButton icon={RefreshCw} tone="secondary" disabled={isLoading} onClick={() => void refresh()}>
            Refresh
          </PageActionButton>
        }
      />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <section className="grid gap-4 md:grid-cols-5">
        <MetricCard icon={Server} label="Nodes" value={overview?.total_servers ?? 0} />
        <MetricCard icon={Signal} label="Observable" value={overview?.observable_servers ?? 0} />
        <MetricCard icon={TriangleAlert} label="Degraded" value={overview?.degraded_servers ?? 0} />
        <MetricCard icon={Activity} label="Metrics missing" value={overview?.metrics_missing_servers ?? 0} />
        <MetricCard icon={Database} label="Logs missing" value={overview?.logs_missing_servers ?? 0} />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {providers.map((provider) => (
          <ProviderReadinessCard key={provider.provider_type} provider={provider} />
        ))}
      </section>

      {degradedNodes.length ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>{degradedNodes.length} node(s) need observability attention.</strong>{' '}
          Most common causes are missing exporters, unavailable Loki streams, scrape failures, or stale metrics.
        </section>
      ) : null}

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Infrastructure Observability Board</h3>
          <p className="mt-1 text-sm text-zinc-500">
            NexusOps derives readiness from telemetry availability. Grafana is available only as optional advanced tooling.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-50">
              <tr>
                {['Node', 'Readiness', 'Metrics', 'Logs', 'Exporters', 'Scrape', 'Staleness', 'Signals'].map((heading) => (
                  <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {(overview?.servers ?? []).map((server) => (
                <ObservabilityRow key={server.server_id} server={server} />
              ))}
            </tbody>
          </table>
          {isLoading ? <p className="p-5 text-sm text-zinc-500">Checking telemetry readiness...</p> : null}
          {!isLoading && overview?.servers.length === 0 ? <p className="p-5 text-sm text-zinc-500">No inventory nodes available.</p> : null}
        </div>
      </section>
    </div>
  );
}

function ProviderReadinessCard({ provider }: { provider: MonitoringProviderStatus }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium capitalize text-zinc-500">{provider.provider_type}</p>
          <div className="mt-2">
            <RuntimeBadge value={provider.reachable ? 'ready' : provider.configured ? 'unavailable' : 'not_configured'} />
          </div>
          <p className="mt-3 text-sm text-zinc-500">
            {provider.provider_type === 'grafana'
              ? 'Optional advanced visualization.'
              : provider.provider_type === 'loki'
                ? 'Log ingestion and stream readiness.'
                : 'Metrics scrape and exporter visibility.'}
          </p>
          {provider.error ? <p className="mt-2 text-xs text-rose-700">{providerStatusMessage(provider)}</p> : null}
        </div>
        {provider.url ? (
          <a className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 hover:bg-zinc-50" href={provider.url} rel="noreferrer" target="_blank" title="Open provider">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        ) : null}
      </div>
    </div>
  );
}

function ObservabilityRow({ server }: { server: ServerMetrics }) {
  return (
    <tr>
      <td className="px-5 py-4">
        <div className="font-medium text-zinc-950">{server.hostname}</div>
        <div className="font-mono text-xs text-zinc-500">{server.ip_address}</div>
        {server.monitoring_targets.length ? (
          <div className="mt-1 max-w-52 truncate font-mono text-[11px] text-zinc-400" title={server.monitoring_targets.join(', ')}>
            {server.monitoring_interface ?? 'target'}: {server.monitoring_targets[0]}
          </div>
        ) : null}
      </td>
      <td className="px-5 py-4"><RuntimeBadge value={server.monitoring_status} /></td>
      <td className="px-5 py-4">
        <StatusPill tone={server.metrics_available ? 'success' : 'danger'}>
          {server.metrics_available ? 'Available' : 'Missing'}
        </StatusPill>
      </td>
      <td className="px-5 py-4">
        <StatusPill tone={server.logs_available ? 'success' : 'warning'}>
          {server.logs_available ? 'Available' : 'Missing'}
        </StatusPill>
      </td>
      <td className="px-5 py-4">
        <div className="flex flex-wrap gap-1.5">
          <StatusPill tone={server.node_exporter_detected ? 'success' : 'warning'}>node</StatusPill>
          <StatusPill tone={server.cadvisor_running ? 'success' : server.monitoring_strategy === 'host' ? 'muted' : 'warning'}>cadvisor</StatusPill>
          <StatusPill tone={server.promtail_detected ? 'success' : 'warning'}>promtail</StatusPill>
        </div>
      </td>
      <td className="px-5 py-4"><RuntimeBadge value={server.scrape_target_health} /></td>
      <td className="px-5 py-4">
        <StatusPill tone={server.stale_metrics ? 'warning' : 'success'}>
          {server.stale_metrics ? 'Stale' : 'Fresh'}
        </StatusPill>
      </td>
      <td className="px-5 py-4">
        <div className="max-w-md space-y-1">
          <div className="text-xs text-zinc-500">
            CPU {formatPercent(server.cpu_usage_percent)} / Mem {formatPercent(server.memory_usage_percent)} / Disk {formatPercent(server.disk_usage_percent)}
          </div>
          {server.readiness_reasons.length ? (
            <div className="text-xs text-amber-700">{server.readiness_reasons.slice(0, 3).map(formatReason).join(', ')}</div>
          ) : null}
          {server.remediation.length ? (
            <div className="text-xs text-zinc-500">{server.remediation[0]}</div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <MetricLink label="Prometheus" href={server.prometheus_url} />
            <MetricLink label="Advanced metrics" href={server.advanced_metrics_url} />
            <MetricLink label="Advanced logs" href={server.advanced_logs_url} />
          </div>
        </div>
      </td>
    </tr>
  );
}

function MetricLink({ label, href }: { label: string; href: string | null }) {
  if (!href) {
    return null;
  }
  return (
    <a className="text-xs font-semibold text-zinc-700 underline underline-offset-2 hover:text-zinc-950" href={href} rel="noreferrer" target="_blank">
      {label}
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

function formatPercent(value: number | null): string {
  return value === null ? 'No data' : `${value.toFixed(1)}%`;
}

function formatReason(value: string): string {
  return value.replace(/_/g, ' ');
}

function providerStatusMessage(provider: MonitoringProviderStatus): string {
  if (!provider.configured) {
    return `${provider.provider_type} integration is not configured.`;
  }
  return `${provider.provider_type} readiness unavailable.`;
}
