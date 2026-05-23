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
          <h3 className="text-base font-semibold text-zinc-950">Infrastructure Observability</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Snapshot-driven node readiness for host metrics, logs, and optional container telemetry.
          </p>
        </div>
        <div className="divide-y divide-zinc-100">
          {(overview?.servers ?? []).map((server) => (
            <ObservabilityRow key={server.server_id} server={server} />
          ))}
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
  const primaryReason = primaryReadinessReason(server);
  const summary = summarizeSignals(server);

  return (
    <article className="px-5 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-zinc-950">{server.hostname}</h4>
            <StatusPill tone={readinessTone(server.monitoring_status)}>{server.monitoring_status}</StatusPill>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span className="font-mono">{server.ip_address}</span>
            <span>{server.monitoring_interface ?? 'no interface'}</span>
            <span>{server.monitoring_strategy}</span>
          </div>
          {server.monitoring_targets.length ? (
            <div className="mt-1 truncate font-mono text-xs text-zinc-400" title={server.monitoring_targets[0]}>
              {server.monitoring_targets[0]}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <MetricLink label="Prometheus" href={server.prometheus_url} />
          <MetricLink label="Node-Exporter" href={server.advanced_metrics_url} />
          <MetricLink label="cAdvisor" href={server.container_metrics_url} />
          <MetricLink label="Logs" href={server.advanced_logs_url} />
        </div>
      </div>

      {server.metrics_available && !server.advanced_metrics_url ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Host metrics are detected, but no Grafana Node-Exporter dashboard URL is configured or discoverable.
        </div>
      ) : null}
      {server.cadvisor_running && !server.container_metrics_url ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          cAdvisor is detected, but no Grafana cAdvisor dashboard URL is configured or discoverable.
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <SignalCard
          title="Host Metrics"
          state={server.metrics_available ? 'Ready' : 'Missing'}
          tone={server.metrics_available ? 'success' : 'danger'}
          detail={`node_exporter ${server.node_exporter_reachable ? 'reachable' : 'not reachable'} / scrape ${formatReason(server.scrape_target_health)}`}
        />
        <SignalCard
          title="Logs"
          state={server.logs_available ? 'Ready' : 'Missing'}
          tone={server.logs_available ? 'success' : 'warning'}
          detail={server.promtail_reachable ? 'promtail reachable' : 'log ingestion unavailable'}
        />
        <SignalCard
          title="Containers"
          state={server.monitoring_strategy === 'host' ? 'Optional' : server.cadvisor_running ? 'Ready' : 'Missing'}
          tone={server.monitoring_strategy === 'host' ? 'muted' : server.cadvisor_running ? 'success' : 'warning'}
          detail={server.monitoring_strategy === 'host' ? 'cAdvisor not required' : `Docker ${server.docker_runtime_available ? 'available' : 'not confirmed'}`}
        />
      </div>

      <div className="mt-3 flex flex-col gap-2 text-xs text-zinc-500 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <span>{summary}</span>
          {primaryReason ? <span className="ml-2 text-amber-600">{primaryReason}</span> : null}
          {server.remediation.length ? <span className="ml-2">{server.remediation[0]}</span> : null}
        </div>

        {server.technical_details.length ? (
          <details className="max-w-full lg:max-w-xl">
            <summary className="cursor-pointer text-xs font-semibold text-zinc-400 hover:text-zinc-200">
              Show technical details
            </summary>
            <div className="mt-2 max-h-28 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-2 font-mono text-[11px] leading-relaxed text-zinc-400">
              {server.technical_details.slice(0, 4).map((detail) => (
                <div key={detail} className="break-words">{detail}</div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </article>
  );
}

function SignalCard({
  title,
  state,
  detail,
  tone,
}: {
  title: string;
  state: string;
  detail: string;
  tone: 'success' | 'warning' | 'danger' | 'muted';
}) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{title}</span>
        <StatusPill tone={tone}>{state}</StatusPill>
      </div>
      <p className="mt-2 text-xs text-zinc-500">{detail}</p>
    </div>
  );
}

function primaryReadinessReason(server: ServerMetrics): string | null {
  const reason = server.readiness_reasons.find((item) => !isTechnicalNoise(item));
  return reason ? formatReason(reason) : null;
}

function summarizeSignals(server: ServerMetrics): string {
  const cpu = formatPercent(server.cpu_usage_percent);
  const memory = formatPercent(server.memory_usage_percent);
  const disk = formatPercent(server.disk_usage_percent);
  if (cpu === 'No data' && memory === 'No data' && disk === 'No data') {
    return 'No operational metric snapshot yet.';
  }
  return `CPU ${cpu} / Mem ${memory} / Disk ${disk}`;
}

function isTechnicalNoise(value: string): boolean {
  const normalized = value.toLowerCase();
  return (
    normalized.includes('client error') ||
    normalized.includes('http') ||
    normalized.includes('query=') ||
    normalized.includes('traceback') ||
    normalized.length > 80
  );
}

function readinessTone(value: string): 'success' | 'warning' | 'danger' | 'muted' {
  const normalized = value.toLowerCase();
  if (normalized === 'healthy') {
    return 'success';
  }
  if (normalized === 'partial' || normalized === 'stale') {
    return 'warning';
  }
  if (normalized === 'missing') {
    return 'danger';
  }
  return 'muted';
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
