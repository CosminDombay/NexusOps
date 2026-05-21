import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Activity, Box, ExternalLink, HardDrive, Loader2, Play, Power, RefreshCw, RotateCw, ServerIcon, ShieldCheck, TerminalSquare } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listAutomations } from '../../automations/api/automationsApi';
import type { Automation } from '../../automations/types/automation';
import { useAuth } from '../../auth/hooks/useAuth';
import { listDeployments } from '../../deployments/api/deploymentsApi';
import type { Deployment } from '../../deployments/types/deployment';
import { listLinuxGroups, listLinuxUsers, listSSHKeys } from '../../identity/api/identityApi';
import type { LinuxGroup, LinuxUser, SSHKey } from '../../identity/types/identity';
import { listJobs } from '../../jobs/api/jobsApi';
import type { Job } from '../../jobs/types/job';
import { getServerMetrics, getPrometheusHealth } from '../../monitoring/api/monitoringApi';
import type { PrometheusHealth, ServerMetrics } from '../../monitoring/types/monitoring';
import { runVmAction } from '../../proxmox/api/proxmoxApi';
import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import { FileBrowserPanel } from '../../remote-access/components/FileBrowserPanel';
import { ShellPanel } from '../../remote-access/components/ShellPanel';
import { RuntimeStateBadge } from '../../runtime-state/components/RuntimeStateBadge';
import { canRunLifecycleAction } from '../../runtime-state/utils/eligibility';
import { listWorkflows } from '../../workflows/api/workflowsApi';
import type { WorkflowRun } from '../../workflows/types/workflow';
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
  workflows: WorkflowRun[];
  automations: Automation[];
  users: LinuxUser[];
  groups: LinuxGroup[];
  sshKeys: SSHKey[];
};

type HostTab = 'overview' | 'management' | 'metrics' | 'terminal' | 'files' | 'deployments' | 'jobs' | 'workflows' | 'packages' | 'profiles' | 'identity';

const initialState: LoadState = {
  server: null,
  system: null,
  network: null,
  docker: null,
  metrics: null,
  prometheus: null,
  deployments: [],
  jobs: [],
  workflows: [],
  automations: [],
  users: [],
  groups: [],
  sshKeys: [],
};

