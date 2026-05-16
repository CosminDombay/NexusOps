import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Play, RefreshCw, Square, Terminal } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import { createDeployment, getDeploymentLogs, listDeployments, runDeploymentOperation } from './api/deploymentsApi';
import type { Deployment } from './types/deployment';

const defaultCompose = `services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`;

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('');
  const [name, setName] = useState('nginx-demo');
  const [targetServerId, setTargetServerId] = useState('');
  const [composeContent, setComposeContent] = useState(defaultCompose);
  const [envContent, setEnvContent] = useState('');
  const [logs, setLogs] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDeployments, nextServers] = await Promise.all([listDeployments(), listServers()]);
      setDeployments(nextDeployments);
      setServers(nextServers);
      setTargetServerId((current) => current || nextServers[0]?.id || '');
      setSelectedDeploymentId((current) => current || nextDeployments[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate() {
    if (!name.trim() || !targetServerId || !composeContent.trim()) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const deployment = await createDeployment({
        name,
        target_server_id: targetServerId,
        compose_content: composeContent,
        env_content: envContent || null,
      });
      setDeployments((current) => [deployment, ...current]);
      setSelectedDeploymentId(deployment.id);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
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

  useEffect(() => {
    void refresh();
  }, []);

  const selectedDeployment = deployments.find((deployment) => deployment.id === selectedDeploymentId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="Docker Deployments" description="Docker Compose projects deployed to managed Linux servers." />

      {error ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <section className="grid gap-4 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm lg:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-zinc-950">Deployment name</span>
          <input className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-zinc-950">Target host</span>
          <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={targetServerId} onChange={(event) => setTargetServerId(event.target.value)}>
            <option value="">Select host</option>
            {servers.map((server) => (
              <option key={server.id} value={server.id}>{server.hostname}</option>
            ))}
          </select>
        </label>
        <label className="block lg:col-span-2">
          <span className="text-sm font-medium text-zinc-950">Compose YAML</span>
          <textarea className="mt-2 min-h-56 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm" value={composeContent} onChange={(event) => setComposeContent(event.target.value)} />
        </label>
        <label className="block lg:col-span-2">
          <span className="text-sm font-medium text-zinc-950">Environment file</span>
          <textarea className="mt-2 min-h-24 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm" value={envContent} onChange={(event) => setEnvContent(event.target.value)} />
        </label>
        <button className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isWorking} type="button" onClick={handleCreate}>
          <Play className="h-4 w-4" aria-hidden="true" />
          Create
        </button>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <label className="block min-w-80">
            <span className="text-sm font-medium text-zinc-950">Deployment</span>
            <select className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={selectedDeploymentId} onChange={(event) => setSelectedDeploymentId(event.target.value)}>
              <option value="">Select deployment</option>
              {deployments.map((deployment) => (
                <option key={deployment.id} value={deployment.id}>{deployment.name} ({deployment.status})</option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <ActionButton icon={Play} label="Deploy" disabled={!selectedDeployment || isWorking} onClick={() => void run('deploy')} />
            <ActionButton icon={RefreshCw} label="Redeploy" disabled={!selectedDeployment || isWorking} onClick={() => void run('redeploy')} />
            <ActionButton icon={RefreshCw} label="Restart" disabled={!selectedDeployment || isWorking} onClick={() => void run('restart')} />
            <ActionButton icon={Square} label="Stop" disabled={!selectedDeployment || isWorking} onClick={() => void run('stop')} />
            <ActionButton icon={Terminal} label="Logs" disabled={!selectedDeployment || isWorking} onClick={() => void loadLogs()} />
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
                  <td className="py-3 text-zinc-600">{deployment.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Logs</h3>
        <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-zinc-950 p-4 text-xs text-zinc-50">{logs || 'No logs loaded.'}</pre>
      </section>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  disabled,
  onClick,
}: {
  icon: typeof Play;
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-semibold text-zinc-700 disabled:opacity-50" disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}
