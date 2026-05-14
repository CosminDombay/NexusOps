import { useCallback, useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import { executeJob, executeJobBulk, executeOperationalAction, listJobs, listOperationalActions } from './api/jobsApi';
import { JobResultViewer } from './components/JobResultViewer';
import { JobsTable } from './components/JobsTable';
import { OperationalActionsPanel } from './components/OperationalActionsPanel';
import { RunCommandPanel } from './components/RunCommandPanel';
import type { Job, OperationalAction } from './types/job';

export function JobsPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [operationType, setOperationType] = useState('command');
  const [command, setCommand] = useState('uptime');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isExecutingAction, setIsExecutingAction] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [nextServers, nextJobs, nextActions] = await Promise.all([
        listServers(),
        listJobs(),
        listOperationalActions(),
      ]);
      setServers(nextServers);
      setJobs(nextJobs);
      setActions(nextActions);
      setSelectedServerId((current) => current || nextServers[0]?.id || '');
      setSelectedActionId((current) => current || nextActions[0]?.id || '');
    } catch (error) {
      setLoadError(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  async function handleExecute() {
    if ((!selectedServerId && selectedServerIds.length === 0) || !command.trim()) {
      return;
    }

    setIsExecuting(true);
    setExecuteError(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executeJobBulk({
          target_server_ids: selectedServerIds,
          operation_type: operationType,
          command,
        });
        const resultJobs = result.results.flatMap((item) => (item.job ? [item.job] : []));
        setJobs((currentJobs) => [...resultJobs, ...currentJobs]);
        setSelectedJobId(resultJobs[0]?.id ?? null);
        setBulkResult(`${result.success_count} succeeded, ${result.failure_count} failed`);
      } else {
        const job = await executeJob({
          target_server_id: selectedServerId,
          operation_type: operationType,
          command,
        });
        setJobs((currentJobs) => [job, ...currentJobs]);
        setSelectedJobId(job.id);
        setBulkResult(null);
      }
    } catch (error) {
      setExecuteError(getApiErrorMessage(error));
    } finally {
      setIsExecuting(false);
    }
  }

  async function handleExecuteAction() {
    if (!selectedServerId || !selectedActionId) {
      return;
    }

    const action = actions.find((candidate) => candidate.id === selectedActionId);
    if (action?.destructive) {
      const confirmed = window.confirm(`Run ${action.name} on the selected host?`);
      if (!confirmed) {
        return;
      }
    }

    setIsExecutingAction(true);
    setActionError(null);

    try {
      const job = await executeOperationalAction({
        target_server_id: selectedServerId,
        action_id: selectedActionId,
      });
      setJobs((currentJobs) => [job, ...currentJobs]);
      setSelectedJobId(job.id);
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsExecutingAction(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Reusable operational actions, remote command execution, and orchestration history."
      />

      <OperationalActionsPanel
        actions={actions}
        error={actionError}
        isExecuting={isExecutingAction}
        selectedActionId={selectedActionId}
        selectedServerId={selectedServerId}
        servers={servers}
        onExecute={handleExecuteAction}
        onSelectedActionChange={setSelectedActionId}
        onSelectedServerChange={setSelectedServerId}
      />

      <RunCommandPanel
        command={command}
        error={executeError}
        isExecuting={isExecuting}
        operationType={operationType}
        selectedServerId={selectedServerId}
        selectedServerIds={selectedServerIds}
        servers={servers}
        onCommandChange={setCommand}
        onOperationTypeChange={setOperationType}
        onSelectedServerChange={setSelectedServerId}
        onSelectedServersChange={setSelectedServerIds}
        onSubmit={handleExecute}
      />
      {bulkResult ? <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700">{bulkResult}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <JobsTable
          error={loadError}
          isLoading={isLoading}
          jobs={jobs}
          selectedJobId={selectedJob?.id ?? null}
          onRefresh={refresh}
          onSelectJob={(job) => setSelectedJobId(job.id)}
        />
        <JobResultViewer job={selectedJob} />
      </div>
    </div>
  );
}