export function HostDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [state, setState] = useState<LoadState>(initialState);
  const [errors, setErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [activeVmAction, setActiveVmAction] = useState<ProxmoxVmAction | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<HostTab>('overview');
  const allowManagement = user?.role === 'admin' || user?.role === 'operator';

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

    const [system, network, docker, metrics, prometheus, deployments, jobs, workflows, automations, users, groups, sshKeys] =
      await Promise.all([
        settle(() => getServerSystem(id)),
        settle(() => getServerNetwork(id)),
        settle(() => getServerDocker(id)),
        settle(() => getServerMetrics(id)),
        settle(() => getPrometheusHealth()),
        settle(() => listDeployments()),
        settle(() => listJobs()),
        settle(() => listWorkflows()),
        settle(() => listAutomations()),
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
      deployments: deployments.ok ? deployments.value.filter((item) => deploymentTouchesServer(item, id)) : [],
      jobs: jobs.ok ? jobs.value.filter((job) => job.target_server_id === id).slice(0, 8) : [],
      workflows: workflows.ok ? workflows.value.filter((workflow) => workflowTouchesServer(workflow, id)).slice(0, 8) : [],
      automations: automations.ok ? automations.value.filter((automation) => automation.target_server_ids.includes(id)).slice(0, 8) : [],
      users: users.ok ? users.value : [],
      groups: groups.ok ? groups.value : [],
      sshKeys: sshKeys.ok ? sshKeys.value : [],
    });
    setErrors(
      [system, network, docker, metrics, prometheus, deployments, jobs, workflows, automations, users, groups, sshKeys]
        .filter((result) => !result.ok)
        .map((result) => (result.ok ? '' : result.error)),
    );
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exporterState = useMemo(() => detectExporters(state), [state]);

  async function handleVmLifecycle(action: ProxmoxVmAction) {
    const server = state.server;
    const vmId = getProviderVmId(server);
    if (!server || vmId === null) {
      setNotice({ tone: 'error', message: 'This inventory host is not linked to a Proxmox VMID.' });
      return;
    }

    if (action !== 'start') {
      const confirmed = window.confirm(`${actionLabel(action)} ${server.node_type === 'lxc' ? 'LXC' : 'VM'} ${server.hostname} (${vmId})?`);
      if (!confirmed) {
        return;
      }
    }

    setActiveVmAction(action);
    setNotice(null);
    try {
      const response = await runVmAction(vmId, action);
      setNotice({ tone: 'success', message: response.message });
      await refresh();
    } catch (caughtError) {
      setNotice({ tone: 'error', message: getApiErrorMessage(caughtError) });
    } finally {
      setActiveVmAction(null);
    }
  }

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
        description="Unified operations for this managed node across inventory, provider, monitoring, remote access, jobs, deployments, and identity."
      />

      {notice ? <HostNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <EnvironmentBadge environment={server.environment} />
          <LifecycleBadge state={server.lifecycle_state} />
          <SyncBadge status={server.sync_status} />
          <HealthBadge status={server.last_health_status} />
          <RuntimeStateBadge runtimeState={server.runtime_state} />
          <ReadinessBadge readiness={nodeReadiness(server, state)} />
          <NodeTypePill nodeType={server.node_type} />
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
          type="button"
          onClick={() => void refresh()}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
        <Link
          className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
          to={`/inventory/${server.id}/tools`}
        >
          <TerminalSquare className="h-4 w-4" aria-hidden="true" />
          Host Tools
        </Link>
      </div>

      {errors.length ? <ErrorPanel title="Some live checks failed" errors={errors} onRetry={refresh} compact /> : null}

      <nav className="flex gap-2 overflow-x-auto rounded-lg border border-zinc-200 bg-white p-2 shadow-sm">
        {hostTabs.map((tab) => (
          <button
            key={tab.id}
            className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold ${
              activeTab === tab.id ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950'
            }`}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab !== 'overview' ? (
        <HostTabPanel
          activeVmAction={activeVmAction}
          allowManagement={allowManagement}
          canUseRemoteAccess={allowManagement && Boolean(server.runtime_state?.eligibility.can_open_shell ?? true)}
          server={server}
          state={state}
          tab={activeTab}
          onVmLifecycle={(action) => void handleVmLifecycle(action)}
        />
      ) : null}

      {activeTab === 'overview' ? (
        <>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ServerIcon} label="LAN IP" value={state.network?.lan_ip ?? server.ip_address} />
        <MetricCard icon={Activity} label="Uptime" value={formatDuration(state.system?.uptime_seconds ?? state.metrics?.uptime_seconds)} />
        <MetricCard icon={HardDrive} label="Memory" value={formatPercent(bytesPercent(state.system?.memory_used_bytes, state.system?.memory_total_bytes) ?? state.metrics?.memory_usage_percent)} />
        <MetricCard icon={Box} label="Readiness" value={formatReadiness(nodeReadiness(server, state))} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Panel title="System Overview">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Info label="Node type" value={formatNodeType(server.node_type)} />
              <Info label="OS" value={state.system?.operating_system ?? server.operating_system} />
              <Info label="Kernel" value={state.system?.kernel ?? 'Unknown'} />
              <Info label="CPU" value={state.system?.cpu_model ?? 'Unknown'} />
              <Info label="Cores" value={state.system?.cpu_cores ? String(state.system.cpu_cores) : 'Unknown'} />
              <Info label="Load" value={state.system?.load_average.join(' / ') || 'Unknown'} />
              <Info label="Provider" value={`${server.provider}${server.provider_node ? ` / ${server.provider_node}` : ''}`} />
              <Info label="Lifecycle" value={server.lifecycle_state} />
              <Info label="Operational state" value={nodeReadiness(server, state)} />
              <Info label="SSH readiness" value={server.runtime_state?.ssh_state ?? sshReadiness(server, state)} />
              <Info label="Monitoring state" value={server.runtime_state?.monitoring_state ?? monitoringReadiness(state)} />
              <Info label="Provider state" value={server.runtime_state?.provider_state ?? 'unknown'} />
            </dl>
          </Panel>

          <Panel title="Provider Metadata">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Provider" value={server.provider} />
              <Info label="Provider type" value={server.provider_type ?? 'Unknown'} />
              <Info label="Provider node" value={server.provider_node ?? 'Unknown'} />
              <Info label="External ID" value={server.external_id ?? server.vmid ?? 'Unknown'} />
            </div>
            <MetadataBlock metadata={server.provider_metadata} />
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
              <Badge tone={state.metrics?.monitoring_state === 'monitoring_ready' ? 'success' : 'warning'}>
                {formatReadiness(state.metrics?.monitoring_state ?? monitoringReadiness(state))}
              </Badge>
              <Badge tone={state.metrics?.metrics_available ? 'success' : 'warning'}>metrics {state.metrics?.metrics_available ? 'available' : 'missing'}</Badge>
              <Badge tone={state.metrics?.logs_available ? 'success' : 'warning'}>logs {state.metrics?.logs_available ? 'available' : 'missing'}</Badge>
              <Badge tone={state.prometheus?.reachable ? 'success' : 'warning'}>{state.prometheus?.reachable ? 'Prometheus reachable' : 'Prometheus unavailable'}</Badge>
              <Badge tone={exporterState.node ? 'success' : 'muted'}>node_exporter {exporterState.node ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.promtail ? 'success' : 'muted'}>promtail {exporterState.promtail ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.cadvisor ? 'success' : 'muted'}>cadvisor {exporterState.cadvisor ? 'detected' : 'not detected'}</Badge>
              {state.metrics?.stale_metrics ? <Badge tone="warning">stale metrics</Badge> : null}
            </div>
            {state.metrics?.grafana_url ? (
              <a className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-zinc-800 hover:text-zinc-950" href={state.metrics.grafana_url} target="_blank" rel="noreferrer">
                Open advanced metrics <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : null}
          </Panel>

          <Panel title="Related Resources">
            <LinkList items={[
              { label: `${state.deployments.length} deployments`, to: '/deployments' },
              { label: `${state.jobs.length} recent jobs`, to: '/jobs' },
              { label: `${state.workflows.length} recent workflows`, to: '/workflows' },
              { label: `${state.automations.length} automations targeting node`, to: '/automations' },
              { label: `${state.users.length} users / ${state.groups.length} groups`, to: '/identity' },
              { label: `${state.sshKeys.length} SSH keys`, to: '/identity' },
            ]} />
          </Panel>

          <Panel title="Quick Actions">
            <LinkList items={[
              { label: 'Open dedicated host tools', to: `/inventory/${server.id}/tools` },
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
        </>
      ) : null}
    </div>
  );
}

const hostTabs: Array<{ id: HostTab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'management', label: 'Management' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'terminal', label: 'Terminal' },
  { id: 'files', label: 'Files' },
  { id: 'deployments', label: 'Deployments' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'workflows', label: 'Workflows' },
  { id: 'packages', label: 'Packages' },
  { id: 'profiles', label: 'Profiles' },
  { id: 'identity', label: 'Identity' },
];

function HostTabPanel({
  activeVmAction,
  allowManagement,
  canUseRemoteAccess,
  tab,
  server,
  state,
  onVmLifecycle,
}: {
  activeVmAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  canUseRemoteAccess: boolean;
  tab: HostTab;
  server: Server;
  state: LoadState;
  onVmLifecycle: (action: ProxmoxVmAction) => void;
}) {
  if (tab === 'management') {
    return (
      <Panel title="VM management">
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <Info label="Provider" value={server.provider} />
            <Info label="Node" value={server.provider_node ?? 'Unknown'} />
            <Info label="VMID" value={String(getProviderVmId(server) ?? 'Not linked')} />
          </div>
          <VmLifecycleActions
            activeAction={activeVmAction}
            allowManagement={allowManagement}
            server={server}
            onAction={onVmLifecycle}
          />
          {!allowManagement ? <p className="text-sm text-zinc-500">Operator or admin role required for VM lifecycle actions.</p> : null}
        </div>
      </Panel>
    );
  }

  if (tab === 'terminal') {
    return (
      <div className="min-h-[520px]">
        <ShellPanel server={server} canUseShell={canUseRemoteAccess} compact />
      </div>
    );
  }

  if (tab === 'files') {
    return (
      <FileBrowserPanel server={server} canUseFiles={canUseRemoteAccess} />
    );
  }

  if (tab === 'deployments') {
    return (
      <Panel title="Host deployments">
        <LinkList items={[
          ...state.deployments.map((deployment) => ({ label: `${deployment.name} - ${deployment.status}`, to: '/deployments' })),
          { label: 'Create deployment for this host', to: '/deployments' },
        ]} />
      </Panel>
    );
  }

  if (tab === 'jobs') {
    return (
      <Panel title="Recent jobs">
        <LinkList items={[
          ...state.jobs.map((job) => ({ label: `${job.operation_type} - ${job.status}`, to: '/jobs' })),
          { label: 'Run command for this host', to: '/jobs' },
        ]} />
      </Panel>
    );
  }

  if (tab === 'workflows') {
    return (
      <Panel title="Recent workflow executions">
        <LinkList items={[
          ...state.workflows.map((workflow) => ({
            label: `${formatReadiness(workflow.workflow_type)} - ${workflow.status} - ${workflowProgress(workflow)}`,
            to: '/workflows',
          })),
          ...state.automations.map((automation) => ({
            label: `${automation.name} automation - ${automation.runtime_state}`,
            to: '/automations',
          })),
          { label: 'Open workflow history', to: '/workflows' },
        ]} />
      </Panel>
    );
  }

  if (tab === 'metrics') {
    return (
      <Panel title="Metrics">
        <div className="grid gap-3 md:grid-cols-3">
          <Info label="Uptime" value={formatDuration(state.metrics?.uptime_seconds)} />
          <Info label="CPU" value={formatPercent(state.metrics?.cpu_usage_percent)} />
          <Info label="Memory" value={formatPercent(state.metrics?.memory_usage_percent)} />
        </div>
      </Panel>
    );
  }

  if (tab === 'overview') {
    return null;
  }

  const links: Record<'packages' | 'profiles' | 'identity', Array<{ label: string; to: string }>> = {
    packages: [{ label: 'Run package against this host', to: '/packages' }],
    profiles: [{ label: 'Apply profile to this host', to: '/profiles' }],
    identity: [{ label: `${state.users.length} users / ${state.groups.length} groups`, to: '/identity' }],
  };

  return (
    <Panel title={hostTabs.find((item) => item.id === tab)?.label ?? 'Host operations'}>
      <LinkList items={links[tab]} />
    </Panel>
  );
}

function HostNotice({
  message,
  tone,
  onDismiss,
}: {
  message: string;
  tone: 'success' | 'error';
  onDismiss: () => void;
}) {
  const className =
    tone === 'success'
      ? 'border-emerald-400/30 bg-emerald-950/40 text-emerald-100'
      : 'border-rose-400/30 bg-rose-950/50 text-rose-100';
  return (
    <div className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${className}`}>
      <p className="text-sm font-medium">{message}</p>
      <button className="text-sm font-semibold underline-offset-2 hover:underline" type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function ReadinessBadge({ readiness }: { readiness: string }) {
  const tone =
    readiness === 'healthy' || readiness === 'booted'
      ? 'success'
      : readiness === 'degraded' ||
          readiness === 'ssh_unreachable' ||
          readiness === 'network_missing' ||
          readiness === 'monitoring_missing' ||
          readiness === 'partially_managed'
        ? 'warning'
        : 'muted';
  return <Badge tone={tone}>{formatReadiness(readiness)}</Badge>;
}

function NodeTypePill({ nodeType }: { nodeType: Server['node_type'] }) {
  const className =
    nodeType === 'hypervisor'
      ? 'bg-violet-50 text-violet-700 ring-violet-200'
      : nodeType === 'lxc'
        ? 'bg-cyan-50 text-cyan-700 ring-cyan-200'
        : nodeType === 'vm'
          ? 'bg-indigo-50 text-indigo-700 ring-indigo-200'
          : 'bg-zinc-100 text-zinc-700 ring-zinc-200';
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {formatNodeType(nodeType)}
    </span>
  );
}

function MetadataBlock({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!entries.length) {
    return <EmptyText text="No provider metadata recorded." />;
  }
  return (
    <dl className="mt-4 grid gap-3 md:grid-cols-2">
      {entries.slice(0, 12).map(([key, value]) => (
        <Info key={key} label={key.replace(/_/g, ' ')} value={metadataValue(value)} />
      ))}
    </dl>
  );
}

function VmLifecycleActions({
  activeAction,
  allowManagement,
  server,
  onAction,
}: {
  activeAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  server: Server;
  onAction: (action: ProxmoxVmAction) => void;
}) {
  const vmId = getProviderVmId(server);
  const isBusy = activeAction !== null;
  const isLinkedProxmoxVm = server.provider === 'proxmox' && vmId !== null;
  const commonDisabled = !allowManagement || !isLinkedProxmoxVm || isBusy;
  const canStart = canRunLifecycleAction(server.runtime_state, 'start') || (!server.runtime_state && isLinkedProxmoxVm);
  const canStop = canRunLifecycleAction(server.runtime_state, 'stop') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));
  const canReboot = canRunLifecycleAction(server.runtime_state, 'reboot') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));

  return (
    <div className="flex flex-wrap gap-2">
      <LifecycleButton
        action="start"
        disabled={commonDisabled || !canStart}
        icon={Play}
        isLoading={activeAction === 'start'}
        label="Start"
        tone="primary"
        onClick={() => onAction('start')}
      />
      <LifecycleButton
        action="shutdown"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'shutdown'}
        label="Shutdown"
        onClick={() => onAction('shutdown')}
      />
      <LifecycleButton
        action="reboot"
        disabled={commonDisabled || !canReboot}
        icon={RotateCw}
        isLoading={activeAction === 'reboot'}
        label="Reboot"
        onClick={() => onAction('reboot')}
      />
      <LifecycleButton
        action="stop"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'stop'}
        label="Stop"
        tone="danger"
        onClick={() => onAction('stop')}
      />
    </div>
  );
}

