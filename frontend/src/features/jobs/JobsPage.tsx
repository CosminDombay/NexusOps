import { useCallback, useEffect, useMemo, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { CollapsibleSection, PageActionButton } from '../../components/operations/OperationalComponents';
import { SearchField } from '../../components/search/SearchField';
import { getApiErrorMessage } from '../../lib/api/client';
import { matchesSearch } from '../../lib/search/match';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import {
  createOperationalAction,
  deleteOperationalAction,
  executeJob,
  executeJobBulk,
  executeOperationalAction,
  listJobs,
  listOperationalActions,
  updateOperationalAction,
} from './api/jobsApi';
import { JobResultViewer } from './components/JobResultViewer';
import { JobsTable } from './components/JobsTable';
import { OperationalActionsPanel } from './components/OperationalActionsPanel';
import { RunCommandPanel } from './components/RunCommandPanel';
import type { CreateOperationalActionPayload, Job, OperationalAction } from './types/job';

type ActionFormState = CreateOperationalActionPayload;
type JobStatusFilter = 'all' | 'failed';
type JobScopeFilter = 'all' | 'profile' | 'workflow' | 'automation' | 'package' | 'deployment';

const initialActionForm: ActionFormState = {
  id: '',
  name: '',
  category: 'Custom',
  description: '',
  command: '',
  destructive: false,
};

export function JobsPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [executionCredentialRef, setExecutionCredentialRef] = useState('');
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
  const [actionBuilderInitialForm, setActionBuilderInitialForm] =
    useState<ActionFormState>(initialActionForm);
  const [editingActionId, setEditingActionId] = useState<string | null>(null);
  const [isSavingAction, setIsSavingAction] = useState(false);
  const [isActionBuilderOpen, setIsActionBuilderOpen] = useState(false);
  const [actionSearch, setActionSearch] = useState('');
  const [jobSearch, setJobSearch] = useState('');
  const [jobStatusFilter, setJobStatusFilter] = useState<JobStatusFilter>('all');
  const [jobScopeFilter, setJobScopeFilter] = useState<JobScopeFilter>('all');

  const filteredActions = useMemo(
    () =>
      actions.filter((action) =>
        matchesSearch(actionSearch, [
          action.id,
          action.name,
          action.category,
          action.description,
          action.command,
          action.is_builtin ? 'built in' : 'custom',
        ]),
      ),
    [actionSearch, actions],
  );
  const filteredJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          matchesJobStatusFilter(job, jobStatusFilter) &&
          matchesJobScopeFilter(job, jobScopeFilter) &&
          matchesSearch(jobSearch, [
            job.target_hostname,
            job.operation_type,
            job.status,
            job.command,
            job.stderr,
            job.stdout,
            job.exit_code,
            job.execution_origin,
            job.correlation_id,
          ]),
      ),
    [jobScopeFilter, jobSearch, jobStatusFilter, jobs],
  );
  const visibleSelectedJob = useMemo(
    () => filteredJobs.find((job) => job.id === selectedJobId) ?? filteredJobs[0] ?? null,
    [filteredJobs, selectedJobId],
  );

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [nextServers, nextJobs, nextActions, nextCredentials] = await Promise.all([
        listServers(),
        listJobs(),
        listOperationalActions(),
        listCredentials(),
      ]);
      setServers(nextServers);
      setJobs(nextJobs);
      setActions(nextActions);
      setCredentials(nextCredentials);
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
          credential_ref: executionCredentialRef || null,
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
          credential_ref: executionCredentialRef || null,
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
        credential_ref: executionCredentialRef || null,
      });
      setJobs((currentJobs) => [job, ...currentJobs]);
      setSelectedJobId(job.id);
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsExecutingAction(false);
    }
  }

  function startEditAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    setIsActionBuilderOpen(true);
    setEditingActionId(action.id);
    setActionBuilderInitialForm({
      id: action.id,
      name: action.name,
      category: action.category,
      description: action.description,
      command: action.command,
      destructive: action.destructive,
    });
    setActionError(null);
  }

  function resetActionForm() {
    setEditingActionId(null);
    setActionBuilderInitialForm(initialActionForm);
    setIsActionBuilderOpen(false);
  }

  async function saveAction(form: ActionFormState) {
    if (!form.id.trim() || !form.name.trim() || !form.command.trim()) {
      setActionError('Action id, name, and command are required.');
      return;
    }
    setIsSavingAction(true);
    setActionError(null);
    try {
      if (editingActionId) {
        const updated = await updateOperationalAction(editingActionId, {
          name: form.name,
          category: form.category,
          description: form.description,
          command: form.command,
          destructive: form.destructive,
        });
        setActions((current) =>
          current.map((action) => (action.id === updated.id ? updated : action)),
        );
        setSelectedActionId(updated.id);
      } else {
        const created = await createOperationalAction(form);
        setActions((current) => [...current, created]);
        setSelectedActionId(created.id);
      }
      resetActionForm();
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsSavingAction(false);
    }
  }

  async function removeAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    const confirmed = window.confirm(`Delete custom action ${action.name}?`);
    if (!confirmed) {
      return;
    }
    setActionError(null);
    try {
      await deleteOperationalAction(action.id);
      const nextActions = actions.filter((candidate) => candidate.id !== action.id);
      setActions(nextActions);
      setSelectedActionId((current) =>
        current === action.id ? (nextActions[0]?.id ?? '') : current,
      );
      if (editingActionId === action.id) {
        resetActionForm();
      }
    } catch (error) {
      setActionError(getApiErrorMessage(error));
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
        actions={
          <PageActionButton tone="secondary" onClick={() => setIsActionBuilderOpen(true)}>
            Create custom action
          </PageActionButton>
        }
      />

      <CollapsibleSection
        title="Operational action runner"
        description="Run a saved action against an inventory-managed node."
        defaultOpen
      >
        <SearchField
          className="mb-4"
          placeholder="Search actions, categories, scripts..."
          value={actionSearch}
          onChange={setActionSearch}
        />
        <OperationalActionsPanel
          actions={filteredActions}
          credentials={credentials}
          error={actionError}
          executionCredentialRef={executionCredentialRef}
          isExecuting={isExecutingAction}
          selectedActionId={selectedActionId}
          selectedServerId={selectedServerId}
          servers={servers}
          onExecute={handleExecuteAction}
          onExecutionCredentialChange={setExecutionCredentialRef}
          onDeleteAction={removeAction}
          onEditAction={startEditAction}
          onSelectedActionChange={setSelectedActionId}
          onSelectedServerChange={setSelectedServerId}
        />
      </CollapsibleSection>

      <ContextDrawer
        description="Save reusable command sequences and scripts that execute through Jobs."
        isOpen={isActionBuilderOpen}
        title={editingActionId ? 'Edit Custom Action' : 'Create Custom Action'}
        width="xl"
        onClose={resetActionForm}
      >
        <CustomActionBuilder
          editingActionId={editingActionId}
          initialForm={actionBuilderInitialForm}
          isSaving={isSavingAction}
          onCancel={resetActionForm}
          onChange={() => setActionError(null)}
          onSave={saveAction}
        />
      </ContextDrawer>

      <CollapsibleSection
        title="Raw command runner"
        description="Use for direct diagnostics and one-off commands. Saved actions should be preferred for repeatable operations."
      >
        <RunCommandPanel
          command={command}
          credentials={credentials}
          error={executeError}
          executionCredentialRef={executionCredentialRef}
          isExecuting={isExecuting}
          operationType={operationType}
          selectedServerId={selectedServerId}
          selectedServerIds={selectedServerIds}
          servers={servers}
          onCommandChange={setCommand}
          onExecutionCredentialChange={setExecutionCredentialRef}
          onOperationTypeChange={setOperationType}
          onSelectedServerChange={setSelectedServerId}
          onSelectedServersChange={setSelectedServerIds}
          onSubmit={handleExecute}
        />
      </CollapsibleSection>
      {bulkResult ? (
        <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700">{bulkResult}</p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(480px,1fr)]">
        <div className="space-y-3">
          <JobHistoryFilters
            scopeFilter={jobScopeFilter}
            statusFilter={jobStatusFilter}
            onScopeFilterChange={setJobScopeFilter}
            onStatusFilterChange={setJobStatusFilter}
          />
          <SearchField
            placeholder="Search jobs, hosts, commands, output..."
            value={jobSearch}
            onChange={setJobSearch}
          />
          <JobsTable
            error={loadError}
            isLoading={isLoading}
            jobs={filteredJobs}
            selectedJobId={visibleSelectedJob?.id ?? null}
            onRefresh={refresh}
            onSelectJob={(job) => setSelectedJobId(job.id)}
          />
        </div>
        <JobResultViewer job={visibleSelectedJob} />
      </div>
    </div>
  );
}

function JobHistoryFilters({
  scopeFilter,
  statusFilter,
  onScopeFilterChange,
  onStatusFilterChange,
}: {
  scopeFilter: JobScopeFilter;
  statusFilter: JobStatusFilter;
  onScopeFilterChange: (filter: JobScopeFilter) => void;
  onStatusFilterChange: (filter: JobStatusFilter) => void;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap gap-2">
        {[
          ['all', 'All statuses'],
          ['failed', 'Failures'],
        ].map(([value, label]) => (
          <button
            key={value}
            className={filterButtonClass(statusFilter === value)}
            type="button"
            onClick={() => onStatusFilterChange(value as JobStatusFilter)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {[
          ['all', 'All sources'],
          ['profile', 'Profiles'],
          ['workflow', 'Workflows'],
          ['automation', 'Automations'],
          ['package', 'Packages'],
          ['deployment', 'Deployments'],
        ].map(([value, label]) => (
          <button
            key={value}
            className={filterButtonClass(scopeFilter === value)}
            type="button"
            onClick={() => onScopeFilterChange(value as JobScopeFilter)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function filterButtonClass(isActive: boolean): string {
  return [
    'rounded-md px-3 py-1.5 text-sm font-semibold transition',
    isActive ? 'bg-zinc-950 text-white' : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200',
  ].join(' ');
}

function matchesJobStatusFilter(job: Job, filter: JobStatusFilter): boolean {
  if (filter === 'all') {
    return true;
  }
  return ['failed', 'cancelled', 'stale'].includes(job.status);
}

function matchesJobScopeFilter(job: Job, filter: JobScopeFilter): boolean {
  if (filter === 'all') {
    return true;
  }
  const operationType = job.operation_type.toLowerCase();
  const origin = job.execution_origin.toLowerCase();
  if (filter === 'profile') {
    return operationType.startsWith('profile:') || origin === 'profile';
  }
  if (filter === 'workflow') {
    return origin === 'workflow' || operationType.startsWith('workflow:');
  }
  if (filter === 'automation') {
    return origin === 'automation' || operationType.startsWith('automation:');
  }
  if (filter === 'package') {
    return operationType.startsWith('package:') || origin === 'package';
  }
  return operationType.startsWith('deployment:') || origin === 'deployment';
}

function CustomActionBuilder({
  editingActionId,
  initialForm,
  isSaving,
  onCancel,
  onChange,
  onSave,
}: {
  editingActionId: string | null;
  initialForm: ActionFormState;
  isSaving: boolean;
  onCancel: () => void;
  onChange: () => void;
  onSave: (form: ActionFormState) => void;
}) {
  const [form, setForm] = useState<ActionFormState>(initialForm);

  useEffect(() => {
    setForm(initialForm);
  }, [initialForm]);

  function updateField<K extends keyof ActionFormState>(field: K, value: ActionFormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    onChange();
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">
            {editingActionId ? 'Edit custom action' : 'Create custom action'}
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Save reusable command sequences and scripts that execute through Jobs.
          </p>
        </div>
        {editingActionId ? (
          <button
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel edit
          </button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="block text-sm font-medium text-zinc-700">
          ID
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm disabled:bg-zinc-100"
            disabled={Boolean(editingActionId)}
            placeholder="enable-docker-user"
            value={form.id}
            onChange={(event) => updateField('id', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Name
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.name}
            onChange={(event) => updateField('name', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Category
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.category}
            onChange={(event) => updateField('category', event.target.value)}
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm font-medium text-zinc-700">
          <input
            checked={form.destructive}
            type="checkbox"
            onChange={(event) => updateField('destructive', event.target.checked)}
          />
          Changes host
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Description
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.description}
            onChange={(event) => updateField('description', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Command or script
          <textarea
            className="mt-1 min-h-36 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
            placeholder={'set -e\nsudo usermod -aG docker $USER\nid'}
            value={form.command}
            onChange={(event) => updateField('command', event.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
          disabled={isSaving}
          type="button"
          onClick={() => onSave(form)}
        >
          {isSaving ? 'Saving' : editingActionId ? 'Save action' : 'Create action'}
        </button>
      </div>
    </section>
  );
}
