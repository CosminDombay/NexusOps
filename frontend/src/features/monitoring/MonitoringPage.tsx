import { useEffect, useState } from 'react';
import { Activity, Cpu, Database, ExternalLink, RefreshCw } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { getMonitoringOverview, getPrometheusHealth } from './api/monitoringApi';
import type { MonitoringOverview, MonitoringProviderStatus, PrometheusHealth } from './types/monitoring';

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
  const prometheusProvider = providerByType(providers, 'prometheus');
  const grafanaProvider = providerByType(providers, 'grafana');
  const lokiProvider = providerByType(providers, 'loki');

  return (
    <div className="space-y-6">
      <PageHeader title="Monitoring" description="Prometheus-backed host metrics and inventory health signals." />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard icon={Database} label="Servers" value={overview?.total_servers ?? 0} />
        <MetricCard icon={Activity} label="Online" value={overview?.online_servers ?? 0} />
        <MetricCard icon={Activity} label="Offline" value={overview?.offline_servers ?? 0} />
        <MetricCard icon={Cpu} label="Prometheus" value={prometheusProvider?.reachable ? 'Ready' : 'Unavailable'} />
      </div>

      {prometheusProvider && !prometheusProvider.reachable ? (
        <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {providerMessage(prometheusProvider)}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <IntegrationLinkCard label="Prometheus" href={prometheusProvider?.url ?? null} status={providerStatus(prometheusProvider)} />
        <IntegrationLinkCard label="Grafana" href={grafanaProvider?.url ?? null} status={providerStatus(grafanaProvider)} />
        <IntegrationLinkCard label="Loki" href={lokiProvider?.url ?? null} status={providerStatus(lokiProvider)} />
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Server metrics</h3>
          <button className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-semibold text-zinc-700" disabled={isLoading} type="button" onClick={() => void refresh()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-50">
              <tr>
                {['Host', 'State', 'CPU', 'Memory', 'Disk', 'Uptime', 'Links'].map((heading) => (
                  <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {(overview?.servers ?? []).map((server) => (
                <tr key={server.server_id}>
                  <td className="px-5 py-4">
                    <div className="font-medium text-zinc-950">{server.hostname}</div>
                    <div className="font-mono text-xs text-zinc-500">{server.ip_address}</div>
                  </td>
                  <td className="px-5 py-4">{server.online ? 'Online' : 'Offline'}</td>
                  <td className="px-5 py-4">{formatPercent(server.cpu_usage_percent)}</td>
                  <td className="px-5 py-4">{formatPercent(server.memory_usage_percent)}</td>
                  <td className="px-5 py-4">{formatPercent(server.disk_usage_percent)}</td>
                  <td className="px-5 py-4">{formatDuration(server.uptime_seconds)}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <MetricLink label="Grafana" href={server.grafana_url} />
                      <MetricLink label="Prom" href={server.prometheus_url} />
                      <MetricLink label="Loki" href={server.loki_url} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!isLoading && overview?.servers.length === 0 ? <p className="p-5 text-sm text-zinc-500">No inventory servers available.</p> : null}
        </div>
      </section>
    </div>
  );
}

function providerByType(providers: MonitoringProviderStatus[], providerType: string): MonitoringProviderStatus | undefined {
  return providers.find((provider) => provider.provider_type === providerType);
}

function providerStatus(provider: MonitoringProviderStatus | undefined): string {
  if (!provider?.configured) return 'Not configured';
  return provider.reachable ? 'Ready' : 'Unavailable';
}

function providerMessage(provider: MonitoringProviderStatus): string {
  if (!provider.configured) return 'Prometheus integration is not configured or is disabled.';
  return provider.error ?? 'Prometheus integration is configured but not reachable.';
}

function IntegrationLinkCard({ label, href, status }: { label: string; href: string | null; status: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-zinc-500">{label}</p>
          <p className="mt-2 text-lg font-semibold text-zinc-950">{status}</p>
        </div>
        {href ? (
          <a className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 hover:bg-zinc-50" href={href} rel="noreferrer" target="_blank">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        ) : (
          <ExternalLink className="h-5 w-5 text-zinc-300" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}

function MetricLink({ label, href }: { label: string; href: string | null }) {
  if (!href) {
    return <span className="text-xs text-zinc-400">{label}</span>;
  }
  return (
    <a className="text-xs font-semibold text-zinc-950 underline" href={href} rel="noreferrer" target="_blank">
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

function formatDuration(value: number | null): string {
  if (value === null) {
    return 'No data';
  }
  const hours = Math.floor(value / 3600);
  return `${hours}h`;
}
