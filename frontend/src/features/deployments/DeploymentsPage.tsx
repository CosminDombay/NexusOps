import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Eye,
  FileText,
  KeyRound,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCw,
  Server,
  Square,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, CollapsibleSection } from '../../components/operations/OperationalComponents';
import { OperationalTimeline } from '../../components/operations/OperationalTimeline';
import { formatDurationSeconds, formatOperationalLabel } from '../../components/operations/runtimeFormat';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server as InventoryServer } from '../inventory/types/server';
import { selectedTargetIds } from '../inventory/types/targetSelection';
import type { Job } from '../jobs/types/job';
import {
  createDeployment,
  deleteDeployment,
  dryRunDeployment,
  getDeploymentLogs,
  getDeploymentStatus,
  listDeployments,
  refreshDeploymentRuntime,
  runDeploymentOperation,
  updateDeployment,
  validateDeploymentPayload,
} from './api/deploymentsApi';
import type { CreateDeploymentPayload, Deployment, DeploymentDryRun, DeploymentStatus } from './types/deployment';

const defaultCompose = `services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`;

const defaultRemotePath = '/opt/nexusops/deployments';
const statusFilters: Array<DeploymentStatus | 'all'> = [
  'all',
  'running',
  'deploying',
  'partial_success',
  'degraded',
  'stopped',
  'failed',
  'draft',
];
const autoRefreshIntervalMs = 30_000;