function LifecycleButton({
  disabled,
  icon: Icon,
  isLoading,
  label,
  onClick,
  tone = 'secondary',
}: {
  action: ProxmoxVmAction;
  disabled: boolean;
  icon: typeof Play;
  isLoading: boolean;
  label: string;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
}) {
  const className =
    tone === 'primary'
      ? 'border-cyan-400 bg-cyan-400 text-zinc-950 hover:bg-cyan-300 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : tone === 'danger'
        ? 'border-rose-400/50 bg-white text-rose-700 hover:bg-rose-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
        : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400';
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${className}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
      {label}
    </button>
  );
}

function getProviderVmId(server: Server | null): number | null {
  const raw = server?.vmid ?? server?.external_id ?? null;
  if (!raw) {
    return null;
  }
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function actionLabel(action: ProxmoxVmAction): string {
  return action.charAt(0).toUpperCase() + action.slice(1);
}

async function settle<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: string }> {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error: getApiErrorMessage(error) };
  }
}

function workflowTouchesServer(workflow: WorkflowRun, serverId: string): boolean {
  if (workflow.target_server_id === serverId) {
    return true;
  }
  return workflow.steps.some((step) => step.metadata_json.target_server_id === serverId);
}

function deploymentTouchesServer(deployment: Deployment, serverId: string): boolean {
  return deployment.target_server_id === serverId || (deployment.target_server_ids ?? []).includes(serverId);
}

