import { useEffect, useMemo, useState } from 'react';
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
  getDeploymentLogs,
  getDeploymentStatus,
  listDeployments,
  runDeploymentOperation,
  updateDeployment,
} from './api/deploymentsApi';
import type { CreateDeploymentPayload, Deployment, DeploymentStatus } from './types/deployment';

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
  const [credentialRefs, setCredentialRefs] = useState<
    Array<{ key: string; credentialId: string }>
  >([]);
  const [logs, setLogs] = useState('');
  const [inspectOutput, setInspectOutput] = useState('');
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

  async function refresh() {
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
  }

  function deploymentPayload(targets: string[]): CreateDeploymentPayload {
    return {
      name: name.trim(),
      target_server_id: targets[0],
      target_server_ids: targets,
      compose_content: composeContent,
      env_content: envContent || null,
      remote_path: remotePath.trim(),
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
    setCredentialRefs([]);
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

  async function inspect(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentStatus(deployment.id);
      setInspectOutput(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
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
  }, []);

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
            onLogs={loadLogs}
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
          credentialRefs={credentialRefs}
          isWorking={isWorking}
          onNameChange={setName}
          onComposeChange={setComposeContent}
          onEnvChange={setEnvContent}
          onRemotePathChange={setRemotePath}
          onCredentialRefsChange={setCredentialRefs}
          onTargetServerIdChange={setTargetServerId}
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
  onLogs,
  onEdit,
  onDelete,
}: {
  deployment: Deployment;
  selected: boolean;
  isWorking: boolean;
  onSelect: () => void;
  onRun: (deployment: Deployment, operation: DeploymentOperationName) => Promise<void>;
  onInspect: (deployment: Deployment) => Promise<void>;
  onLogs: (deployment: Deployment) => Promise<void>;
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
          <RuntimeBadge value={deployment.status} />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Info
            label="Ports"
            value={deployment.ports.length ? deployment.ports.join(', ') : 'none'}
          />
          <Info label="Health" value={deployment.health_state} />
          <Info label="Sync" value={deployment.sync_status} />
          <Info label="Uptime" value={formatDuration(deployment.uptime_seconds)} />
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
          {deployment.remote_path ? (
            <Chip icon={Activity} label={deploymentPathPreview(deployment)} />
          ) : null}
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          icon={Play}
          label="Start"
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
          icon={Terminal}
          label="Logs"
          disabled={isWorking}
          onClick={() => void onLogs(deployment)}
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
            <RuntimeBadge value={target.status} />
            <span className="text-xs text-zinc-500">{formatDuration(target.last_execution?.duration_seconds ?? null)}</span>
          </div>
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
        <RuntimeBadge value={execution.status} />
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {execution.success_count}/{execution.target_count} succeeded
        {execution.failed_count ? `, ${execution.failed_count} failed` : ''} - {formatDuration(execution.duration_seconds)}
      </p>
      {execution.error_message ? <p className="mt-1 text-xs text-rose-700">{execution.error_message}</p> : null}
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
  credentialRefs,
  isWorking,
  onNameChange,
  onComposeChange,
  onEnvChange,
  onRemotePathChange,
  onCredentialRefsChange,
  onTargetServerIdChange,
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
  credentialRefs: Array<{ key: string; credentialId: string }>;
  isWorking: boolean;
  onNameChange: (value: string) => void;
  onComposeChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onRemotePathChange: (value: string) => void;
  onCredentialRefsChange: (value: Array<{ key: string; credentialId: string }>) => void;
  onTargetServerIdChange: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
}) {
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
  if (seconds === null) return 'unknown';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function selectedDeploymentSummary(deployment: Deployment | null): string {
  if (!deployment) return 'Select a deployment to inspect runtime state.';
  const execution = deployment.latest_execution;
  return [
    `name: ${deployment.name}`,
    `status: ${statusLabel(normalizeStatus(deployment.status))}`,
    `targets: ${deployment.targets.length ? deployment.targets.map((target) => `${target.hostname ?? target.server_id}=${target.status}`).join(', ') : deployment.target_hostname ?? deployment.target_server_id ?? 'none'}`,
    `latest execution: ${execution ? `${execution.operation} ${execution.status} (${execution.success_count}/${execution.target_count} succeeded)` : 'none'}`,
    `ports: ${deployment.ports.length ? deployment.ports.join(', ') : 'none'}`,
    `compose source: ${deployment.compose_source}`,
    `health: ${deployment.health_state}`,
    `sync: ${deployment.sync_status}`,
    `remote path: ${deployment.remote_path ?? 'none'}`,
  ].join('\n');
}
