import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Activity, Box, ExternalLink, HardDrive, RefreshCw, ServerIcon, ShieldCheck } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listDeployments } from '../../deployments/api/deploymentsApi';
import type { Deployment } from '../../deployments/types/deployment';
import { listLinuxGroups, listLinuxUsers, listSSHKeys } from '../../identity/api/identityApi';
import type { LinuxGroup, LinuxUser, SSHKey } from '../../identity/types/identity';
import { listJobs } from '../../jobs/api/jobsApi';
import type { Job } from '../../jobs/types/job';
import { getServerMetrics, getPrometheusHealth } from '../../monitoring/api/monitoringApi';
import type { PrometheusHealth, ServerMetrics } from '../../monitoring/types/monitoring';
import {
  getServer,
  getServerDocker,
  getServerNetwork,
  getServerSystem,
} from '../api/serversApi';
import type { HostDocker, HostNetwork, HostSystem, Server } from '../types/server';
import { EnvironmentBadge, HealthBadge, LifecycleBadge, SyncBadge } from '../components/ServerBadges';

type LoadState = {
  server: Server | null;
  system: HostSystem | null;
  network: HostNetwork | null;
  docker: HostDocker | null;
  metrics: ServerMetrics | null;
  prometheus: PrometheusHealth | null;
  deployments: Deployment[];
  jobs: Job[];
  users: LinuxUser[];
  groups: LinuxGroup[];
  sshKeys: SSHKey[];
};

const initialState: LoadState = {
  server: null,
  system: null,
  network: null,
  docker: null,
  metrics: null,
  prometheus: null,
  deployments: [],
  jobs: [],
  users: [],
  groups: [],
  sshKeys: [],
};