function workflowProgress(workflow: WorkflowRun): string {
  if (!workflow.steps.length) {
    return 'no steps';
  }
  const failed = workflow.failed_steps ? `, ${workflow.failed_steps} failed` : '';
  return `${workflow.completed_steps}/${workflow.steps.length} completed${failed}`;
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

function nodeReadiness(server: Server, state: LoadState): string {
  if (server.runtime_state) {
    if (server.runtime_state.degraded_reasons.length) {
      return 'degraded';
    }
    return server.runtime_state.orchestration_state;
  }
  const metadataReadiness = String(server.provider_metadata.operational_readiness ?? '').trim();
  if (metadataReadiness) {
    if (!state.prometheus?.reachable && metadataReadiness === 'booted') {
      return 'monitoring_missing';
    }
    return metadataReadiness;
  }
  if (server.lifecycle_state === 'archived' || server.lifecycle_state === 'decommissioned') {
    return server.lifecycle_state;
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (state.system || state.network) {
    return state.prometheus?.reachable === false ? 'monitoring_missing' : 'healthy';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  if (server.last_health_status === 'sync_error') {
    return 'degraded';
  }
  return server.managed ? 'partially_managed' : 'discovered';
}

function sshReadiness(server: Server, state: LoadState): string {
  if (state.system || state.network) {
    return 'ready';
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  return server.credential_id || server.ssh_username ? 'not_verified' : 'credential_missing';
}

function monitoringReadiness(state: LoadState): string {
  if (!state.prometheus) {
    return 'unknown';
  }
  return state.prometheus.reachable ? 'prometheus_reachable' : 'monitoring_missing';
}

function formatReadiness(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'Unknown';
}

function formatNodeType(value: Server['node_type']): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function metadataValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => metadataValue(item)).join(', ') : 'None';
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
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