type DrawerMode = 'create' | 'edit' | null;
type DeploymentOperationName = 'deploy' | 'redeploy' | 'restart' | 'stop';

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [servers, setServers] = useState<InventoryServer[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('');
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [statusFilter, setStatusFilter] = useState<DeploymentStatus | 'all'>('all');
  const [name, setName] = useState('nginx-demo');
  const [targetServerId, setTargetServerId] = useState('');
  const targetSelector = useTargetSelection('single');
  const [composeContent, setComposeContent] = useState(defaultCompose);
  const [envContent, setEnvContent] = useState('');
  const [remotePath, setRemotePath] = useState(defaultRemotePath);
  const [executionCredentialId, setExecutionCredentialId] = useState('');
  const [credentialRefs, setCredentialRefs] = useState<
    Array<{ key: string; credentialId: string }>
  >([]);
  const [logs, setLogs] = useState('');
  const [inspectOutput, setInspectOutput] = useState('');
  const [dryRunPreview, setDryRunPreview] = useState<DeploymentDryRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingDeploymentId, setEditingDeploymentId] = useState<string | null>(null);

  const selectedDeployment =
    deployments.find((deployment) => deployment.id === selectedDeploymentId) ??
    deployments[0] ??
    null;
  const filteredDeployments = useMemo(
    () =>
      deployments.filter(
        (deployment) =>
          statusFilter === 'all' || normalizeStatus(deployment.status) === statusFilter,
      ),
    [deployments, statusFilter],
  );

  const refreshDeploymentList = useCallback(async () => {
    try {
      const nextDeployments = await listDeployments();
      setDeployments(nextDeployments);
      setSelectedDeploymentId((current) => current || nextDeployments[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }, []);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDeployments, nextServers, nextCredentials] = await Promise.all([
        listDeployments(),
        listServers(),
        listCredentials(),
      ]);
      setDeployments(nextDeployments);
      setServers(nextServers);
      setCredentials(nextCredentials);
      setTargetServerId((current) => current || nextServers[0]?.id || '');
      setSelectedDeploymentId((current) => current || nextDeployments[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  function deploymentPayload(targets: string[]): CreateDeploymentPayload {
    return {
      name: name.trim(),
      target_server_id: targets[0],
      target_server_ids: targets,
      compose_content: composeContent,
      env_content: envContent || null,
      remote_path: remotePath.trim(),
      execution_credential_ref: executionCredentialId || null,
      credential_refs: Object.fromEntries(
        credentialRefs
          .filter((item) => item.key.trim() && item.credentialId)
          .map((item) => [item.key.trim(), item.credentialId]),
      ),
    };
  }

  function resetForm() {
    setEditingDeploymentId(null);
    setName('nginx-demo');
    setComposeContent(defaultCompose);
    setEnvContent('');
    setRemotePath(defaultRemotePath);
    setExecutionCredentialId('');
    setCredentialRefs([]);
    setDryRunPreview(null);
    targetSelector.setMode('single');
    targetSelector.setSelectedId(targetServerId);
    targetSelector.setSelectedIds([]);
  }

  function openCreateDrawer() {
    resetForm();
    setDrawerMode('create');
  }

  function openEditDrawer(deployment: Deployment) {
    setEditingDeploymentId(deployment.id);
    setSelectedDeploymentId(deployment.id);
    setName(deployment.name);
    setComposeContent(deployment.compose_content);
    setEnvContent(deployment.env_content ?? '');
    setRemotePath(deployment.remote_path ?? defaultRemotePath);
    setExecutionCredentialId(deployment.execution_credential_ref ?? '');
    setCredentialRefs(
      Object.entries(deployment.credential_refs ?? {}).map(([key, credentialId]) => ({
        key,
        credentialId,
      })),
    );
    targetSelector.setMode((deployment.target_server_ids?.length ?? 0) > 1 ? 'bulk' : 'single');
    targetSelector.setSelectedId(deployment.target_server_id ?? '');
    targetSelector.setSelectedIds(deployment.target_server_ids ?? []);
    setTargetServerId(deployment.target_server_id ?? '');
    setDrawerMode('edit');
    setError(null);
    setDryRunPreview(null);
  }

  async function handleSave() {
    const targets = selectedTargetIds({
      ...targetSelector.selection,
      selectedId: targetSelector.selection.selectedId || targetServerId,
    });
    if (!name.trim() || targets.length === 0 || !composeContent.trim() || !remotePath.trim()) {
      setError('Deployment name, target, compose YAML, and remote path are required.');
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const payload = deploymentPayload(targets);
      if (editingDeploymentId) {
        const deployment = await updateDeployment(editingDeploymentId, payload);
        setDeployments((current) =>
          current.map((item) => (item.id === deployment.id ? deployment : item)),
        );
        setSelectedDeploymentId(deployment.id);
        await refreshDeploymentList();
      } else {
        const deployment = await createDeployment(payload);
        setDeployments((current) => [deployment, ...current]);
        setSelectedDeploymentId(deployment.id);
      }
      setDrawerMode(null);
      resetForm();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function previewCurrentDeployment() {
    const targets = selectedTargetIds({
      ...targetSelector.selection,
      selectedId: targetSelector.selection.selectedId || targetServerId,
    });
    if (!name.trim() || targets.length === 0 || !composeContent.trim() || !remotePath.trim()) {
      setError('Deployment name, target, compose YAML, and remote path are required.');
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      setDryRunPreview(await validateDeploymentPayload(deploymentPayload(targets)));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function run(deployment: Deployment, operation: DeploymentOperationName) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await runDeploymentOperation(deployment.id, operation);
      setDeployments((current) =>
        current.map((item) => (item.id === result.deployment.id ? result.deployment : item)),
      );
      setLogs(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function previewSavedDeployment(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const preview = await dryRunDeployment(deployment.id);
      setInspectOutput(formatDryRunPreview(preview));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function inspect(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentStatus(deployment.id);
      setInspectOutput(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
      const refreshed = await refreshDeploymentRuntime(deployment.id);
      setDeployments((current) =>
        current.map((item) => (item.id === refreshed.id ? refreshed : item)),
      );
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function refreshRuntime(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const refreshed = await refreshDeploymentRuntime(deployment.id);
      setDeployments((current) =>
        current.map((item) => (item.id === refreshed.id ? refreshed : item)),
      );
      setInspectOutput(selectedDeploymentSummary(refreshed));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function loadLogs(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentLogs(deployment.id);
      setLogs(result.logs || formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleDeleteDeployment(deployment: Deployment) {
    const confirmed = window.confirm(
      `Delete deployment ${deployment.name}? This removes the NexusOps record and history only. It does not stop containers or remove files from the server.`,
    );
    if (!confirmed) return;
    setIsWorking(true);
    setError(null);
    try {
      await deleteDeployment(deployment.id);
      const nextDeployments = deployments.filter((item) => item.id !== deployment.id);
      setDeployments(nextDeployments);
      setSelectedDeploymentId(nextDeployments[0]?.id ?? '');
      setLogs('');
      setInspectOutput('');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === 'visible' && !isWorking) {
        void refreshDeploymentList();
      }
    }, autoRefreshIntervalMs);

    return () => window.clearInterval(intervalId);
  }, [isWorking, refreshDeploymentList]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Docker Deployments"
        description="Operational Compose services deployed to inventory-managed Linux hosts."
        actions={
          <>
            <PageActionButton icon={RefreshCw} tone="secondary" onClick={() => void refresh()}>
              Refresh
            </PageActionButton>
            <PageActionButton icon={Plus} onClick={openCreateDrawer}>
              Create deployment
            </PageActionButton>
          </>
        }
      />

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Services" value={deployments.length} />
          <Metric
            label="Running"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'running').length}
          />
          <Metric
            label="Failed"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'failed').length}
          />
          <Metric
            label="Drift"
            value={deployments.filter((item) => item.sync_status !== 'synced').length}
          />
        </div>
      </section>

      <section className="flex flex-wrap gap-2">
        {statusFilters.map((status) => (
          <button
            key={status}
            className={`rounded-md px-3 py-2 text-sm font-semibold ${statusFilter === status ? 'bg-zinc-950 text-white' : 'border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'}`}
            type="button"
            onClick={() => setStatusFilter(status)}
          >
            {status === 'all' ? 'All' : statusLabel(status)}
          </button>
        ))}
      </section>

      {isLoading ? (
        <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-500">
          Loading deployments...
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-3">
        {filteredDeployments.map((deployment) => (
          <DeploymentCard
            key={deployment.id}
            deployment={deployment}
            selected={deployment.id === selectedDeployment?.id}
            isWorking={isWorking}
            onSelect={() => setSelectedDeploymentId(deployment.id)}
            onRun={run}
            onInspect={inspect}
            onRefreshRuntime={refreshRuntime}
            onLogs={loadLogs}
            onPreview={previewSavedDeployment}
            onEdit={openEditDrawer}
            onDelete={handleDeleteDeployment}
          />
        ))}
        {!filteredDeployments.length && !isLoading ? (
          <div className="rounded-md border border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500 xl:col-span-3">
            No deployments match this view.
          </div>
        ) : null}
      </section>

      <CollapsibleSection
        title="Runtime output"
        description="Inspect and logs output are available on demand so the deployment list stays scannable."
      >
        <section className="grid gap-4 xl:grid-cols-2">
        <OutputPanel
          title="Inspect"
          value={inspectOutput || selectedDeploymentSummary(selectedDeployment)}
        />
        <OutputPanel title="Logs" value={logs || 'No logs loaded.'} />
        </section>
      </CollapsibleSection>

      {drawerMode ? (
        <DeploymentDrawer
          mode={drawerMode}
          servers={servers}
          credentials={credentials}
          targetSelector={targetSelector}
          name={name}
          composeContent={composeContent}
          envContent={envContent}
          remotePath={remotePath}
          executionCredentialId={executionCredentialId}
          credentialRefs={credentialRefs}
          dryRunPreview={dryRunPreview}
          isWorking={isWorking}
          onNameChange={setName}
          onComposeChange={setComposeContent}
          onEnvChange={setEnvContent}
          onRemotePathChange={setRemotePath}
          onExecutionCredentialChange={setExecutionCredentialId}
          onCredentialRefsChange={setCredentialRefs}
          onTargetServerIdChange={setTargetServerId}
          onPreview={() => void previewCurrentDeployment()}
          onClose={() => {
            setDrawerMode(null);
            resetForm();
          }}
          onSave={() => void handleSave()}
        />
      ) : null}
    </div>
  );
}

function DeploymentCard({
  deployment,
  selected,
  isWorking,
  onSelect,
  onRun,
  onInspect,
  onRefreshRuntime,
  onLogs,
  onPreview,
  onEdit,
  onDelete,
}: {
  deployment: Deployment;
  selected: boolean;
  isWorking: boolean;
  onSelect: () => void;
  onRun: (deployment: Deployment, operation: DeploymentOperationName) => Promise<void>;
  onInspect: (deployment: Deployment) => Promise<void>;
  onRefreshRuntime: (deployment: Deployment) => Promise<void>;
  onLogs: (deployment: Deployment) => Promise<void>;
  onPreview: (deployment: Deployment) => Promise<void>;
  onEdit: (deployment: Deployment) => void;
  onDelete: (deployment: Deployment) => Promise<void>;
}) {
  return (
    <article
      className={`rounded-md border bg-white p-4 shadow-sm ${selected ? 'border-cyan-400 ring-1 ring-cyan-200' : 'border-zinc-200'}`}
    >
      <button className="w-full text-left" type="button" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-zinc-950">{deployment.name}</h2>
            <p className="mt-1 flex items-center gap-1 text-sm text-zinc-500">
              <Server className="h-4 w-4" aria-hidden="true" />
              {deployment.targets.length > 1 ? (
                <span className="font-semibold text-zinc-700">{deployment.targets.length} targets</span>
              ) : deployment.target_server_id ? (
                <Link
                  className="font-semibold text-zinc-700 hover:text-zinc-950"
                  to={`/inventory/${deployment.target_server_id}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  {deployment.target_hostname ?? 'Open host'}
                </Link>
              ) : (
                'No target'
              )}
            </p>
          </div>
          <RuntimeBadge value={deployment.runtime_state === 'unknown' ? deployment.status : deployment.runtime_state} />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Info
            label="Ports"
            value={deployment.ports.length ? deployment.ports.join(', ') : 'none'}
          />
          <Info label="Runtime" value={deployment.runtime_state} />
          <Info label="Execution" value={deploymentExecutionLabel(deployment.execution_status ?? deployment.status)} />
          <Info label="Health" value={deployment.health_state} />
          <Info label="Sync" value={deployment.sync_status} />
          <Info label="Uptime" value={formatDuration(deployment.uptime_seconds)} />
          <Info label="Runtime age" value={deployment.runtime_stale ? 'stale' : formatDuration(deployment.runtime_age_seconds)} />
          <Info label="Failure reason" value={deployment.runtime_failure_reason ?? 'none'} />
        </div>
        <DeploymentTargets deployment={deployment} />
        <DeploymentExecutionSummary deployment={deployment} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip icon={FileText} label={deployment.compose_source} />
          {Object.keys(deployment.credential_refs ?? {}).length ? (
            <Chip
              icon={KeyRound}
              label={`${Object.keys(deployment.credential_refs).length} secret refs`}
            />
          ) : null}
          {deployment.execution_credential_ref ? (
            <Chip icon={KeyRound} label="execution credential" />
          ) : null}
          {deployment.remote_path ? (
            <Chip icon={Activity} label={deploymentPathPreview(deployment)} />
          ) : null}
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          icon={Play}
          label="Deploy"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'deploy')}
        />
        <ActionButton
          icon={Square}
          label="Stop"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'stop')}
        />
        <ActionButton
          icon={RotateCw}
          label="Restart"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'restart')}
        />
        <ActionButton
          icon={RefreshCw}
          label="Redeploy"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'redeploy')}
        />
        <ActionButton
          icon={Eye}
          label="Inspect"
          disabled={isWorking}
          onClick={() => void onInspect(deployment)}
        />
        <ActionButton
          icon={RefreshCw}
          label="Check runtime"
          disabled={isWorking}
          onClick={() => void onRefreshRuntime(deployment)}
        />
        <ActionButton
          icon={Terminal}
          label="Logs"
          disabled={isWorking}
          onClick={() => void onLogs(deployment)}
        />
        <ActionButton
          icon={FileText}
          label="Preview"
          disabled={isWorking}
          onClick={() => void onPreview(deployment)}
        />
        <ActionButton
          icon={Pencil}
          label="Edit"
          disabled={isWorking}
          onClick={() => onEdit(deployment)}
        />
        <ActionButton
          icon={Trash2}
          label="Delete"
          disabled={isWorking}
          tone="danger"
          onClick={() => void onDelete(deployment)}
        />
      </div>
    </article>
  );
}

function DeploymentTargets({ deployment }: { deployment: Deployment }) {
  const targets = deployment.targets.length
    ? deployment.targets
    : deployment.target_server_id
      ? [
          {
            id: deployment.target_server_id,
            server_id: deployment.target_server_id,
            hostname: deployment.target_hostname,
            node_type: null,
            environment: null,
            provider: null,
            readiness: 'unknown',
            remote_path: deployment.remote_path ?? '',
            status: deployment.status,
            runtime_state: deployment.runtime_state,
            health_state: deployment.health_state,
            sync_status: deployment.sync_status,
            runtime_checked_at: deployment.runtime_checked_at,
            runtime_error: deployment.runtime_error,
            runtime_stale: deployment.runtime_stale,
            runtime_age_seconds: deployment.runtime_age_seconds,
            runtime_failure_reason: deployment.runtime_failure_reason,
            containers: [],
            missing_services: [],
            last_job_id: null,
            last_execution: null,
            created_at: deployment.created_at,
            updated_at: deployment.updated_at,
          },
        ]
      : [];

  if (!targets.length) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment targets configured.</p>;
  }

  return (
    <div className="mt-4 grid gap-2">
      {targets.map((target) => (
        <div key={target.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div>
            <Link
              className="text-sm font-semibold text-zinc-950 hover:text-zinc-700"
              to={`/inventory/${target.server_id}`}
              onClick={(event) => event.stopPropagation()}
            >
              {target.hostname ?? target.server_id}
            </Link>
            <p className="mt-0.5 text-xs text-zinc-500">
              {formatNodeType(target.node_type)} - {target.environment ?? 'unknown'} - {target.provider ?? 'unknown'} - {formatLabel(target.readiness)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RuntimeBadge value={target.runtime_state === 'unknown' ? target.status : target.runtime_state} />
            <span className="text-xs text-zinc-500">{formatDuration(target.last_execution?.duration_seconds ?? null)}</span>
          </div>
          <div className="basis-full text-xs text-zinc-500">
            runtime {formatLabel(target.runtime_state)} - health {formatLabel(target.health_state)} - sync {formatLabel(target.sync_status)}
            {target.runtime_checked_at ? ` - checked ${new Date(target.runtime_checked_at).toLocaleString()}` : ''}
            {target.runtime_stale ? ' - stale' : ''}
          </div>
          {target.containers.length ? (
            <div className="basis-full space-y-1">
              {target.containers.map((container) => (
                <div key={`${target.id}-${container.name}`} className="flex flex-wrap items-center gap-2 text-xs text-zinc-600">
                  <span className="font-semibold text-zinc-800">{container.service}</span>
                  <span>{container.name}</span>
                  <RuntimeBadge value={container.state} />
                  <span>health {formatLabel(container.health)}</span>
                  {container.restart_count !== null ? <span>restarts {container.restart_count}</span> : null}
                </div>
              ))}
            </div>
          ) : null}
          {target.missing_services.length ? (
            <p className="basis-full text-xs text-amber-700">Missing services: {target.missing_services.join(', ')}</p>
          ) : null}
          {target.runtime_error ? (
            <p className="basis-full text-xs text-rose-700">{target.runtime_error}</p>
          ) : null}
          {target.runtime_failure_reason && target.runtime_failure_reason !== target.runtime_error ? (
            <p className="basis-full text-xs text-amber-700">{target.runtime_failure_reason}</p>
          ) : null}
          {target.last_execution?.error_message ? (
            <p className="basis-full text-xs text-rose-700">{target.last_execution.error_message}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function DeploymentExecutionSummary({ deployment }: { deployment: Deployment }) {
  const execution = deployment.latest_execution;
  if (!execution) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment executions yet.</p>;
  }
  return (
    <div className="mt-3 rounded-md border border-zinc-200 px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-zinc-950">{formatLabel(execution.operation)} execution</span>
        <RuntimeBadge value={deploymentExecutionBadgeValue(execution.status)} />
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {execution.success_count}/{execution.target_count} succeeded
        {execution.failed_count ? `, ${execution.failed_count} failed` : ''} - {formatDuration(execution.duration_seconds)}
      </p>
      {execution.error_message ? <p className="mt-1 text-xs text-rose-700">{execution.error_message}</p> : null}
      {execution.target_executions.length ? (
        <div className="mt-3 space-y-2">
          {execution.target_executions.map((target) => (
            <div key={target.id} className="rounded-md bg-zinc-50 px-2 py-1.5 text-xs text-zinc-600">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-zinc-800">{target.hostname ?? target.server_id}</span>
                <span>{deploymentExecutionLabel(target.status)}</span>
              </div>
              {target.stderr ? <pre className="mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-rose-700">{target.stderr}</pre> : null}
              {!target.stderr && target.stdout ? <pre className="mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-zinc-500">{target.stdout}</pre> : null}
            </div>
          ))}
        </div>
      ) : null}
      <div className="mt-3">
        <OperationalTimeline
          activities={execution.activity_timeline}
          emptyText="No deployment runtime activity has been recorded yet."
        />
      </div>
    </div>
  );
}

function DeploymentDrawer({
  mode,
  servers,
  credentials,
  targetSelector,
  name,
  composeContent,
  envContent,
  remotePath,
  executionCredentialId,
  credentialRefs,
  dryRunPreview,
  isWorking,
  onNameChange,
  onComposeChange,
  onEnvChange,
  onRemotePathChange,
  onExecutionCredentialChange,
  onCredentialRefsChange,
  onTargetServerIdChange,
  onPreview,
  onClose,
  onSave,
}: {
  mode: 'create' | 'edit';
  servers: InventoryServer[];
  credentials: Credential[];
  targetSelector: ReturnType<typeof useTargetSelection>;
  name: string;
  composeContent: string;
  envContent: string;
  remotePath: string;
  executionCredentialId: string;
  credentialRefs: Array<{ key: string; credentialId: string }>;
  dryRunPreview: DeploymentDryRun | null;
  isWorking: boolean;
  onNameChange: (value: string) => void;
  onComposeChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onRemotePathChange: (value: string) => void;
  onExecutionCredentialChange: (value: string) => void;
  onCredentialRefsChange: (value: Array<{ key: string; credentialId: string }>) => void;
  onTargetServerIdChange: (value: string) => void;
  onPreview: () => void;
  onClose: () => void;
  onSave: () => void;
}) {
  const executionCredentials = credentials.filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password');
  const hasMissingExecutionCredential = Boolean(
    executionCredentialId &&
      !executionCredentials.some((credential) => credential.id === executionCredentialId),
  );
  return (
    <div className="fixed inset-0 z-40 overflow-hidden bg-zinc-950/40 p-3 sm:p-5">
      <aside className="mx-auto flex h-full w-[min(100%,56rem)] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-md bg-white shadow-xl sm:max-w-[calc(100vw-2.5rem)]">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-zinc-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">
              {mode === 'edit' ? 'Edit deployment' : 'Create deployment'}
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              Compose content, target host, and runtime secrets stay in the existing deployment
              workflow.
            </p>
          </div>
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-600 hover:bg-zinc-50"
            type="button"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="grid min-w-0 flex-1 gap-4 overflow-y-auto overflow-x-hidden p-5">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Deployment name</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
            />
          </label>
          <div className="min-w-0">
            <TargetSelector
              servers={servers}
              eligibility="deployments"
              selection={targetSelector.selection}
              filters={targetSelector.filters}
              title="Deployment target"
              description="Select the inventory host that will run this Compose service."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(selection) => {
                targetSelector.setMode(selection.mode);
                targetSelector.setSelectedId(selection.selectedId);
                targetSelector.setSelectedIds(selection.selectedIds);
                onTargetServerIdChange(selection.selectedId);
              }}
            />
          </div>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Compose YAML</span>
            <textarea
              className="mt-2 min-h-72 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={composeContent}
              onChange={(event) => onComposeChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Remote base path</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm"
              placeholder={defaultRemotePath}
              value={remotePath}
              onChange={(event) => onRemotePathChange(event.target.value)}
            />
          </label>
          <section className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <label className="block">
              <span className="text-sm font-medium text-zinc-950">Execution / sudo credential</span>
              <select
                className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
                value={executionCredentialId}
                onChange={(event) => onExecutionCredentialChange(event.target.value)}
              >
                <option value="">Use target saved credential or passwordless access</option>
                {hasMissingExecutionCredential ? (
                  <option value={executionCredentialId} disabled>
                    Missing saved credential ({executionCredentialId.slice(0, 8)})
                  </option>
                ) : null}
                {executionCredentials.map((credential) => (
                  <option key={credential.id} value={credential.id}>
                    {credential.name}
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-2 text-sm text-zinc-500">
              Used by deployment Jobs for Docker commands and sudo fallback. This is separate from
              credential-backed environment variables.
            </p>
            {hasMissingExecutionCredential ? (
              <p className="mt-2 text-sm font-medium text-amber-700">
                The saved execution credential no longer exists. Select an existing credential before
                saving or deploying.
              </p>
            ) : null}
          </section>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Environment file</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={envContent}
              onChange={(event) => onEnvChange(event.target.value)}
            />
          </label>
          <section className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-zinc-950">Credential-backed env</span>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                type="button"
                onClick={() =>
                  onCredentialRefsChange([
                    ...credentialRefs,
                    { key: '', credentialId: credentials[0]?.id ?? '' },
                  ])
                }
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                Add secret
              </button>
            </div>
            {credentialRefs.length ? (
              <div className="space-y-2">
                {credentialRefs.map((item, index) => (
                  <div key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                    <input
                      className="h-10 rounded-md border border-zinc-300 px-3 font-mono text-sm"
                      placeholder="ENV_KEY"
                      value={item.key}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, key: event.target.value } : row,
                          ),
                        )
                      }
                    />
                    <select
                      className="h-10 rounded-md border border-zinc-300 px-3 text-sm"
                      value={item.credentialId}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, credentialId: event.target.value } : row,
                          ),
                        )
                      }
                    >
                      <option value="">Select credential</option>
                      {credentials.map((credential) => (
                        <option key={credential.id} value={credential.id}>
                          {credential.name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="inline-flex h-10 items-center justify-center rounded-md border border-rose-300 px-3 text-rose-700 hover:bg-rose-50"
                      type="button"
                      onClick={() =>
                        onCredentialRefsChange(
                          credentialRefs.filter((_, rowIndex) => rowIndex !== index),
                        )
                      }
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">
                Use credentials for tokens, passwords, and API keys that should not live in the env
                editor.
              </p>
            )}
          </section>
          <section className="rounded-md border border-zinc-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-950">Deployment preview</h3>
                <p className="mt-1 text-sm text-zinc-500">Validate Compose and inspect redacted runtime commands before saving.</p>
              </div>
              <button
                className="inline-flex h-10 items-center rounded-md border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 hover:bg-zinc-50 disabled:bg-zinc-100"
                disabled={isWorking}
                type="button"
                onClick={onPreview}
              >
                Preview
              </button>
            </div>
            {dryRunPreview ? <DryRunPreviewPanel preview={dryRunPreview} /> : null}
          </section>
          <div className="flex justify-end gap-2 border-t border-zinc-200 pt-4">
            <button
              className="inline-flex h-10 items-center rounded-md border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="inline-flex h-10 items-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white disabled:bg-zinc-300"
              disabled={isWorking}
              type="button"
              onClick={onSave}
            >
              {mode === 'edit' ? 'Save changes' : 'Create deployment'}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-zinc-950">{value}</p>
    </div>
  );
}

function DryRunPreviewPanel({ preview }: { preview: DeploymentDryRun }) {
  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap gap-2">
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${preview.validation.valid ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-rose-50 text-rose-700 ring-1 ring-rose-200'}`}>
          {preview.validation.valid ? 'valid compose' : 'invalid compose'}
        </span>
        {preview.validation.services.map((service) => (
          <span key={service} className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
            {service}
          </span>
        ))}
      </div>
      {[...preview.validation.errors, ...preview.validation.warnings].length ? (
        <div className="space-y-1 text-sm">
          {preview.validation.errors.map((item) => (
            <p key={item} className="text-rose-700">{item}</p>
          ))}
          {preview.validation.warnings.map((item) => (
            <p key={item} className="text-amber-700">{item}</p>
          ))}
        </div>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-3">
        <Info label="Env keys" value={preview.env_keys.length ? preview.env_keys.join(', ') : 'none'} />
        <Info label="Secret refs" value={preview.credential_env_keys.length ? preview.credential_env_keys.join(', ') : 'none'} />
        <Info label="Targets" value={String(preview.targets.length)} />
      </div>
      {preview.targets.map((target) => (
        <div key={target.server_id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-zinc-950">{target.hostname ?? target.server_id}</p>
            <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-zinc-700 ring-1 ring-zinc-200">
              {target.execution_credential_ref ? 'execution credential' : 'target/passwordless'}
            </span>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-zinc-500">{target.deployment_path}</p>
          <pre className="mt-3 max-h-52 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-100">
            {target.redacted_command_preview}
          </pre>
        </div>
      ))}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-800">{value}</p>
    </div>
  );
}

function Chip({ icon: Icon, label }: { icon: typeof FileText; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </span>
  );
}

function OutputPanel({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-zinc-800 bg-zinc-950 p-4 text-xs leading-5 text-zinc-100 shadow-inner">
        {value}
      </pre>
    </section>
  );
}

function deploymentPathPreview(deployment: Deployment): string {
  const safeName = deployment.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  return `${deployment.remote_path?.replace(/\/$/, '')}/${safeName}`;
}

function statusLabel(status: DeploymentStatus | 'all'): string {
  if (status === 'draft') return 'created';
  return formatLabel(status);
}

function normalizeStatus(status: DeploymentStatus): DeploymentStatus {
  if (status === 'created') return 'draft';
  if (status === 'deployed') return 'running';
  return status;
}

function ActionButton({
  icon: Icon,
  label,
  disabled,
  tone = 'default',
  onClick,
}: {
  icon: typeof Play;
  label: string;
  disabled: boolean;
  tone?: 'default' | 'danger';
  onClick: () => void;
}) {
  const className =
    tone === 'danger'
      ? 'inline-flex h-9 items-center gap-2 rounded-md border border-rose-300 px-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50'
      : 'inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50';
  return (
    <button className={className} disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}

function formatDuration(seconds: number | null): string {
  return seconds === null ? 'unknown' : formatDurationSeconds(seconds);
}

function formatLabel(value: string): string {
  return formatOperationalLabel(value);
}

function deploymentExecutionBadgeValue(status: DeploymentStatus): string {
  return status === 'running' ? 'success' : status;
}

function deploymentExecutionLabel(status: DeploymentStatus): string {
  if (status === 'running') return 'Succeeded';
  return formatLabel(status);
}

function formatNodeType(value: string | null): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value ? formatLabel(value) : 'Unknown';
}

function formatJobsOutput(jobs: Job[]): string {
  if (!jobs.length) return '';
  return jobs
    .map((job) =>
      [
        `===== ${job.operation_type} (${job.status}) =====`,
        job.stdout ?? '',
        job.stderr ?? '',
      ]
        .filter(Boolean)
        .join('\n'),
    )
    .join('\n\n');
}

function formatDryRunPreview(preview: DeploymentDryRun): string {
  return [
    `operation: ${preview.operation}`,
    `compose: ${preview.validation.valid ? 'valid' : 'invalid'}`,
    `services: ${preview.validation.services.join(', ') || 'none'}`,
    preview.validation.errors.length ? `errors: ${preview.validation.errors.join('; ')}` : '',
    preview.validation.warnings.length ? `warnings: ${preview.validation.warnings.join('; ')}` : '',
    `env keys: ${preview.env_keys.join(', ') || 'none'}`,
    `credential env keys: ${preview.credential_env_keys.join(', ') || 'none'}`,
    ...preview.targets.map((target) =>
      [
        '',
        `===== ${target.hostname ?? target.server_id} =====`,
        `path: ${target.deployment_path}`,
        `execution credential: ${target.execution_credential_ref ? 'configured' : 'target/passwordless fallback'}`,
        target.redacted_command_preview,
      ].join('\n'),
    ),
  ].filter(Boolean).join('\n');
}

function selectedDeploymentSummary(deployment: Deployment | null): string {
  if (!deployment) return 'Select a deployment to inspect runtime state.';
  const execution = deployment.latest_execution;
  return [
    `name: ${deployment.name}`,
    `runtime: ${formatLabel(deployment.runtime_state)}`,
    `execution status: ${deployment.execution_status ?? deployment.status}`,
    `status: ${statusLabel(normalizeStatus(deployment.status))}`,
    `targets: ${deployment.targets.length ? deployment.targets.map((target) => `${target.hostname ?? target.server_id}=runtime:${target.runtime_state}/execution:${target.status}`).join(', ') : deployment.target_hostname ?? deployment.target_server_id ?? 'none'}`,
    `latest execution: ${execution ? `${execution.operation} ${execution.status} (${execution.success_count}/${execution.target_count} succeeded)` : 'none'}`,
    `ports: ${deployment.ports.length ? deployment.ports.join(', ') : 'none'}`,
    `compose source: ${deployment.compose_source}`,
    `health: ${deployment.health_state}`,
    `sync: ${deployment.sync_status}`,
    `runtime checked: ${deployment.runtime_checked_at ? new Date(deployment.runtime_checked_at).toLocaleString() : 'not checked'}`,
    `runtime age: ${formatDuration(deployment.runtime_age_seconds)}`,
    `runtime stale: ${deployment.runtime_stale ? 'yes' : 'no'}`,
    deployment.runtime_failure_reason ? `failure reason: ${deployment.runtime_failure_reason}` : '',
    deployment.runtime_error ? `runtime error: ${deployment.runtime_error}` : '',
    `remote path: ${deployment.remote_path ?? 'none'}`,
  ].filter(Boolean).join('\n');
}
