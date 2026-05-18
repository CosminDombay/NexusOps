import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { KeyRound, Pencil, Play, Plus, RefreshCw, Square, Terminal, Trash2, X } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import { selectedTargetIds } from '../inventory/types/targetSelection';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { createDeployment, deleteDeployment, getDeploymentLogs, listDeployments, runDeploymentOperation, updateDeployment } from './api/deploymentsApi';
import type { CreateDeploymentPayload, Deployment } from './types/deployment';

const defaultCompose = `services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`;

const defaultRemotePath = '/opt/nexusops/deployments';

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('');
  const [name, setName] = useState('nginx-demo');
  const [targetServerId, setTargetServerId] = useState('');
  const targetSelector = useTargetSelection('single');
  const [composeContent, setComposeContent] = useState(defaultCompose);
  const [envContent, setEnvContent] = useState('');
  const [remotePath, setRemotePath] = useState(defaultRemotePath);
  const [credentialRefs, setCredentialRefs] = useState<Array<{ key: string; credentialId: string }>>([]);
  const [logs, setLogs] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingDeploymentId, setEditingDeploymentId] = useState<string | null>(null);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDeployments, nextServers, nextCredentials] = await Promise.all([listDeployments(), listServers(), listCredentials()]);
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

  async function handleSave() {
    const targets = selectedTargetIds({
      ...targetSelector.selection,
      selectedId: targetSelector.selection.selectedId || targetServerId,
    });
    if (!name.trim() || targets.length === 0 || !composeContent.trim() || !remotePath.trim()) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const payload = deploymentPayload(targets);
      if (editingDeploymentId) {
        const deployment = await updateDeployment(editingDeploymentId, payload);
        setDeployments((current) => current.map((item) => (item.id === deployment.id ? deployment : item)));
        setSelectedDeploymentId(deployment.id);
        setEditingDeploymentId(null);
      } else {
        const deployment = await createDeployment(payload);
        setDeployments((current) => [deployment, ...current]);
        setSelectedDeploymentId(deployment.id);
      }
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function handleEditDeployment() {
    const deployment = selectedDeployment;
    if (!deployment) {
      return;
    }
    setEditingDeploymentId(deployment.id);
    setName(deployment.name);
    setComposeContent(deployment.compose_content);
    setEnvContent(deployment.env_content ?? '');
    setRemotePath(deployment.remote_path ?? defaultRemotePath);
    setCredentialRefs(
      Object.entries(deployment.credential_refs ?? {}).map(([key, credentialId]) => ({ key, credentialId })),
    );
    targetSelector.setMode('single');
    targetSelector.setSelectedId(deployment.target_server_id ?? '');
    targetSelector.setSelectedIds([]);
    setTargetServerId(deployment.target_server_id ?? '');
    setError(null);
  }

  async function run(operation: 'deploy' | 'redeploy' | 'restart' | 'stop') {
    if (!selectedDeploymentId) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const result = await runDeploymentOperation(selectedDeploymentId, operation);
      setDeployments((current) =>
        current.map((deployment) => (deployment.id === result.deployment.id ? result.deployment : deployment)),
      );
      setLogs(`${result.job.stdout ?? ''}${result.job.stderr ? `\n${result.job.stderr}` : ''}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function loadLogs() {
    if (!selectedDeploymentId) {
      return;
    }
    setIsWorking(true);
    try {
      const result = await getDeploymentLogs(selectedDeploymentId);
      setLogs(result.logs || result.job.stderr || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleDeleteDeployment() {
    const deployment = selectedDeployment;
    if (!deployment) {
      return;
    }
    const confirmed = window.confirm(
      `Delete deployment ${deployment.name}? This removes the NexusOps record and history only. It does not stop containers or remove files from the server.`,
    );
    if (!confirmed) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      await deleteDeployment(deployment.id);
      const nextDeployments = deployments.filter((item) => item.id !== deployment.id);
      setDeployments(nextDeployments);
      setSelectedDeploymentId(nextDeployments[0]?.id ?? '');
      setLogs('');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const selectedDeployment = deployments.find((deployment) => deployment.id === selectedDeploymentId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="Docker Deployments" description="Docker Compose projects deployed to managed Linux servers." />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <section className="grid gap-4 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm lg:grid-cols-2">
        <div className="flex items-center justify-between gap-3 lg:col-span-2">
          <h2 className="text-base font-semibold text-zinc-950">{editingDeploymentId ? 'Edit deployment' : 'Create deployment'}</h2>
          {editingDeploymentId ? (
            <button className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={resetForm}>
              <X className="h-4 w-4" aria-hidden="true" />
              Cancel edit
            </button>
          ) : null}
        </div>
        <label className="block">
          <span className="text-sm font-medium text-zinc-950">Deployment name</span>
          <input className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <div className="lg:col-span-2">
          <TargetSelector
            servers={servers}
            selection={targetSelector.selection}
            filters={targetSelector.filters}
            title="Deployment targets"
            description="Create a compose deployment for one host now, or pass bulk targets for future distributed execution."
            onFiltersChange={targetSelector.setFilters}
            onSelectionChange={(selection) => {
              targetSelector.setMode(selection.mode);
              targetSelector.setSelectedId(selection.selectedId);
              targetSelector.setSelectedIds(selection.selectedIds);
              setTargetServerId(selection.selectedId);
            }}
          />
        </div>
        <label className="block lg:col-span-2">
          <span className="text-sm font-medium text-zinc-950">Compose YAML</span>
          <textarea className="mt-2 min-h-56 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm" value={composeContent} onChange={(event) => setComposeContent(event.target.value)} />
        </label>
        <section className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-4 lg:col-span-2">
          <div>
            <h3 className="text-sm font-semibold text-zinc-950">Host deployment settings</h3>
            <p className="mt-1 text-sm text-zinc-500">NexusOps writes docker-compose.yaml and .env under this base directory on the selected server.</p>
          </div>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Remote base path</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm"
              placeholder={defaultRemotePath}
              value={remotePath}
              onChange={(event) => setRemotePath(event.target.value)}
            />
          </label>
          <div className="grid gap-2 text-xs text-zinc-500 md:grid-cols-2">
            <p>Default requires the SSH user to own or write to /opt/nexusops.</p>
            <p>For non-root SSH users, use a path like /home/ubuntu/nexusops/deployments.</p>
          </div>
        </section>
        <label className="block lg:col-span-2">
          <span className="text-sm font-medium text-zinc-950">Environment file</span>
          <textarea className="mt-2 min-h-24 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm" value={envContent} onChange={(event) => setEnvContent(event.target.value)} />
        </label>
        <div className="space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-zinc-950">Credential-backed env</span>
            <button
              className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={() => setCredentialRefs((current) => [...current, { key: '', credentialId: credentials[0]?.id ?? '' }])}
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
                      setCredentialRefs((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, key: event.target.value } : row)))
                    }
                  />
                  <select
                    className="h-10 rounded-md border border-zinc-300 px-3 text-sm"
                    value={item.credentialId}
                    onChange={(event) =>
                      setCredentialRefs((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, credentialId: event.target.value } : row)))
                    }
                  >
                    <option value="">Select credential</option>
                    {credentials.map((credential) => (
                      <option key={credential.id} value={credential.id}>{credential.name}</option>
                    ))}
                  </select>
                  <button
                    className="inline-flex h-10 items-center justify-center rounded-md border border-rose-300 px-3 text-rose-700 hover:bg-rose-50"
                    type="button"
                    onClick={() => setCredentialRefs((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Use credentials for tokens, passwords, and API keys that should not live in the env editor.</p>
          )}
        </div>
        <button className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isWorking} type="button" onClick={handleSave}>
          {editingDeploymentId ? <Pencil className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
          {editingDeploymentId ? 'Save changes' : 'Create'}
        </button>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <label className="block min-w-80">
            <span className="text-sm font-medium text-zinc-950">Deployment</span>
            <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={selectedDeploymentId} onChange={(event) => setSelectedDeploymentId(event.target.value)}>
              <option value="">Select deployment</option>
              {deployments.map((deployment) => (
                <option key={deployment.id} value={deployment.id}>{deployment.name} ({deploymentStatusLabel(deployment.status)})</option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <ActionButton icon={Play} label="Deploy" disabled={!selectedDeployment || isWorking} onClick={() => void run('deploy')} />
            <ActionButton icon={RefreshCw} label="Redeploy" disabled={!selectedDeployment || isWorking} onClick={() => void run('redeploy')} />
            <ActionButton icon={RefreshCw} label="Restart" disabled={!selectedDeployment || isWorking} onClick={() => void run('restart')} />
            <ActionButton icon={Square} label="Stop" disabled={!selectedDeployment || isWorking} onClick={() => void run('stop')} />
            <ActionButton icon={Terminal} label="Logs" disabled={!selectedDeployment || isWorking} onClick={() => void loadLogs()} />
            <ActionButton icon={Pencil} label="Edit" disabled={!selectedDeployment || isWorking} onClick={handleEditDeployment} />
            <ActionButton icon={Trash2} label="Delete" disabled={!selectedDeployment || isWorking} tone="danger" onClick={() => void handleDeleteDeployment()} />
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          {isLoading ? <p className="text-sm text-zinc-500">Loading deployments...</p> : null}
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <tbody className="divide-y divide-zinc-100">
              {deployments.map((deployment) => (
                <tr key={deployment.id}>
                  <td className="py-3 font-medium text-zinc-950">{deployment.name}</td>
                  <td className="py-3 text-zinc-600">
                    {deployment.target_server_id ? (
                      <Link className="font-semibold text-zinc-800 hover:text-zinc-950" to={`/inventory/${deployment.target_server_id}`}>
                        {deployment.target_hostname ?? 'Open host'}
                      </Link>
                    ) : 'No target'}
                  </td>
                  <td className="py-3 font-mono text-xs text-zinc-500">
                    {deployment.remote_path ? deploymentPathPreview(deployment) : null}
                  </td>
                  <td className="py-3 text-zinc-600"><DeploymentStatusBadge status={deployment.status} /></td>
                  <td className="py-3 text-zinc-600">
                    {Object.keys(deployment.credential_refs ?? {}).length ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
                        <KeyRound className="h-3 w-3" aria-hidden="true" />
                        {Object.keys(deployment.credential_refs).length}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Logs</h3>
        <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-zinc-800 bg-zinc-950 p-4 text-xs leading-5 text-zinc-100 shadow-inner">{logs || 'No logs loaded.'}</pre>
      </section>
    </div>
  );
}

function deploymentPathPreview(deployment: Deployment): string {
  const safeName = deployment.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  return `${deployment.remote_path?.replace(/\/$/, '')}/${safeName}`;
}

function deploymentStatusLabel(status: Deployment['status']): string {
  if (status === 'draft') return 'created';
  if (status === 'running') return 'deployed';
  return status;
}

function DeploymentStatusBadge({ status }: { status: Deployment['status'] }) {
  const label = deploymentStatusLabel(status);
  const className =
    label === 'deployed'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : label === 'failed'
        ? 'bg-rose-50 text-rose-700 ring-rose-200'
        : label === 'stopped'
          ? 'bg-amber-50 text-amber-700 ring-amber-200'
          : 'bg-sky-50 text-sky-700 ring-sky-200';
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
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
  const className = tone === 'danger'
    ? 'inline-flex h-10 items-center gap-2 rounded-md border border-rose-300 px-3 text-sm font-semibold text-rose-700 disabled:opacity-50'
    : 'inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-semibold text-zinc-700 disabled:opacity-50';
  return (
    <button className={className} disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}