export function HostDetailPage() {
  const { id } = useParams();
  const [state, setState] = useState<LoadState>(initialState);
  const [errors, setErrors] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    setErrors([]);

    const serverResult = await settle(() => getServer(id));
    if (!serverResult.ok) {
      setErrors([serverResult.error]);
      setIsLoading(false);
      return;
    }

    const [system, network, docker, metrics, prometheus, deployments, jobs, users, groups, sshKeys] =
      await Promise.all([
        settle(() => getServerSystem(id)),
        settle(() => getServerNetwork(id)),
        settle(() => getServerDocker(id)),
        settle(() => getServerMetrics(id)),
        settle(() => getPrometheusHealth()),
        settle(() => listDeployments()),
        settle(() => listJobs()),
        settle(() => listLinuxUsers()),
        settle(() => listLinuxGroups()),
        settle(() => listSSHKeys()),
      ]);

    setState({
      server: serverResult.value,
      system: system.ok ? system.value : null,
      network: network.ok ? network.value : null,
      docker: docker.ok ? docker.value : null,
      metrics: metrics.ok ? metrics.value : null,
      prometheus: prometheus.ok ? prometheus.value : null,
      deployments: deployments.ok ? deployments.value.filter((item) => item.target_server_id === id) : [],
      jobs: jobs.ok ? jobs.value.filter((job) => job.target_server_id === id).slice(0, 8) : [],
      users: users.ok ? users.value : [],
      groups: groups.ok ? groups.value : [],
      sshKeys: sshKeys.ok ? sshKeys.value : [],
    });
    setErrors(
      [system, network, docker, metrics, prometheus, deployments, jobs, users, groups, sshKeys]
        .filter((result) => !result.ok)
        .map((result) => (result.ok ? '' : result.error)),
    );
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exporterState = useMemo(() => detectExporters(state), [state]);

  if (isLoading && !state.server) {
    return <div className="h-80 animate-pulse rounded-lg bg-zinc-100" />;
  }

  if (!state.server) {
    return <ErrorPanel title="Host could not be loaded" errors={errors} onRetry={refresh} />;
  }

  const server = state.server;

  return (
    <div className="space-y-6">
      <PageHeader
        title={server.hostname}
        description="Inventory, provider, system, network, deployment, identity, and monitoring context for this host."
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <EnvironmentBadge environment={server.environment} />
          <LifecycleBadge state={server.lifecycle_state} />
          <SyncBadge status={server.sync_status} />
          <HealthBadge status={server.last_health_status} />
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
          type="button"
          onClick={() => void refresh()}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      {errors.length ? <ErrorPanel title="Some live checks failed" errors={errors} onRetry={refresh} compact /> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ServerIcon} label="LAN IP" value={state.network?.lan_ip ?? server.ip_address} />
        <MetricCard icon={Activity} label="Uptime" value={formatDuration(state.system?.uptime_seconds ?? state.metrics?.uptime_seconds)} />
        <MetricCard icon={HardDrive} label="Memory" value={formatPercent(bytesPercent(state.system?.memory_used_bytes, state.system?.memory_total_bytes) ?? state.metrics?.memory_usage_percent)} />
        <MetricCard icon={Box} label="Containers" value={state.docker ? String(state.docker.containers.length) : 'Unknown'} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Panel title="System Overview">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Info label="OS" value={state.system?.operating_system ?? server.operating_system} />
              <Info label="Kernel" value={state.system?.kernel ?? 'Unknown'} />
              <Info label="CPU" value={state.system?.cpu_model ?? 'Unknown'} />
              <Info label="Cores" value={state.system?.cpu_cores ? String(state.system.cpu_cores) : 'Unknown'} />
              <Info label="Load" value={state.system?.load_average.join(' / ') || 'Unknown'} />
              <Info label="Provider" value={`${server.provider}${server.provider_node ? ` / ${server.provider_node}` : ''}`} />
            </dl>
          </Panel>

          <Panel title="Filesystems">
            <div className="grid gap-3 md:grid-cols-2">
              {(state.system?.filesystems ?? []).map((fs) => (
                <div key={`${fs.filesystem}-${fs.mountpoint}`} className="rounded-md border border-zinc-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-sm font-semibold text-zinc-950">{fs.mountpoint}</span>
                    <span className="text-xs text-zinc-500">{fs.type}</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-zinc-100">
                    <div className="h-2 rounded-full bg-zinc-900" style={{ width: `${bytesPercent(fs.used_bytes, fs.size_bytes) ?? 0}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">{formatBytes(fs.used_bytes)} / {formatBytes(fs.size_bytes)}</p>
                </div>
              ))}
              {state.system?.filesystems.length === 0 ? <EmptyText text="No filesystem data collected." /> : null}
            </div>
          </Panel>

          <Panel title="Network">
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Interfaces</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.interfaces ?? []).map((item) => (
                    <div key={item.name} className="rounded-md border border-zinc-200 p-3">
                      <div className="font-mono text-sm font-semibold">{item.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.addresses.map((address) => (
                          <span key={address} className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700">{address}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                  {state.network?.interfaces.length === 0 ? <EmptyText text="No interfaces discovered." /> : null}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Listening Services</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.listening_ports ?? []).map((port) => (
                    <div key={`${port.protocol}-${port.address}-${port.port}`} className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 p-3">
                      <div>
                        <div className="font-mono text-sm font-semibold">{port.port}/{port.protocol}</div>
                        <div className="text-xs text-zinc-500">{port.process ?? port.service ?? 'unknown process'}</div>
                      </div>
                      {serviceUrl(server.ip_address, port) ? (
                        <a className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-950" href={serviceUrl(server.ip_address, port) ?? undefined} target="_blank" rel="noreferrer">
                          Open <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      ) : null}
                    </div>
                  ))}
                  {state.network?.listening_ports.length === 0 ? <EmptyText text="No listening ports discovered." /> : null}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Docker Runtime">
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge tone={state.docker?.installed ? 'success' : 'muted'}>{state.docker?.installed ? `Docker ${state.docker.version}` : 'Docker not detected'}</Badge>
              <Badge tone="muted">Restart quick actions planned</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200 text-sm">
                <thead className="bg-zinc-50">
                  <tr>{['Container', 'Image', 'Status', 'Ports', 'Compose'].map((heading) => <th key={heading} className="px-3 py-2 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {(state.docker?.containers ?? []).map((container) => (
                    <tr key={container.container_id}>
                      <td className="px-3 py-2 font-semibold">{container.name}</td>
                      <td className="px-3 py-2 font-mono text-xs">{container.image}</td>
                      <td className="px-3 py-2"><Badge tone={container.status.toLowerCase().includes('up') ? 'success' : 'muted'}>{container.status}</Badge></td>
                      <td className="px-3 py-2 font-mono text-xs">{container.ports || '-'}</td>
                      <td className="px-3 py-2">{container.compose_project ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {state.docker?.containers.length === 0 ? <EmptyText text="No running containers discovered." /> : null}
            </div>
          </Panel>
        </div>

        <aside className="space-y-6">
          <Panel title="Monitoring">
            <div className="space-y-2">
              <Badge tone={state.prometheus?.reachable ? 'success' : 'warning'}>{state.prometheus?.reachable ? 'Prometheus reachable' : 'Prometheus unavailable'}</Badge>
              <Badge tone={exporterState.node ? 'success' : 'muted'}>node_exporter {exporterState.node ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.promtail ? 'success' : 'muted'}>promtail {exporterState.promtail ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.cadvisor ? 'success' : 'muted'}>cadvisor {exporterState.cadvisor ? 'detected' : 'not detected'}</Badge>
            </div>
            {state.metrics?.grafana_url ? (
              <a className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-zinc-800 hover:text-zinc-950" href={state.metrics.grafana_url} target="_blank" rel="noreferrer">
                Open Grafana <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : null}
          </Panel>

          <Panel title="Related Resources">
            <LinkList items={[
              { label: `${state.deployments.length} deployments`, to: '/deployments' },
              { label: `${state.jobs.length} recent jobs`, to: '/jobs' },
              { label: `${state.users.length} users / ${state.groups.length} groups`, to: '/identity' },
              { label: `${state.sshKeys.length} SSH keys`, to: '/identity' },
            ]} />
          </Panel>

          <Panel title="Quick Actions">
            <LinkList items={[
              { label: 'Run command', to: '/jobs' },
              { label: 'Apply profile', to: '/profiles' },
              { label: 'Deploy compose app', to: '/deployments' },
              { label: 'View monitoring', to: '/monitoring' },
            ]} />
          </Panel>

          <Panel title="Identity Scope">
            <div className="flex items-center gap-3 text-sm text-zinc-600">
              <ShieldCheck className="h-5 w-5 text-zinc-500" aria-hidden="true" />
              Linux identity orchestration is available through Jobs-backed replication.
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

async function settle<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: string }> {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error: getApiErrorMessage(error) };
  }
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof ServerIcon; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
      <div className="mt-3 text-sm text-zinc-500">{label}</div>
      <div className="mt-1 break-words text-xl font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-zinc-900">{value}</dd>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: 'success' | 'warning' | 'muted' }) {
  const className = {
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    muted: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  }[tone];
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>{children}</span>;
}

function EmptyText({ text }: { text: string }) {
  return <p className="py-3 text-sm text-zinc-500">{text}</p>;
}

function LinkList({ items }: { items: Array<{ label: string; to: string }> }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <Link key={item.label} className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" to={item.to}>
          {item.label}
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </Link>
      ))}
    </div>
  );
}

function ErrorPanel({ title, errors, onRetry, compact = false }: { title: string; errors: string[]; onRetry: () => void; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-amber-200 bg-amber-50 text-amber-900 ${compact ? 'p-3' : 'p-5'}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </div>
        <button className="rounded-md bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800" type="button" onClick={onRetry}>Retry</button>
      </div>
    </div>
  );
}

function formatBytes(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let next = value;
  let index = 0;
  while (next >= 1024 && index < units.length - 1) {
    next /= 1024;
    index += 1;
  }
  return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function bytesPercent(used: number | null | undefined, total: number | null | undefined): number | null {
  if (!used || !total) {
    return null;
  }
  return Math.round((used / total) * 100);
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? 'Unknown' : `${Math.round(value)}%`;
}

function formatDuration(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  return days ? `${days}d ${hours}h` : `${hours}h`;
}

function serviceUrl(host: string, port: { port: number; service: string | null; protocol: string }): string | null {
  if (port.service === 'http' || port.port === 80) {
    return `http://${host}`;
  }
  if (port.service === 'https' || port.port === 443) {
    return `https://${host}`;
  }
  if ([3000, 8000, 9090].includes(port.port)) {
    return `http://${host}:${port.port}`;
  }
  return null;
}

function detectExporters(state: LoadState) {
  const processes = (state.network?.listening_ports ?? []).map((port) => `${port.process ?? ''} ${port.port}`).join(' ').toLowerCase();
  const containers = (state.docker?.containers ?? []).map((container) => `${container.name} ${container.image}`).join(' ').toLowerCase();
  return {
    node: processes.includes('9100') || containers.includes('node-exporter') || containers.includes('node_exporter'),
    promtail: containers.includes('promtail') || processes.includes('promtail'),
    cadvisor: containers.includes('cadvisor') || processes.includes('8080'),
  };
}
